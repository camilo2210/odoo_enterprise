# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class AccountTax(models.Model):
    _inherit = 'account.tax'

    l10n_bg_saft_tax_code = fields.Char(
        string='Bulgarian SAF-T Tax Code',
        help=('A 6-digit number that pricisely identifies a tax code in the '
            'Bulgarian SAF-T report, the first 3 digits identify the tax type.'),
    )
