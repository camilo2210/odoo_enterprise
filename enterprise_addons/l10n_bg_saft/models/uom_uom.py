# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class UomUom(models.Model):
    _inherit = "uom.uom"

    l10n_bg_saft_uom_code = fields.Char(
        string="Unit Code (Bg SAF-T)",
        help="Code of the Unit of Measure used in the the Bulgarian SAF-T report",
    )
    l10n_bg_saft_uom_description = fields.Char(
        string="Unit Description (Bg SAF-T)",
        help="Description of the Unit of Measure used in the the Bulgarian SAF-T report",
    )
    l10n_bg_saft_uom_conversion_factor = fields.Float(
        'Conversion Factor to the Bulgarian SAF-T UoM',
        required=True,
        default=1,
    )

    _l10n_bg_saft_uom_conversion_factor_gt_zero = models.Constraint(
        'CHECK (l10n_bg_saft_uom_conversion_factor!=0)',
        'The conversion ratio for a Bg SAF-T Unit of Measure cannot be 0!',
    )
