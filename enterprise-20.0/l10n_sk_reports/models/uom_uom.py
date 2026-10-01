from odoo import fields, models


class UomUom(models.Model):
    _inherit = 'uom.uom'

    l10n_sk_vat_code = fields.Selection(
        selection=[
            ('kg', 'Kilograms'),
            ('t', 'Tons'),
            ('m', 'Meters'),
            ('ks', 'Pieces'),
        ],
        string="Slovak VAT Control Statement Unit",
        help="Reporting unit code (MJ) used by the Slovak VAT Control Statement export."
             "This field is set automatically via CSV data loading and is only for internal reporting use.",
        groups="base.group_system",
    )
