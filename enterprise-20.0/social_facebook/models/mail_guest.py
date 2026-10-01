# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class MailGuest(models.Model):
    _inherit = "mail.guest"

    meta_user_id = fields.Char("Meta User Identifier", index="btree_not_null")
