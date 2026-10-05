# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class HrWorkEntryType(models.Model):
    _inherit = 'hr.work.entry.type'

    def _get_data_files_to_update(self):
        # Note: file order should be maintained
        return super()._get_data_files_to_update() + [(
            'l10n_ke_hr_payroll', [
                'data/hr_work_entry_type_data.xml',
            ])]
