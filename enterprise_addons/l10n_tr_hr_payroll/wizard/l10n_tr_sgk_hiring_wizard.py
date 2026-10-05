# Part of Odoo. See LICENSE file for full copyright and licensing details.
from lxml import etree

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.xml_utils import cleanup_xml_node
from odoo.tools.binary import BinaryBytes


class L10nTrSGKHiringWizard(models.TransientModel):
    _name = 'l10n.tr.sgk.hiring.wizard'
    _description = 'SGK Hiring Notice'

    @api.model
    def default_get(self, fields):
        if self.env.company.country_id.code != 'TR':
            raise UserError(self.env._('Generating SGK report only works in Turkey company, Please try again in turkey company.'))
        return super().default_get(fields)

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    employee_ids = fields.Many2many('hr.employee', domain="[('company_id', '=', company_id)]", required=True)
    xml_file = fields.Binary('SGK XML File', readonly=True, store=True)
    xml_filename = fields.Char()
    is_transferred = fields.Boolean('Is Transferred from another Workspace')
    former_sgk_number = fields.Char('Former Workspace SGK Number')

    def action_generate_report(self):
        self.ensure_one()
        self._pre_generate_validation()
        xml_str = self.env['ir.qweb']._render('l10n_tr_hr_payroll.l10n_tr_sgk_hiring_notice_template', {
            'employees': self.employee_ids,
            'company': self.env.company,
            'former_sgk_number': self.former_sgk_number or '',
        })

        root = cleanup_xml_node(xml_str, remove_blank_text=False, remove_blank_nodes=False)
        self.xml_file = BinaryBytes(
            etree.tostring(
                root,
                pretty_print=True,
                encoding="utf-8",
                xml_declaration=True,
            )
        )
        self.xml_filename = f"{self.env._("SGK Hiring-%(employees)s", employees=", ".join(self.employee_ids.mapped("name")))}.xml"

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'name': self._description,
            'view_mode': 'form',
            'target': 'new',
        }

    def _get_missing_fields(self, record, required_fields):
        missing = []
        fields = record._fields
        for field_name in required_fields:
            if not record[field_name]:
                missing.append(fields[field_name].string)
        return missing

    def _pre_generate_validation(self):
        error_message = []
        company_missing_fields = self._get_missing_fields(self.env.company, [
            'l10n_tr_sgk_intermediary_code', 'l10n_tr_sgk_workspace_registration_no',
        ])
        if company_missing_fields:
            error_message.append(
                self.env._('Cannot generate report for company: %(company_name)s.\nMissing:\n- %(fields)s\nPlease configure it from Setting',
                    company_name=self.company_id.name,
                    fields='\n- '.join(company_missing_fields),
                )
            )
        for emp in self.employee_ids:
            missing = self._get_missing_fields(emp, [
                'certificate', 'identification_id', 'l10n_tr_first_name', 'l10n_tr_last_name', 'l10n_tr_insurance_type',
                'l10n_tr_graduation_year', 'l10n_tr_labour_sector', 'l10n_tr_occupational_code', 'l10n_tr_job_code',
            ])
            if missing:
                error_message.append(
                    self.env._('Cannot generate report for %(name)s.\nMissing:\n- %(fields)s',
                        name=emp.name,
                        fields='\n- '.join(missing),
                    )
                )
        if error_message:
            raise UserError('\n\n'.join(error_message))
