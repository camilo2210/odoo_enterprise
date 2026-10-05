# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class PosOrderReceipt(models.AbstractModel):
    _inherit = 'pos.order.receipt'
    _description = 'Point of Sale Order Receipt Generator'

    def _self_order_preparation_lang(self):
        """
        Preparation tickets of self orders are generated from the backend, outside of any
        user request, so the context carries no language and everything is printed in
        en_US. `with_user` doesn't help: it swaps the user but keeps the context as is.
        The ticket is printed on behalf of the self ordering user, so use its language.
        """
        self.ensure_one()
        if self.source not in ['mobile', 'kiosk']:
            return False

        lang = self.config_id.self_ordering_default_user_id.lang
        return lang if lang and lang != self.env.context.get('lang') else False

    def _order_change_receipts_generate_html(self):
        # The QWeb template is rendered with the env language, so it must be set here too
        # and not only in _order_change_receipt_generate_data.
        lang = self._self_order_preparation_lang()
        if not lang:
            return super()._order_change_receipts_generate_html()

        self_user = self.config_id.self_ordering_default_user_id
        return self.with_user(self_user) \
            .sudo() \
            .with_context(lang=lang) \
            ._order_change_receipts_generate_html()
