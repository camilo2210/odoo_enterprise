from odoo import models, fields


class PosPayment(models.Model):
    _inherit = "pos.payment"

    tyro_merchant_receipt = fields.Json(string="Tyro Merchant Receipt")
