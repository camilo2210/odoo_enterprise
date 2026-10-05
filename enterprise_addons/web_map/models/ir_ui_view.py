# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class IrUiView(models.Model):
    _inherit = 'ir.ui.view'

    type = fields.Selection(selection_add=[('map', "Map")])

    def _is_qweb_based_view(self, view_type):
        return view_type == "map" or super()._is_qweb_based_view(view_type)

    def _get_view_info(self):
        return {'map': {'icon': 'location_on'}} | super()._get_view_info()
