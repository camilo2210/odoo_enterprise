# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.exceptions import UserError
from odoo.addons.pos_self_order.controllers.orders import PosSelfOrderController

class PosSelfOrderPreparationDisplayController(PosSelfOrderController):
    @http.route()
    def change_printer_status(self, access_token, has_paper):
        super().change_printer_status(access_token, has_paper)
        pos_config = self._verify_pos_config(access_token)
        pos_config.env['pos.prep.display']._paper_status_change(pos_config)

    @http.route()
    def remove_order(self, access_token, order_id, order_access_token):
        pos_config = self._verify_pos_config(access_token)
        pos_order = pos_config.env['pos.order'].browse(order_id)
        if not pos_order.can_be_cancelled():
            raise UserError(_("This order cannot be cancelled because it's already in preparation."))
        super().remove_order(access_token, order_id, order_access_token)
