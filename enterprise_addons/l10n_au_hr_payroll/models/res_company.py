# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_au_branch_code = fields.Char(
        string="Branch Code",
        help="The branch code of the company, if any.")
    l10n_au_wpn_number = fields.Char(
        string="Withholding Payer Number",
        help="Number given to individuals / enterprises that have PAYGW obligations but don't have an ABN.")
    l10n_au_registered_for_whm = fields.Boolean("Registered for Working Holiday Maker")
    l10n_au_registered_for_palm = fields.Boolean("Registered for PALM Scheme")

    l10n_au_previous_bms_id = fields.Char("Previous BMS ID",
        help="The previous Business Management Software ID is a unique ID provided by your previous STP-compliant payroll software.")
    l10n_au_bms_id = fields.Char("BMS ID", readonly=False,
        help="Odoo's generated Business Management Software ID used as a unique ATO identifier for your company.")

    def _prepare_resource_calendar_values(self):
        """
        Override to set the default calendar to
        38 hours/week for Australian companies
        """
        vals = super()._prepare_resource_calendar_values()
        if self.country_id.code == 'AU':
            vals.update({
                'name': _('38 hours/week - %s', self.name),
                'full_time_required_hours': 38.0,
                'attendance_ids': [
                    (0, 0, {'dayofweek': '0', 'duration_hours': 7.6, 'hour_from': 0, 'hour_to': 0}),
                    (0, 0, {'dayofweek': '1', 'duration_hours': 7.6, 'hour_from': 0, 'hour_to': 0}),
                    (0, 0, {'dayofweek': '2', 'duration_hours': 7.6, 'hour_from': 0, 'hour_to': 0}),
                    (0, 0, {'dayofweek': '3', 'duration_hours': 7.6, 'hour_from': 0, 'hour_to': 0}),
                    (0, 0, {'dayofweek': '4', 'duration_hours': 7.6, 'hour_from': 0, 'hour_to': 0}),
                ],
            })
        return vals
