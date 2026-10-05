# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    l10n_tr_invoice_currency_rate_type = fields.Selection(
        selection=[("sell", "Selling"), ("buy", "Buying")],
        string="Invoice/Credit Note",
        help="Exchange rate type defaulted on this partner's invoices and credit notes. "
        "Leave empty to use the regular per-document default.",
    )
    l10n_tr_bill_currency_rate_type = fields.Selection(
        selection=[("sell", "Selling"), ("buy", "Buying")],
        string="Bill/Refund",
        help="Exchange rate type defaulted on this partner's vendor bills and refunds. "
        "Leave empty to use the regular per-document default.",
    )
