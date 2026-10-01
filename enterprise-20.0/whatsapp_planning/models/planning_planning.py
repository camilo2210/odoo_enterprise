from datetime import datetime
from odoo.tools import format_date
from odoo import models
from odoo.exceptions import UserError


class PlanningPlanning(models.Model):
    _inherit = 'planning.planning'

    def _send_planning(self, slots, message=None, employees=False):
        if self.company_id.planning_medium != 'whatsapp':
            return super()._send_planning(slots, message, employees)

        template = self.company_id.wa_template_schedule_published
        if not template:
            raise UserError(self.env._("Can't send whatsapp message as the needed template is not present"))
        if template.status != 'approved':
            raise UserError(self.env._("Can't send whatsapp message as the needed template has not been approved"))

        employees_sudo = employees.sudo()
        employee_url_map = employees_sudo._planning_get_url(self.date_start, self.date_end)
        ics_url_per_employee_id = {
            e.id: f'/planning/{self.access_token}/{e.employee_token}.ics'
            for e in employees_sudo
        }

        ## /!\ For security reason, we only make message models for public employees
        first_start_date = {}
        last_end_date = {}
        for slot in slots:
            if not slot.employee_ids:
                continue
            for employee in slot.employee_ids:
                if employee not in first_start_date:
                    first_start_date[employee.id] = slot.start_datetime
                    last_end_date[employee.id] = slot.end_datetime
                    continue
                first_start_date[employee.id] = min(first_start_date[employee.id], slot.start_datetime)
                last_end_date[employee.id] = max(last_end_date[employee.id], slot.end_datetime)

        for employee in employees:
            if employee.id not in first_start_date:
                first_start_date[employee.id] = self.date_start
                last_end_date[employee.id] = self.date_end
        public_employees = self.env['hr.employee.public'].browse(employees.ids)
        comp = self.env['whatsapp.composer'].create({
            'res_model': 'res.partner',
            'free_text_1': format_date(self.env, datetime(first_start_date[employee.id].year, first_start_date[employee.id].month, first_start_date[employee.id].day)),
            'free_text_2': format_date(self.env, datetime(last_end_date[employee.id].year, last_end_date[employee.id].month, last_end_date[employee.id].day)),
            'res_ids': public_employees._get_related_partners().ids,
            'batch_mode': len(public_employees._get_related_partners().ids) > 1,
            'wa_template_id': template.id
        })
        messages = self.env['whatsapp.message'].create(comp._create_whatsapp_messages_values())
        for message in messages:
            employee_id = message.mail_message_id.res_id
            message.free_text_json = {
                **message.free_text_json,
                'free_text_1': format_date(self.env, datetime(first_start_date[employee_id].year, first_start_date[employee_id].month, first_start_date[employee_id].day)),
                'free_text_2': format_date(self.env, datetime(last_end_date[employee.id].year, last_end_date[employee.id].month, last_end_date[employee.id].day)),
                'free_text_4': employee_url_map.get(employee.id, "/"),
                'button_dynamic_url_1': ics_url_per_employee_id[employee.id],
            }
            message._send()

        # mark as sent
        return slots.write({
            'state': '2_published',
            'publication_warning': False,
        })
