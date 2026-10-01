# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, api


class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def _load_pos_preparation_data_fields(self):
        res = super()._load_pos_preparation_data_fields()
        return res + ['table_stand_number']

    def can_be_cancelled(self):
        self.ensure_one()
        prep_orders = self.env['pos.prep.order'].search([('pos_order_id', '=', self.id)])
        if prep_orders:
            return not prep_orders.prep_line_ids.prep_display_ids
        return True
