# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_be_mobility_expense_category_ids = fields.Many2many(
        related="company_id.l10n_be_mobility_expense_category_ids",
        readonly=False,
        string="Mobility Expense Categories",
    )
