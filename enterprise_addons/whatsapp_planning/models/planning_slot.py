from odoo import models
from odoo.tools import format_datetime
from odoo.exceptions import UserError


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    def _send_slot(self, employees, start_datetime, end_datetime, include_unassigned=True, message=None):
        if self.company_id.planning_medium != 'whatsapp':
            return super()._send_slot(employees, start_datetime, end_datetime, include_unassigned, message)

        if not include_unassigned:
            self = self.filtered('resource_id')  # noqa: PLW0642
        self.ensure_one()

        employee_with_backend = employees.filtered('user_id')
        employee_without_backend = employees - employee_with_backend
        planning = False
        employee_url_map = {}
        planning = self.env['planning.planning'].create({
            'start_datetime': start_datetime,
            'end_datetime': end_datetime,
            'include_unassigned': include_unassigned,
        })
        if employee_without_backend:
            employee_url_map = employee_without_backend.sudo()._planning_get_url(planning.date_start, planning.date_end)

        employee_url_map.update(employee_with_backend._planning_get_url(start_datetime.date(), end_datetime.date()))
        cal_url = self._get_slot_resource_urls()

        if self.employee_ids:
            template = self.company_id.wa_template_assigned_shift
        else:
            template = self.company_id.wa_template_open_shift_available

        if not template:
            raise UserError(self.env._("Can't send whatsapp message as the needed template is not present"))
        if template.status != 'approved':
            raise UserError(self.env._("Can't send whatsapp message as the needed template has not been approved"))

        date_line = self.env._("%(start)s → %(end)s", start=format_datetime(self.env, self.start_datetime), end=format_datetime(self.env, self.end_datetime))
        role_line = self.role_id.name if self.role_id else "/"
        project_line = self.project_id.name if hasattr(self, "project_id") and self.project_id else "/"
        task_line = self.task_id.name if hasattr(self, "task_id") and self.task_id else "/"
        sol_line = self.sale_line_id.name if hasattr(self, "sale_line_id") and self.sale_line_id else "/"
        if self.env.company.planning_employee_unavailabilities == 'switch':
            unassign_message = self.env._("If you need to change a shift, please contact your colleagues to request a shift exchange.")
        else:
            unassign_message = self.env._("If you are unable to work an assigned shift please unassign yourself at least %s day(s) before the shift starts.", self.env.company.planning_self_unassign_days_before)

        comp = self.env['whatsapp.composer'].create({
            'res_model': 'res.partner',
            'free_text_1': date_line,
            'free_text_2': role_line,
            'free_text_3': project_line,
            'free_text_4': task_line,
            'free_text_5': sol_line,
            'free_text_6': self.name or '/',
            'free_text_8': unassign_message,
            'button_dynamic_url_1': '?' + cal_url['google_url'].split("?")[1],
            'res_ids': employees._get_related_partners().ids,
            'batch_mode': len(employees._get_related_partners().ids) > 1,
            'wa_template_id': template.id
        })
        messages = self.env['whatsapp.message'].create(comp._create_whatsapp_messages_values())
        for message in messages:
            url = "/"
            if message.mail_message_id.partner_ids.employee_ids.id in employee_url_map:
                url = message.get_base_url() + employee_url_map[message.mail_message_id.partner_ids.employee_ids.id]
            message.free_text_json = {'free_text_7': url, **message.free_text_json}
        messages._send()

        self.write({
            'state': '2_published',
            'publication_warning': False,
        })
        return None

    def _send_shift_assigned(self, human_resource):
        if self.company_id.planning_medium != 'whatsapp':
            return super()._send_shift_assigned(human_resource)

        old_assignees = self.employee_ids - human_resource.employee_id
        reassign_names = ", ".join(employee.name for employee in human_resource.employee_id)
        if not old_assignees:
            return False
        template = self.company_id.wa_template_shift_reassigned
        if not template:
            raise UserError(self.env._("Can't send whatsapp message as the needed template is not present"))
        if template.status != 'approved':
            raise UserError(self.env._("Can't send whatsapp message as the needed template has not been approved"))

        old_users = old_assignees.filtered('user_id')
        old_non_user = old_assignees - old_users
        url_map = {}
        if old_non_user:
            planning = self.env['planning.planning'].create({
                'start_datetime': self.start_datetime,
                'end_datetime': self.end_datetime,
            })
            url_map = old_non_user.sudo()._planning_get_url(planning.date_start, planning.date_end)
        url_map.update(old_users.sudo()._planning_get_url(self.start_datetime, self.end_datetime))

        date_line = self.env._("%(start)s → %(end)s", start=format_datetime(self.env, self.start_datetime), end=format_datetime(self.env, self.end_datetime))
        role_line = self.role_id.name if self.role_id else "/"
        project_line = self.project_id.name if hasattr(self, "project_id") and self.project_id else "/"
        task_line = self.task_id.name if hasattr(self, "task_id") and self.task_id else "/"
        sol_line = self.sale_line_id.name if hasattr(self, "sale_line_id") and self.sale_line_id else "/"
        comp = self.env['whatsapp.composer'].create({
            'res_model': 'res.partner',
            'free_text_1': reassign_names,
            'free_text_2': date_line,
            'free_text_3': role_line,
            'free_text_4': project_line,
            'free_text_5': task_line,
            'free_text_6': sol_line,
            'free_text_7': self.name or '/',
            'res_ids': old_assignees._get_related_partners().ids,
            'batch_mode': len(old_assignees._get_related_partners().ids) > 1,
            'wa_template_id': template.id,
        })
        messages = self.env['whatsapp.message'].create(comp._create_whatsapp_messages_values())
        for message in messages:
            message.free_text_json = {**message.free_text_json, 'free_text_8': url_map.get(message.mail_message_id.res_id, '/')}
        messages._send()

    def _get_employee_contact_field(self):
        return 'work_phone' if self.company_id.planning_medium == 'whatsapp' else super()._get_employee_contact_field()

    def _get_employee_contact_missing_fields_form_view_ref(self):
        return 'whatsapp_planning.hr_employee_view_form_phone' if self.company_id.planning_medium == 'whatsapp' else super()._get_employee_contact_missing_fields_form_view_ref()
