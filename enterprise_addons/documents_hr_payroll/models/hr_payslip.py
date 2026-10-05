# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HrPayslip(models.Model):
    _name = 'hr.payslip'
    _inherit = ['hr.payslip', 'documents.mixin']

    document_access_url = fields.Char(compute="_compute_document_access_url")

    def action_resend_payslips(self, notify=False):
        def show_notification(notification_type, message):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Send Payslip By Email"),
                    'type': notification_type,
                    'message': message
                }
            }

        if not self.env.user.has_group('hr_payroll.group_hr_payroll_user'):
            raise UserError(_('You can not send the documents link to the employee.'))
        payslips_sudo = self.sudo()
        if any(payslip.state not in ['validated', 'paid'] for payslip in payslips_sudo):
            return show_notification('warning', _('A payslip should be validated or paid to be sent to the employee.'))
        invalid_employees = payslips_sudo.employee_id.filtered(lambda e: not (e.private_email or e.work_email))
        if invalid_employees:
            raise UserError(
                _('Employee\'s private or work email must be set to use "Send By Email" function:\n%s',
                  '\n'.join(invalid_employees.mapped('name'))))

        payslip_without_documents = payslips_sudo.filtered(lambda p: not p.document_access_url)
        if payslip_without_documents:
            message = _("Some payslips could not be resend as they do not have related document")
            return show_notification("warning", message)

        return {
            'name': _('Send Email'),
            'type': 'ir.actions.act_window',
            'target': 'new',
            'view_mode': 'form',
            'res_model': 'hr.payslip.send.mail',
            'context': {
                'default_payslip_ids': self.ids,
            },
        }

    def _get_document_vals_access_rights(self):
        """ All payslips should be accessible in 'Anyone with the link' to make the link permanent.
        The document must be still accessible even if the employee and its user (if any) are archived."""
        return {
            'access_via_link': 'view',
            'access_internal': 'none',
            'is_access_via_link_hidden': True,
        }

    def _get_document_members(self):
        return [(self.employee_id.user_id.partner_id or self.employee_id.work_contact_id, ('view', False))]

    def _get_document_folder(self):
        return self.employee_id.hr_employee_payroll_folder_id

    def _generate_pdf(self):
        """ Generate the missing folders before the PDF attachments, which are filed in them.

        An employee may have no folder yet, e.g. when they were archived at the installation of the
        module (their folders are only generated for the active ones), as for the declarations.
        """
        if missing := self.employee_id.filtered(lambda e: not e.hr_employee_payroll_folder_id):
            missing._generate_employee_documents_folders()
        return super()._generate_pdf()

    def _pdf_post_create(self, employee_attachments):
        """ Create a shortcut in the employee's My Drive for each payslip document. """
        super()._pdf_post_create(employee_attachments)
        self.env["documents.document"].sudo().create([
            document.sudo()._get_base_shortcut_vals() | {"owner_id": employee.user_id.id, "folder_id": False}
            for employee, attachments in employee_attachments.items()
            if employee.user_id.active
            for document in attachments.document_ids
        ])

    def _get_email_template(self):
        return self.env.ref(
            'documents_hr_payroll.mail_template_new_payslip', raise_if_not_found=False
        )

    def _compute_document_access_url(self):
        documents = self.env["documents.document"].search(
            [('res_model', '=', self._name), ('res_id', 'in', self.ids)],
            order='res_id, id desc'
        )
        access_url_per_payslip = dict()
        for document in documents:
            if document.res_id not in access_url_per_payslip:  # keep last document for each payslip
                access_url_per_payslip[document.res_id] = document.access_url
        for payslip in self:
            payslip.document_access_url = access_url_per_payslip.get(payslip.id)

    def _check_send_payslip_mail(self):
        self.ensure_one()
        res = super()._check_send_payslip_mail()
        return res and self._check_create_documents()

    @api.model
    def _cron_generate_pdf(self, batch_size=False):
        is_rescheduled = super()._cron_generate_pdf(batch_size=batch_size)
        if is_rescheduled:
            return is_rescheduled

        # Post declarations from mixin
        lines = self.env['hr.payroll.employee.declaration'].search([('pdf_to_post', '=', True)])
        if lines:
            BATCH_SIZE = batch_size or 30
            lines_batch = lines[:BATCH_SIZE]
            lines_batch._post_pdf()
            lines_batch.write({'pdf_to_post': False})
            # if necessary, retrigger the cron to generate more pdfs
            if len(lines) > BATCH_SIZE:
                self.env.ref('hr_payroll.ir_cron_generate_payslip_pdfs')._trigger()
                return True
        return False
