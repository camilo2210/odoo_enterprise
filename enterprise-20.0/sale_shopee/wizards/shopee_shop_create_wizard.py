# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.fields import Domain


class ShopeeShopCreateWizard(models.TransientModel):
    _name = "shopee.shop.create"
    _description = "Create Shopee Shop Wizard"

    account_id = fields.Many2one(
        string="Shopee Account",
        help="The Shopee account on which the new shop is authorized.",
        comodel_name="shopee.account",
        required=True,
        default=lambda self: self.env["shopee.account"].search(self._get_shopee_account_domain(), limit=1),
        domain=lambda self: self._get_shopee_account_domain(),
    )

    def _get_shopee_account_domain(self):
        return Domain.OR([Domain([("company_ids", "in", self.env.company.ids)]), Domain([("company_ids", "=", False)])])

    def action_authorize_shop(self):
        """Redirect the user to Shopee to authorize a new shop on the selected account.

        :return: An action to open the Shopee authorization page.
        :rtype: dict
        """
        self.ensure_one()
        return self.account_id.action_open_auth_link()

    def action_view_accounts(self):
        """Open the list of the existing Shopee accounts.

        :return: An action to open the Shopee accounts.
        :rtype: dict
        """
        return self.env["ir.actions.act_window"]._for_xml_id(
            "sale_shopee.action_shopee_account_list",
        )

    def action_create_account(self):
        """Open the creation of a new Shopee account.

        :return: An action to create a Shopee account.
        :rtype: dict
        """
        return self.env["ir.actions.act_window"]._for_xml_id(
            "sale_shopee.quick_create_account_action",
        )
