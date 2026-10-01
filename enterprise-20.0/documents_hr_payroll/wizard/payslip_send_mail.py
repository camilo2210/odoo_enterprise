# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools import format_date


class HrPayslipSendMail(models.TransientModel):
    _name = 'hr.payslip.send.mail'
    _description = 'Send payslips to Employee by email'

    payslip_ids = fields.Many2many('hr.payslip', string='Payslips', required=True)
    employee_ids = fields.Many2many('hr.employee', string="Recipients", compute="_compute_employee_ids")
    custom_comment = fields.Html('Custom Comment', sanitize=True)
    body_html = fields.Html('Body', compute='_compute_body_html')

    @api.depends('payslip_ids')
    def _compute_employee_ids(self):
        self.employee_ids = self.payslip_ids.employee_id

    @api.depends('payslip_ids', 'employee_ids', 'custom_comment')
    def _compute_body_html(self):
        self.body_html = self._get_employee_body_html(self.payslip_ids.employee_id[0])

    def action_send(self):
        for employee in self.employee_ids:
            self.env['hr.employee'].sudo().browse(employee.id).message_notify(
                body=self._get_employee_body_html(employee),
                partner_ids=[employee.work_contact_id.id],  # send to private address
                subtype_xmlid='mail.mt_comment',
                email_layout_xmlid='mail.mail_notification_light',
            )
        for payslip in self.payslip_ids:
            payslip._message_log(body=self.env._("The payslip has been sent to the employee by email."))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': self.env._("%(payslips)s payslip(s), sent to %(employees)s employee(s)",
                                      payslips=len(self.payslip_ids), employees=len(self.employee_ids)),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def _get_employee_body_html(self, employee):
        payslips = self.payslip_ids.filtered(lambda p: p.employee_id == employee)
        partner = employee.user_partner_id or employee.work_contact_id
        period_by_payslip_id = {payslip.id: self.env._("Payslip %(date_from)s - %(date_to)s",
            date_from=format_date(self.env, payslip.date_from, lang_code=partner.lang, date_format='medium'),
            date_to=format_date(self.env, payslip.date_to, lang_code=partner.lang, date_format='medium')
        ) for payslip in payslips}
        return self.env['ir.qweb']._render(
            'documents_hr_payroll.documents_hr_payroll_resend_payslip_template', {
            'partner': partner,
            'payslips': payslips,
            'period_by_payslip_id': period_by_payslip_id,
            'custom_comment': self.custom_comment
        })
