# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrWorkEntryType(models.Model):
    _inherit = "hr.work.entry.type"

    l10n_us_show_on_payslip = fields.Boolean(string="Show On Payslip", default=True, tracking=True)

    @api.model
    def _get_critical_fields(self):
        return super()._get_critical_fields() + ['l10n_us_show_on_payslip']

    def _get_data_files_to_update(self):
        # Note: file order should be maintained
        return super()._get_data_files_to_update() + [(
            'l10n_us_hr_payroll', [
                'data/hr_work_entry_type_data.xml',
            ])]
