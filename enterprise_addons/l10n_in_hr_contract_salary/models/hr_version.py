from odoo import models


class HrVersion(models.Model):
    _inherit = 'hr.version'

    def _inverse_final_yearly_costs(self):
        indian_versions = self.filtered(
            lambda v: v.company_id.country_id.code == 'IN' and self.env.context.get('salary_simulation')
        )
        indian_versions._compute_final_yearly_costs()
        non_indian_versions = self - indian_versions
        if non_indian_versions:
            super(HrVersion, non_indian_versions)._inverse_final_yearly_costs()

    def _generate_salary_simulation_payslip(self):
        return super(HrVersion, self.with_context(calculate_tds=False))._generate_salary_simulation_payslip()
