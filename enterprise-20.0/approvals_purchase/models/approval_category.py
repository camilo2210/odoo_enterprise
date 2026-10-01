# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ApprovalCategory(models.Model):
    _inherit = 'approval.category'

    create_rfq = fields.Boolean(string="Create RFQ's")

    @api.onchange('create_rfq')
    def _onchange_create_rfq(self):
        if self.create_rfq:
            self.has_product = 'required'
            self.has_quantity = 'required'
