from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_mx_isr_calculation_method = fields.Selection(
        related='company_id.l10n_mx_isr_calculation_method', readonly=False)
    l10n_mx_isr_days_per_month = fields.Float(
        related='company_id.l10n_mx_isr_days_per_month', readonly=False)
