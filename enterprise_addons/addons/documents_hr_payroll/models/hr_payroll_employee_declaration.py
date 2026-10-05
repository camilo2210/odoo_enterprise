# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, Command, fields, models

_logger = logging.getLogger(__name__)


class HrPayrollEmployeeDeclaration(models.Model):
    _inherit = 'hr.payroll.employee.declaration'

    pdf_to_post = fields.Boolean()
    state = fields.Selection(
        selection_add=[
            ('pdf_to_post', 'Queued PDF posting'),
            ('pdf_posted', 'Posted PDF')
        ], ondelete={'pdf_to_post': 'set pdf_generated', 'pdf_posted': 'set pdf_generated'})
    document_id = fields.Many2one('documents.document')

    @api.depends('pdf_to_post', 'document_id')
    def _compute_state(self):
        super()._compute_state()
        for declaration in self:
            if declaration.document_id:
                declaration.state = 'pdf_posted'
            elif declaration.pdf_to_post:
                declaration.state = 'pdf_to_post'

    def _get_posted_documents(self):
        document_data = self.env['documents.document']._read_group([
            ('name', 'in', [line.pdf_filename for line in self]), ('active', '=', True)],
            groupby=['name'], aggregates=['__count'])
        mapped_data = dict(document_data)
        return [posted_filename for posted_filename in mapped_data if mapped_data[posted_filename] > 0]

    def _post_pdf(self):
        missing = self.employee_id.filtered(lambda employee: not employee.hr_employee_payroll_folder_id)
        if missing:
            missing._generate_employee_documents_folders()

        lines = self.filtered('employee_id.hr_employee_payroll_folder_id')
        if lines != self:
            _logger.warning(
                "Cannot post payroll declarations %s: no Payroll folder for their employee, "
                "the Employees folder of their company is not configured.",
                (self - lines).ids,
            )
            if not lines:
                return

        existing_documents = self.env['documents.document'].search([
            ('name', 'in', lines.mapped('pdf_filename')),
            ('folder_id', 'in', lines.employee_id.hr_employee_payroll_folder_id.ids),
        ])
        document_map = {(document.name, document.folder_id.id): document for document in existing_documents}
        document_vals_per_line = {}

        # Create or overwrite documents
        for line in lines:
            payroll_folder = line.employee_id.hr_employee_payroll_folder_id
            existing_document = document_map.get((line.pdf_filename, payroll_folder.id))

            if existing_document:
                existing_document.write({'raw': line.pdf_file})
                line.document_id = existing_document
                continue

            partner_id = self.env[line.res_model]._get_posted_document_owner(line.employee_id).partner_id.id
            access_ids = {
                'access_ids': [Command.create({'partner_id': partner_id, 'role': 'view'})],
            } if partner_id else {}
            document_vals_per_line[line] = {
                'owner_id': False,
                'partner_id': partner_id or False,
                'raw': line.pdf_file,
                'name': line.pdf_filename,
                'folder_id': payroll_folder.id,
                'access_via_link': 'view',
                'access_internal': 'none',
                'is_access_via_link_hidden': True,
                **access_ids,
            }
        if document_vals_per_line:
            shortcut_vals = []
            vals_list = list(document_vals_per_line.values())
            new_documents = self.env['documents.document'].create(vals_list)
            for line, new_document in zip(document_vals_per_line, new_documents):
                line.document_id = new_document
                if employee_user := line.employee_id.user_id.filtered('active'):
                    # Add shortcut in employee's My Drive
                    shortcut_vals.append(new_document._get_base_shortcut_vals() | {
                        "folder_id": False,
                        "owner_id": employee_user.id,
                    })
            if shortcut_vals:
                self.env['documents.document'].sudo().create(shortcut_vals)

        # Send email if template and email address exist
        template = self.env[lines[0].res_model]._get_posted_mail_template()
        if template:
            for line in lines:
                employee = line.employee_id
                email = employee.private_email or employee.work_email
                if email:
                    template.send_mail(line.id, email_layout_xmlid='mail.mail_notification_light')

    @api.model_create_multi
    def create(self, vals_list):
        declarations = super().create(vals_list)
        if any(declaration.pdf_to_post for declaration in declarations):
            self.env.ref('hr_payroll.ir_cron_generate_payslip_pdfs')._trigger()
        return declarations

    def write(self, vals):
        res = super().write(vals)
        if vals.get('pdf_to_post'):
            self.env.ref('hr_payroll.ir_cron_generate_payslip_pdfs')._trigger()
        return res

    def action_post_in_documents(self):
        posted_documents = self._get_posted_documents()
        conflicts = self.filtered(lambda l: l.pdf_filename in posted_documents)
        new_files = self - conflicts

        if new_files:
            new_files.write({'pdf_to_post': True})
            self.env.ref('hr_payroll.ir_cron_generate_payslip_pdfs')._trigger()

        if conflicts:
            return {
                'name': self.env._('File(s) already exist'),
                'type': 'ir.actions.act_window',
                'res_model': 'payroll.overwrite.employee.declaration',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_declaration_ids': [(6, 0, conflicts.ids)],
                }
            }

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': self.env._("PDFs will be posted in Documents shortly"),
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'reload'
                }
            }
        }
