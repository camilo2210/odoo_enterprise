from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    l10n_in_pan_entity_id = fields.Many2one(related='partner_id.l10n_in_pan_entity_id', string="PAN Entity")
