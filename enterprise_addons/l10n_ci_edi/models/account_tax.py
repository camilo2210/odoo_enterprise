from odoo import fields, models


class AccountTax(models.Model):
    _inherit = 'account.tax'

    l10n_ci_edi_tax_code = fields.Selection(
        selection=[
            ('TVA', "TVA (18%)"),
            ('TVAB', "Reduced TVA (9%)"),
            ('TVAC', "TVA exempt by convention"),
            ('TVAD', "TVA exempt by law"),
        ],
        string="FNE Tax Code",
        help="Tax code used when reporting this tax to the FNE system. "
             "Taxes without a code are sent to the FNE as custom taxes.",
    )
