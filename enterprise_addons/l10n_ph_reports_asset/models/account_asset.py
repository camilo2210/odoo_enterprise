# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class AccountAsset(models.Model):
    _inherit = "account.asset"

    l10n_ph_fixed_asset_code = fields.Char(
        string="Fixed Asset Code",
        help="A unique reference for this fixed asset, used in the Fixed Assets Listing report.",
        copy=False,
    )

    _unique_l10n_ph_fixed_asset_code = models.UniqueIndex(
        "(l10n_ph_fixed_asset_code, company_id)",
        "The Fixed Asset Code must be unique per company!"
    )
