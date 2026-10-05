# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrWorkEntryType(models.Model):
    _inherit = 'hr.work.entry.type'

    l10n_hk_use_713 = fields.Boolean("ADW Calculation", tracking=True,
        help="Calculates the employee's pay according to the Average Daily Wage (ADW) rules under Hong Kong employment regulations.")
    l10n_hk_consecutive_days_limit_type = fields.Selection(
        selection=[
            ("from", "From"),
            ("to", "Up To"),
        ],
        string='Validity',
        tracking=True,
        help="Set these values in order to filter disallow this leave type if the amount of consecutive leave day doesn't match the filter.",
    )
    l10n_hk_consecutive_days_limit = fields.Integer(tracking=True)

    @api.model
    def _get_critical_fields(self):
        return super()._get_critical_fields() + ['l10n_hk_use_713', 'l10n_hk_consecutive_days_limit_type', 'l10n_hk_consecutive_days_limit']

    def _get_data_files_to_update(self):
        # Note: file order should be maintained
        return super()._get_data_files_to_update() + [(
            'l10n_hk_hr_payroll', [
                'data/hr_work_entry_type_data.xml',
            ])]
