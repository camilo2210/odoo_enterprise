# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class AccountAccount(models.Model):
    _inherit = 'account.account'

    l10n_bg_saft_account_code = fields.Char(
        string="Account Code (Bg SAF-T)",
        help="Account Code used in the Bulgarian SAF-T Report",
        size=6,
    )
