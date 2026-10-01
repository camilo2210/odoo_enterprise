# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Lazada Shop Creation Wizard.

Allows users to create Lazada shops by entering API credentials and authorizing
the connection with Lazada.
"""

from odoo import fields, models


class LazadaShopCreateWizard(models.TransientModel):
    _name = "lazada.shop.create.wizard"
    _description = "Lazada Shop Creation Wizard"

    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company, required=True
    )
    app_key = fields.Char(
        help="Your Lazada application key (App Key). You can find this in your Lazada "
        "Service Provider Center after creating an application. Enter this before "
        "authorizing the connection.",
        required=True,
    )
    app_secret = fields.Char(
        help="Your Lazada application secret (App Secret). This is provided alongside your "
        "App Key in the Lazada Service Provider Center. Keep this confidential "
        "and enter it before authorizing the connection.",
        required=True,
    )

    def action_create_shop(self):
        """Create a shop using the given credentials and redirect to Lazada authorization page."""
        self.ensure_one()
        shop = self.env["lazada.shop"].create({
            "name": self.env._("New Lazada Shop"),
            "app_key": self.app_key,
            "app_secret": self.app_secret,
            "company_id": self.company_id.id,
        })

        # Redirect to authorization flow
        return shop.action_open_auth_link()
