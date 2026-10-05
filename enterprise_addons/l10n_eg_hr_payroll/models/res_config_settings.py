from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    allowed_work_entry_type_ids = fields.Many2many(related='company_id.allowed_work_entry_type_ids')
    l10n_eg_annual_work_entry_type_id = fields.Many2one(related="company_id.l10n_eg_annual_work_entry_type_id",
        readonly=False, domain="[('id', 'in', allowed_work_entry_type_ids)]"
    )
    l10n_eg_nosi_code = fields.Char(string='Company NOSI Code', related='company_id.l10n_eg_nosi_code', readonly=False)
