from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_kw_annual_work_entry_type_id = fields.Many2one(
        related='company_id.l10n_kw_annual_work_entry_type_id',
        readonly=False,
    )
