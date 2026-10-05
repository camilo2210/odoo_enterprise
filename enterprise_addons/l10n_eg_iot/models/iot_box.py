from odoo import fields, models


class IotBox(models.Model):
    _inherit = "iot.box"

    l10n_eg_proxy_token = fields.Char("Proxy Token", readonly=True)
