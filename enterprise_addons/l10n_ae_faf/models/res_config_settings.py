from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_ae_tax_agency = fields.Many2one(related='company_id.l10n_ae_tax_agency', readonly=False)
    l10n_ae_tax_agent = fields.Many2one(related='company_id.l10n_ae_tax_agent', readonly=False)
