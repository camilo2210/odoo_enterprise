# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
import logging

from collections import defaultdict

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools.date_utils import end_of

_logger = logging.getLogger(__name__)


class HrPayrollEmployeeDeclaration(models.Model):
    _name = 'hr.payroll.employee.declaration'
    _description = 'Payroll Employee Declaration'
    _rec_name = 'employee_id'

    res_model = fields.Char(
        'Declaration Model Name', required=True, index=True)
    res_id = fields.Many2oneReference(
        'Declaration Model Id', index=True, model_field='res_model', required=True)
    employee_id = fields.Many2one('hr.employee', domain="[('company_id', '=', company_id), '|', ('active', '=', True), ('active', '=', False)]", required=True)
    version_id = fields.Many2one('hr.version', domain="[('employee_id', '=', employee_id)]", compute="_compute_version_id", store=True, readonly=False)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    pdf_file = fields.Binary('PDF File', readonly=True, attachment=False)
    pdf_filename = fields.Char()
    pdf_to_generate = fields.Boolean()
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pdf_to_generate', 'Queued PDF generation'),
        ('pdf_generated', 'Generated PDF'),
        ('error', 'PDF generation error'),
    ], compute='_compute_state', store=True)
    declaration_error = fields.Text('Error Description', readonly=True)

    _unique_employee_sheet = models.Constraint(
        'unique(employee_id, res_model, res_id)',
        "An employee can only have one declaration per sheet.",
    )

    @api.depends('pdf_to_generate', 'pdf_file', 'declaration_error')
    def _compute_state(self):
        for declaration in self:
            if declaration.declaration_error:
                declaration.state = 'error'
            elif declaration.pdf_to_generate:
                declaration.state = 'pdf_to_generate'
            elif declaration.pdf_file:
                declaration.state = 'pdf_generated'
            else:
                declaration.state = 'draft'

    @api.depends('res_model', 'res_id', 'employee_id')
    def _compute_version_id(self):
        """
        By default, we will take the version that matches the end of the year field from the `hr.payroll.declaration.mixin`.
        For declarations that would rely more on the version_id field, it is recommended to customize this computation to
        better fit the specific need of the report.
        """
        declaration_map = {}
        for model, records in self.grouped('res_model').items():
            res_ids = records.mapped('res_id')
            if 'year' in self.env[model]._fields:  # We expect the model to use the mixin for the default computation.
                declarations = self.env[model].browse(res_ids)
                for decl in declarations:
                    declaration_map[model, decl.id] = decl

        for record in self:
            declaration = declaration_map.get((record.res_model, record.res_id))
            if declaration and declaration.year:
                end_of_period = end_of(datetime.date(int(declaration.year), 1, 1), 'year')
                version = record.employee_id._get_version(date=end_of_period)
            elif record.version_id:
                version = record.version_id
            else:
                version = record.employee_id.current_version_id.id
            record.version_id = version

    def _generate_pdf(self):
        report_sudo = self.env["ir.actions.report"].sudo()
        declarations_by_sheet = defaultdict(lambda: self.env['hr.payroll.employee.declaration'])
        for declaration in self:
            declarations_by_sheet[(declaration.res_model, declaration.res_id)] += declaration


        for (res_model, res_id), declarations in declarations_by_sheet.items():
            sheet = self.env[res_model].browse(res_id)
            if not sheet.exists():
                _logger.warning('Sheet %s %s does not exist', res_model, res_id)
                continue
            report_id = sheet._get_pdf_report().id
            has_global = any(not d.employee_id for d in declarations)  # eg: Individual account at company level
            if has_global:
                employees = self.env[res_model].browse(res_id).line_ids.employee_id
            else:
                employees = declarations.employee_id
            try:
                rendering_data = sheet._get_rendering_data(employees)
            except UserError as e:
                rendering_data = {'error': str(e)}
            if 'error' in rendering_data:
                sheet.pdf_error = rendering_data['error']
                continue
            for employee, error_msg in rendering_data.get('employees_with_error', {}).items():
                declaration = declarations.filtered(lambda d: d.employee_id == employee)
                if declaration:
                    declaration.declaration_error = error_msg
            rendering_data = sheet._post_process_rendering_data_pdf(rendering_data)

            pdf_files = []
            sheet_count = len(rendering_data)
            counter = 1
            for employee, employee_data in rendering_data.items():
                if (employee and employee not in declarations.employee_id) or (not employee and not has_global):
                    continue
                _logger.info('Printing %s (%s/%s)', sheet._description, counter, sheet_count)
                counter += 1
                sheet_filename = sheet._get_pdf_filename(employee)
                sheet_file, dummy = report_sudo.with_context(lang=employee.lang or self.env.lang)._render_qweb_pdf(
                    report_id,
                    [employee.id],
                    data={
                        "report_data": employee_data,
                        "employee": employee,
                        "company_id": employee.company_id,
                        "payroll_config_id": employee.company_id.current_payroll_config_id,
                    },
                )
                pdf_files.append((employee, sheet_filename, sheet_file))
            if pdf_files:
                sheet._process_files(pdf_files)

    @api.model_create_multi
    def create(self, vals_list):
        declarations = super().create(vals_list)
        if any(declaration.pdf_to_generate for declaration in declarations):
            self.env.ref('hr_payroll.ir_cron_generate_payslip_pdfs')._trigger()
        return declarations

    def write(self, vals):
        res = super().write(vals)
        if vals.get('pdf_to_generate'):
            self.env.ref('hr_payroll.ir_cron_generate_payslip_pdfs')._trigger()
        return res

    def action_generate_pdf(self):
        if self:
            self.write({'pdf_to_generate': True, 'declaration_error': False})
            self.env.ref('hr_payroll.ir_cron_generate_payslip_pdfs')._trigger()
        else:
            not_generated_declaration_pdfs = self.env["hr.payroll.employee.declaration"].search([('state', '=', 'draft')])
            not_generated_declaration_pdfs.write({'pdf_to_generate': True, 'declaration_error': False})
            self.env.ref('hr_payroll.ir_cron_generate_payslip_pdfs')._trigger()
        message = _("PDF generation started. It will be available shortly.")
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': message,
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'reload'
                }
            }
        }

    def action_print_pdf(self):
        """
        Synchronously generates the pdf file and downloads it for a single declaration.
        """
        self.ensure_one()
        self._generate_pdf()

        if self.declaration_error:
            raise UserError(self.env._("Cannot generate PDF: %s", self.declaration_error))

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self._name}/{self.id}/pdf_file/{self.pdf_filename}?download=true',
            'target': 'self',
        }

    @api.autovacuum
    def _gc_orphan_declarations(self):
        orphan_ids = []
        grouped_declarations = self._read_group([], ['res_model'], ['res_id:array_agg'])
        for res_model, res_ids in grouped_declarations:
            existing_ids = set(self.env[res_model].browse(set(res_ids)).exists().ids)
            orphan_ids.extend(res_id for res_id in res_ids if res_id not in existing_ids)
        if orphan_ids:
            self.browse(orphan_ids).unlink()
