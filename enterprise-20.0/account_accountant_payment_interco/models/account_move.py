from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    inter_company_clearing_move_id = fields.Many2one(
        comodel_name='account.move',
        string="Inter Company Clearing Move",
        index='btree_not_null',
    )
