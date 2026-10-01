# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    l10n_br_goods_operation_type_id = fields.Many2one(
        "l10n_br.operation.type",
        copy=False,
        string="Override Operation Type",
        help="Brazil: If an Operation Type is selected, it will be applied to the product in the line, "
            "determining the CFOP for that line. If no selection is made, the operation type will be inherited from the header."
    )
    l10n_br_item_number = fields.Char(
        string="Item Number",
        help="Brazil: Used for B2B control process, it references the number of this item within the purchase order",
        copy=False,
    )
    # The purpose of this field is to map the customer's sale order number on the NF-e, so we need this field on the line instead of move.
    # As we might have combined invoice of multiple sale orders. In that case each invoice line can have different sale order number.
    l10n_br_order_number = fields.Char(
        string="xPed Number",
        help="This field can be used to enter the customer internal purchase number. It creates a tracking register that links the Seller's NF-e number with the real Buyer's Purchase Order Number.",
        copy=False,
    )
