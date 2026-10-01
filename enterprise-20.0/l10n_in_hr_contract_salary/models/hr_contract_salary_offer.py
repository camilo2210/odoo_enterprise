from odoo import api, models
from odoo.tools import float_is_zero, float_round


class HrContractSalaryOffer(models.Model):
    _inherit = 'hr.contract.salary.offer'

    def _get_benefits(self, version):
        monthly_benefits, yearly_benefits = super()._get_benefits(version)
        dependents_selected, additional_cover_amount = self._l10n_in_get_medical_insurance_dependents(version)
        if not dependents_selected:
            return monthly_benefits, yearly_benefits

        difference = float_round(additional_cover_amount - dependents_selected, precision_digits=2)
        if float_is_zero(difference, precision_digits=2):
            return monthly_benefits, yearly_benefits

        monthly_benefits = float_round(monthly_benefits + difference, 2)
        yearly_benefits = float_round(yearly_benefits + (difference * 12.0), 2)
        return monthly_benefits, yearly_benefits

    @api.model
    def _l10n_in_get_medical_insurance_dependents(self, version):
        dependent_fields = (
            'l10n_in_insured_spouse',
            'l10n_in_insured_first_children',
            'l10n_in_insured_second_children',
        )
        dependents_selected = sum(version[field] for field in dependent_fields if version[field])
        if not dependents_selected:
            return 0, 0.0
        insured_total = float(version.l10n_in_medical_insurance_total or 0.0)
        insured_base = float(version.l10n_in_medical_insurance or 0.0)
        additional_cover_amount = insured_total - insured_base
        return dependents_selected, additional_cover_amount
