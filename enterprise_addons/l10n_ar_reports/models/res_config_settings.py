# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_ar_computable_tax_credit = fields.Selection(related='company_id.l10n_ar_computable_tax_credit', readonly=False)
    l10n_ar_daily_book_start_entry_number = fields.Integer(related='company_id.l10n_ar_daily_book_start_entry_number', readonly=False)
    l10n_ar_daily_book_files_under_parent = fields.Boolean(compute='_compute_l10n_ar_daily_book_files_under_parent')

    @api.depends('company_id')
    def _compute_l10n_ar_daily_book_files_under_parent(self):
        for settings in self:
            company = settings.company_id
            settings.l10n_ar_daily_book_files_under_parent = company._l10n_ar_reports_get_daily_book_company() != company
