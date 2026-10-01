# Part of Odoo. See LICENSE file for full copyright and licensing details.

# Mapping of standard shop classes to their compact AI preview equivalents
_AI_PREVIEW_CONVERSIONS = {
    'o_wsale_products_opt_layout_list': 'o_wsale_products_opt_layout_catalog',
    'o_wsale_products_opt_design_showcase': 'o_wsale_products_opt_design_cards',
    'o_wsale_products_opt_design_condensed': 'o_wsale_products_opt_design_cards',
    'o_wsale_products_opt_design_list_large': 'o_wsale_products_opt_design_cards',
}


def adapt_shop_design_classes_for_ai_preview(design_classes):
    """
    Replace list-style CSS classes into catalog/card-style classes
    optimized for compact AI previews.
    """
    if not design_classes:
        return ""

    return " ".join(
        _AI_PREVIEW_CONVERSIONS.get(cls, cls)
        for cls in design_classes.split()
    )
