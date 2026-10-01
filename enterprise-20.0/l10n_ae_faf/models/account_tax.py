from odoo import fields, models


class AccountTax(models.Model):
    _inherit = 'account.tax'

    l10n_ae_tax_code = fields.Selection(
        string="FTA Tax Code",
        selection=[
            ('SR', 'SR - Standard-rated'),
            ('ZR', 'ZR - Zero-rated'),
            ('EX', 'EX - Exempt'),
            ('IG', 'IG - Intra GCC'),
            ('OA', 'OA - Amendments to Output Tax'),
            ('IA', 'IA - Amendments to Input Tax'),
            ('RC', 'RC - Reverse Charge'),
            ('T', 'T - Excise Taxable'),
            ('D', 'D - Excise Deductible'),
        ],
    )
