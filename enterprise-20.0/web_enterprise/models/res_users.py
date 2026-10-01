# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    color_scheme = fields.Selection(related="res_users_settings_id.color_scheme", readonly=False, user_writeable=True)
