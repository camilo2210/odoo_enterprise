# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    allowed_work_entry_type_ids = fields.Many2many(related='company_id.allowed_work_entry_type_ids')
    l10n_tr_annual_work_entry_type_id = fields.Many2one(related="company_id.l10n_tr_annual_work_entry_type_id",
        readonly=False, domain="[('id', 'in', allowed_work_entry_type_ids)]")
    l10n_tr_sgk_workspace_registration_no = fields.Char(
        string='SGK Workspace Registration Number',
        related='company_id.l10n_tr_sgk_workspace_registration_no',
        readonly=False,
    )
    l10n_tr_sgk_workspace_intermediary_code = fields.Char(
        string='Intermediary Code',
        related='company_id.l10n_tr_sgk_intermediary_code',
        readonly=False,
    )
    l10n_tr_tax_reponsible_id = fields.Many2one(related="company_id.l10n_tr_tax_reponsible_id", readonly=False, check_company=True)
    l10n_tr_old_unit_code = fields.Selection(related="company_id.l10n_tr_old_unit_code", readonly=False)
    l10n_tr_new_unit_code = fields.Selection(related="company_id.l10n_tr_new_unit_code", readonly=False)
    l10n_tr_incentive_tier = fields.Selection(related="company_id.l10n_tr_incentive_tier", readonly=False)
