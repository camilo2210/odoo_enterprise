# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, _
from odoo.exceptions import UserError


class HrRuleParameter(models.Model):
    _inherit = 'hr.rule.parameter'

    @api.model
    def _get_parameter_from_code(self, code, date=None, raise_if_not_found=True):
        try:
            return super()._get_parameter_from_code(code, date=date, raise_if_not_found=raise_if_not_found)
        except UserError as e:
            if code.startswith('l10n_ch_withholding_tax_rates_'):
                raise UserError(_("No tax rates found for the employee canton. Make sure you've actually imported using the wizard under Configuration -> Swiss -> Import Tax Rates")) from e
            raise

    def _set_all_external_identifiers_noupdate(self, noupdate):
        # Do not flag in noupdate for swissdec
        if self.country_id.code != 'CH':
            super()._set_all_external_identifiers_noupdate(noupdate)
