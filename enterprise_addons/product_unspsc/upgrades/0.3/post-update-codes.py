from odoo.addons.product_unspsc.hooks import _insert_missing_unspsc_codes


def migrate(cr, version):
    _insert_missing_unspsc_codes(cr)
