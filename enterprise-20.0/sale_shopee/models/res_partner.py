# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    shopee_buyer_identifier = fields.Char("Shopee Buyer ID")
