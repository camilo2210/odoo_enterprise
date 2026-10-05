# Part of Odoo. See LICENSE file for full copyright and licensing details.
import datetime
import uuid
from zoneinfo import ZoneInfo

from odoo import api, Command, fields, models


class PlanningPlanning(models.Model):
    _name = 'planning.planning'
    _description = 'Schedule'

    @api.model
    def _default_access_token(self):
        return str(uuid.uuid4())

    start_datetime = fields.Datetime("Start Date", required=True)
    end_datetime = fields.Datetime("Stop Date", required=True)
    include_unassigned = fields.Boolean("Includes Open Shifts", default=True)
    access_token = fields.Char("Security Token", default=_default_access_token, required=True, copy=False, readonly=True)
    company_id = fields.Many2one('res.company', string="Company", required=True, index=True, default=lambda self: self.env.company,
        help="Company linked to the material resource. Leave empty for the resource to be available in every company.")
    date_start = fields.Date('Date Start', compute='_compute_dates')
    date_end = fields.Date('Date End', compute='_compute_dates')
    allow_self_unassign = fields.Boolean('Let Employee Unassign Themselves', compute='_compute_allow_self_unassign')
    self_unassign_days_before = fields.Integer("Days before shift for unassignment", related="company_id.planning_self_unassign_days_before", export_string_translation=False)
    is_planning_preview = fields.Boolean(string="Is Planning Preview")

    @api.depends('start_datetime', 'end_datetime')
    @api.depends_context('uid')
    def _compute_dates(self):
        tz = ZoneInfo(self.env.user.tz or 'UTC')
        for planning in self:
            planning.date_start = planning.start_datetime.replace(tzinfo=datetime.UTC).astimezone(tz).replace(tzinfo=None)
            planning.date_end = planning.end_datetime.replace(tzinfo=datetime.UTC).astimezone(tz).replace(tzinfo=None)

    def _compute_display_name(self):
        """ This override is need to have a human readable string in the email light layout header (`message.record_name`) """
        self.display_name = self.env._('Planning')

    def _compute_allow_self_unassign(self):
        self.allow_self_unassign = self.company_id.planning_employee_unavailabilities == "unassign"

    # ----------------------------------------------------
    # Business Methods
    # ----------------------------------------------------

    def _is_slot_in_planning(self, slot_sudo):
        return (
            self
            and slot_sudo.start_datetime >= self.start_datetime
            and slot_sudo.end_datetime <= self.end_datetime
            and slot_sudo.state == "2_published"
        )

    def _get_ics_file(self, calendar, employee):
        self.ensure_one()
        slots_in_planning = self.env['planning.slot'].search([
            ('start_datetime', '>=', self.start_datetime),
            ('end_datetime', '<=', self.end_datetime),
            ('state', '=', '2_published'),
            ('resource_ids', 'in', employee.resource_id.id),
        ])
        slots_in_planning._get_ics_file(calendar, employee.tz)
        return calendar

    def _send_planning(self, slots, message=None, employees=False):
        email_from = self.env.user.email or self.env.user.company_id.email or ''
        # extract planning URLs
        employees_sudo = employees.sudo()
        employee_url_map = employees_sudo._planning_get_url(self.date_start, self.date_end)
        ics_url_per_employee_id = {e.id: f'/planning/{self.access_token}/{e.employee_token}.ics' for e in employees_sudo}
        # send planning email template with custom domain per employee
        template = self.env.ref('planning.email_template_planning_planning', raise_if_not_found=False)
        template_context = {
            'slot_unassigned': self.include_unassigned,
            'message': message,
        }
        if template:
            # /!\ For security reason, we only given the public employee to render mail template
            recipients = self.env['hr.employee.public'].browse(employees.ids).filtered('work_email')
            planning_attachment = self.env['ir.attachment']
            if recipients:
                min_startdate = min(slots.mapped('start_datetime'))
                max_enddate = max(slots.mapped('end_datetime'))
                pdf_content = self.env['planning.slot']._generate_planning_report_pdf(min_startdate, max_enddate, slots.ids)
                if pdf_content:
                    planning_attachment = self.env['ir.attachment'].create({
                        'name': self.env._("Planning Report.pdf"),
                        'type': 'binary',
                        'raw': pdf_content,
                        'res_model': self._name,
                        'res_id': self.id,
                        'mimetype': 'application/pdf',
                    })
            for employee in recipients:
                assigned_new_shift = bool(slots.filtered(lambda slot: employee.id in slot.employee_ids.ids))
                template_context['employee'] = employee
                template_context['start_datetime'] = self.date_start
                template_context['end_datetime'] = self.date_end
                template_context['planning_url'] = employee_url_map.get(employee.id)
                template_context['planning_url_ics'] = ics_url_per_employee_id[employee.id] if assigned_new_shift else False
                template_context['assigned_new_shift'] = assigned_new_shift
                template_context['is_internal_user'] = employee.user_id and not employee.user_id.share
                template.with_context(**template_context).send_mail(self.id,
                    email_values={
                        'email_to': employee.work_email,
                        'email_from': email_from,
                        'attachment_ids': [Command.link(planning_attachment.id)],
                    },
                    email_layout_xmlid='mail.mail_notification_light',
                )

        # mark as sent
        slots.write({
            'state': '2_published',
            'publication_warning': False,
        })
        return True

    def _get_preview_planning(self, start_datetime, end_datetime, include_unassigned):
        Planning = self.env['planning.planning']
        planning = Planning.search([
            ('start_datetime', '=', start_datetime),
            ('end_datetime', '=', end_datetime),
            ('is_planning_preview', '=', True),
        ], limit=1)
        if not planning:
            planning = Planning.create({
                'start_datetime': start_datetime,
                'end_datetime': end_datetime,
                'include_unassigned': include_unassigned,
            })
        return planning

    @api.autovacuum
    def _gc_planning_preview(self):
        limit_dt = fields.Datetime.subtract(fields.Datetime.now(), months=3)
        plannings = self.env['planning.planning'].search([
            ('is_planning_preview', '=', True),
            ('create_date', '<=', limit_dt),
        ])
        plannings.unlink()
