# Part of Odoo. See LICENSE file for full copyright and licensing details.

import uuid
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError


class L10nBeFlexiAtWork(models.Model):
    _name = 'l10n.be.flexi.at.work'
    _inherit = 'l10n.be.onss.batch.declaration'
    _description = 'Flexi@Work Declaration'

    name = fields.Char(default=lambda self: str(uuid.uuid4()), readonly=True, required=True)
    operation_type = fields.Selection(
        selection=[
            ('0', 'Submission'),
            ('1', 'Modification'),
            ('3', 'Cancellation'),
        ],
        required=True,
        default='0',
    )
    payslip_id = fields.Many2one('hr.payslip', required=True, index=True,
        domain="[('state', 'in', ['validated', 'paid']), ('l10n_be_needs_flxwage_declaration', '=', True), ('l10n_be_flexi_declaration_id', '=', False)]")

    # Related fields
    company_id = fields.Many2one(related='payslip_id.company_id', default=None, readonly=True, index="btree")
    employee_id = fields.Many2one(related='payslip_id.employee_id', store=True, readonly=True, index="btree")
    version_id = fields.Many2one(related='payslip_id.version_id', store=True, readonly=True, index="btree")

    _payslip_uniq = models.Constraint(
        'unique (payslip_id)',
        'A Flexi@Work declaration already exists for this payslip.',
    )

    _name_uniq = models.Constraint(
        'unique (name)',
        'The reference field must be unique.',
    )

    @api.constrains('payslip_id')
    def _check_payslip_done(self):
        for declaration in self:
            if declaration.payslip_id.state not in ('validated', 'paid'):
                raise UserError(self.env._('The payslip must be validated to create a Flexi@Work declaration.'))

    @api.constrains('version_id')
    def _check_valid_flexi_worker(self):
        if not all(self.version_id.mapped('l10n_be_needs_flxwage_declaration')):
            raise UserError(self.env._('The payslip must be linked to a valid flexi contract (worker code 050 or 450).'))

    def _get_declaration_type(self):
        return 'FLEX'

    def _get_base_schema_url(self):
        return 'https://www.socialsecurity.be/docu_xml/flxwage/'

    def _get_base_schema_filename(self):
        return 'FLXWAGE_'

    def _get_declaration_template_xmlid(self):
        return 'l10n_be_hr_payroll.flxwage_xml_report'

    def _get_rendering_data(self):
        self.ensure_one()

        # Preliminary checks
        if not self.employee_id._is_niss_valid():
            raise UserError(self.env._('Invalid NISS number for employee %s.', self.employee_id.name))

        relation = {
            "relation_type": 1,
            "reference": {
                "type": 10,
                "origin": 8,
                "value": self.name,
            },
        }

        if self.operation_type != '3':
            financial_elements = []
            remuneration, bonus = self.payslip_id._get_flxwage_amounts()
            if bonus:
                financial_elements.append({
                    "code": "0002001000",
                    "value": round(bonus * 100),
                })
            if remuneration:
                financial_elements.append({
                    "code": "0001001000",
                    "value": round(remuneration * 100),
                })

            relation["calculation"] = {
                "start_date": self.payslip_id.date_from,
                "end_date": self.payslip_id.date_to,
                "calculation_date": self.payslip_id.compute_date,
                "caracteristic": {
                    "start_date": self.payslip_id.date_from,
                    "end_date": self.payslip_id.date_to,
                    "employer_category": self.version_id.l10n_be_employer_category_id.dmfa_code,
                    "worker_code": self.version_id.l10n_be_worker_code_id.dmfa_code,
                    "financial_elements": financial_elements,
                },
            }

        target_date = date.today() - relativedelta(months=3)
        target_quarter = (target_date.month - 1) // 3 + 1
        current_year_quarter = '%s%s' % (target_date.year, target_quarter)

        payroll_config = self.company_id._get_payroll_config(self.payslip_id.date_from)
        return {
            "attestation_status": int(self.operation_type),
            "debtor": {
                "onss": payroll_config.onss_registration_number,
                "id": payroll_config.l10n_be_company_number,
                "beneficiaries": [{
                    "niss": self.employee_id.niss,
                    "relations": [relation],
                }],
            },
            "schema_year_quarter": current_year_quarter,
        }

    def _pre_submit_checks(self):
        errors = super()._pre_submit_checks()
        if self.environment == 'S':
            errors.append(self.env._("FLEX declarations are only permitted in Production (R) and Circuit Test (T) environments."))
        return errors
