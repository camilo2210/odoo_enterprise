# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class HrVersion(models.Model):
    _inherit = "hr.version"

    def _l10n_ae_get_labor_compliance_costs(self):
        self.ensure_one()
        return sum(
            float(self._get_property_input_value(code) or 0.0)
            for code in ("MEDICAL_INS", "WORK_PERMIT", "EMPLOYMENT_VISA")
        )

    def _get_benefits_costs(self):
        self.ensure_one()
        costs = super()._get_benefits_costs()
        ae_structure_type = self.env.ref("l10n_ae_hr_payroll.uae_employee_payroll_structure_type", raise_if_not_found=False)
        if self.structure_type_id != ae_structure_type:
            return costs
        return costs + self._l10n_ae_get_labor_compliance_costs()
