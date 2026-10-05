from odoo import fields, models


# Avalara `code` -> Odoo uom.uom xml id, used to auto-fill `value_float` from
# `product.weight` / `product.volume`. Only mass and volume UOMs are used in
# those fields.
AVATAX_CODE_TO_ODOO_UOM = {
    # Mass
    'Kilogram': 'uom.product_uom_kgm',
    'Gram': 'uom.product_uom_gram',
    'Megagram': 'uom.product_uom_ton',
    'Pound': 'uom.product_uom_lb',
    'Ounce': 'uom.product_uom_oz',
    # Volume
    'Millilitre': 'uom.product_uom_milliliter',
    'Litre': 'uom.product_uom_litre',
    'CubicMetre': 'uom.product_uom_cubic_meter',
    'CubicInch': 'uom.product_uom_cubic_inch',
    'CubicFoot': 'uom.product_uom_cubic_foot',
    'Gallon, U.S. Liquid': 'uom.product_uom_gal',
    'gallon (US fluid)': 'uom.product_uom_gal',
    'quart (US fluid)': 'uom.product_uom_qt',
    'ounce (fluid US customary)': 'uom.product_uom_floz',
}


class AvataxUom(models.Model):
    _name = 'avatax.uom'
    _description = "Avatax Unit of Measurement"

    name = fields.Char(required=True, readonly=True)
    code = fields.Char(required=True, readonly=True)
    measurement_type = fields.Char(readonly=True)
    company_id = fields.Many2one('res.company', required=True, readonly=True)

    _code_company_uniq = models.Constraint(
        'UNIQUE (code, company_id)',
        "The unit of measurement already exists for this company.",
    )

    def _get_odoo_uom(self):
        self.ensure_one()
        if ref := AVATAX_CODE_TO_ODOO_UOM.get(self.code):
            return self.env.ref(ref, raise_if_not_found=False) or self.env['uom.uom']

        return self.env['uom.uom']
