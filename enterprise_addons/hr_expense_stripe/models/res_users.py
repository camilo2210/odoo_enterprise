from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    stripe_card_ids = fields.One2many(
        comodel_name='hr.expense.stripe.card',
        inverse_name='user_id',
        groups='base.group_user',
        check_company=True,
    )
