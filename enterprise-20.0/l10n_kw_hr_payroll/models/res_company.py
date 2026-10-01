from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_kw_annual_work_entry_type_id = fields.Many2one(
        'hr.work.entry.type',
        string="KW Annual Leave Time-off Type",
        default=lambda self: self.env.ref("hr_work_entry.l10n_kw_work_entry_type_paid_time_off", raise_if_not_found=False)
    )
