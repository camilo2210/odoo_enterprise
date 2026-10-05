# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_ar_computable_tax_credit = fields.Selection(
        [('wo_prorate', 'Without Prorate'), ('global', 'Global')],
        string="Computable Tax Credit: Prorate Options",
        default='wo_prorate')

    l10n_ar_daily_book_start_entry_number = fields.Integer(
        string="Daily Book's Starting Entry Number",
        default=1,
        help="Entry number the next Daily Book export starts numbering from. "
             "It is updated after each export to keep the numbering continuous.",
    )

    def _l10n_ar_reports_get_daily_book_company(self):
        """ Return the company the Daily Book is filed under.
        A branch with the same CUIT as its parent files under that parent.
        A branch whose CUIT differs files under its own name.
        """
        self.ensure_one()
        for parent in self.sudo().parent_ids:
            if self in parent._get_branches_with_same_vat():
                return parent
        return self
