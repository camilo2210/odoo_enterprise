# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import models


_logger = logging.getLogger(__name__)

_WITHHOLDING_FIELD = 'f45_2063_roerendevoorheffing'

# Sources:
# - Technical Doc https://finances.belgium.be/fr/E-services/Belcotaxonweb/documentation-technique
# - "Avis aux débiteurs" https://finances.belgium.be/fr/entreprises/personnel_et_remuneration/avis_aux_debiteurs#q2


class L10n_Be281_45(models.Model):
    _name = 'l10n_be.281_45'
    _inherit = ['l10n_be.281.mixin']
    _description = 'HR Payroll 281.45 Wizard'

    def _get_declaration_code(self):
        return '281.45'

    def _get_eligible_employees(self, payslips):
        mapping_lines = self._get_mapping_lines(self.declaration_id.year)
        income_lines = mapping_lines.filtered(
            lambda mapping_line: mapping_line.tag != _WITHHOLDING_FIELD and (mapping_line.evaluation_type == 'salary_rule' or mapping_line.is_monetary)
        )
        line_codes = self._get_line_codes()
        all_line_values = payslips._get_line_values(line_codes, extra_domain=self._get_fiscal_line_domain())
        eligible_employees = self.env['hr.employee']
        for employee, slips in payslips.grouped('employee_id').items():
            line_values = {
                code: sum(all_line_values[code][payslip.id]['total'] for payslip in slips)
                for code in line_codes
            }
            if any(round(self._evaluate(mapping_line, line_values, {}), 2) for mapping_line in income_lines):
                eligible_employees |= employee
        return eligible_employees

    def _generate_employees_data(self, employee_payslips, all_line_values):
        res = super()._generate_employees_data(employee_payslips, all_line_values)
        res['sum_withholding'] = sum(
            sheet_values['f45_2063_roerendevoorheffing'] for sheet_values in res['employees_data']
        )
        return res

    def _get_pdf_report(self):
        return self.env.ref('l10n_be_hr_payroll.action_report_employee_281_45')

    def _get_pdf_filename(self, employee):
        self.ensure_one()
        return self.env._('%(year)s-%(employee)s-281_45', year=self.declaration_id.year, employee=employee.name)
