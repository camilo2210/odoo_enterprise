# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class AccountAccount(models.Model):
    _inherit = 'account.account'

    l10n_co_exogenous_config_ids = fields.Many2many(
        comodel_name="l10n_co.exogenous.config",
        relation="account_account_exogenous_config",
    )
