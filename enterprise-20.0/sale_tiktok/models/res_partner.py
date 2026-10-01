# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    tiktok_buyer_extern_id = fields.Char(string="TikTok Buyer ID", index="btree_not_null")
