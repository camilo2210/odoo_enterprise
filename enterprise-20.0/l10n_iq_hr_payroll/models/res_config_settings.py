from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_iq_is_oil_and_gas_company = fields.Boolean(related="company_id.l10n_iq_is_oil_and_gas_company", readonly=False)
    l10n_iq_annual_work_entry_type_id = fields.Many2one(related="company_id.l10n_iq_annual_work_entry_type_id",
        readonly=False)
