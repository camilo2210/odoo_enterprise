from odoo import fields, models


class AccountAsset(models.Model):
    _inherit = 'account.asset'

    l10n_in_value_residual = fields.Monetary(related='current_selected_variant_id.l10n_in_value_residual')
