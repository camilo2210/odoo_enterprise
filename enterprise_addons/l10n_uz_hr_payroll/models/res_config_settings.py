# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_uz_social_tax_category = fields.Selection(related="company_id.l10n_uz_social_tax_category", readonly=False)
    l10n_uz_annual_leave_work_entry_type_id = fields.Many2one(related="company_id.l10n_uz_annual_leave_work_entry_type_id", readonly=False)
