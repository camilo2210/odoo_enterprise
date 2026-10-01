from odoo import fields, models


class AccountTax(models.Model):
    _inherit = 'account.tax'

    l10n_do_edi_invoicing_indicator = fields.Selection(
        string="Invoicing Indicator",
        selection=[
            ('0', 'Non-billable'),
            ('1', 'ITBIS 1 (18%)'),
            ('2', 'ITBIS 2 (16%)'),
            ('3', 'ITBIS 3 (0%)'),
            ('4', 'Exempt (E)'),
            ('5', 'ITBIS Witholding'),
            ('6', 'ISR Witholding'),
            ('7', 'Additional Taxes'),
        ],
    )
    l10n_do_edi_additional_tax_code = fields.Char('Additional Tax Code')
