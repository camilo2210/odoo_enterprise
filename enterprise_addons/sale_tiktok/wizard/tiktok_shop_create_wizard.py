# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class TikTokShopCreateWizard(models.TransientModel):
    _name = "tiktok.shop.create.wizard"
    _description = "TikTok Shop Creation Wizard"

    app_key = fields.Char(
        string="App key",
        help="Your TikTok application key. You can find this in your TikTok "
        "Shop Partner Center → Apps/Service after creating an application. Enter this before "
        "authorizing the connection.",
        required=True,
    )
    app_secret = fields.Char(
        string="App secret",
        help="Your TikTok application secret. This is provided alongside your "
        "App Key in the TikTok Shop Partner Center → Apps/Service. Keep this confidential "
        "and enter it before authorizing the connection.",
        required=True,
    )
    service_extern_id = fields.Char(
        string="Service ID",
        help="Your TikTok service ID. You can find this in your TikTok "
        "Shop Partner Center → Apps/Service at the top of the page called ID. Enter this before "
        "authorizing the connection.",
        required=True,
    )

    def action_create_shop(self):
        self.ensure_one()
        shop = self.env["tiktok.shop"].create({
            "app_key": self.app_key,
            "app_secret": self.app_secret,
            "service_extern_id": self.service_extern_id,
            "name": self.env._("(Pending Authorization)"),
        })
        return shop.action_open_auth_link()
