# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrWorkEntryType(models.Model):
    _inherit = 'hr.work.entry.type'

    l10n_ch_swissdec_payroll_impact = fields.Boolean("Impacts Swiss Payroll", default=False, tracking=True)
    l10n_ch_swissdec_work_interruption = fields.Boolean("Work Interruption", default=False, tracking=True)

    @api.model
    def _get_critical_fields(self):
        return super()._get_critical_fields() + ['l10n_ch_swissdec_payroll_impact', 'l10n_ch_swissdec_work_interruption']

    def _get_data_files_to_update(self):
        # Note: file order should be maintained
        return super()._get_data_files_to_update() + [(
            'l10n_ch_hr_payroll', [
                'data/hr_swiss_work_entry_types.xml',
            ])]
