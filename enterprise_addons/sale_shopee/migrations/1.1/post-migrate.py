from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # New records in noupdate data are created on upgrade, but the
    # _configure_for_shopee function tag is skipped in that case.
    xmlids = (
        'sale_shopee.default_adjustment_product',
        'sale_shopee.default_discount_product',
    )
    default_products = [env.ref(xmlid, raise_if_not_found=False) for xmlid in xmlids]
    products = env['product.product'].browse([product.id for product in default_products if product])
    if products:
        products._configure_for_shopee()
