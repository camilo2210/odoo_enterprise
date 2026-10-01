from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    ai_esg_to_assign_emission_factor_cron = fields.Boolean(copy=False)
