# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_be_mobility_expense_category_ids = fields.Many2many(
        "product.product",
        "company_mobility_expense_category_rel",
        "company_id",
        "product_id",
        string="Expense Mobility Categories",
        domain=[("can_be_expensed", "=", True)],
        help="Any Expense of those categories will be reimbursed with Mobility Budget.",
    )
