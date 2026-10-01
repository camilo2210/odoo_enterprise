from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_om_annual_work_entry_type_id = fields.Many2one(
        related="company_id.l10n_om_annual_work_entry_type_id",
        readonly=False)
    l10n_om_salary_payer = fields.Many2one(
        related="company_id.l10n_om_salary_payer",
        domain="[('country_id.code', '=', 'OM')]",
        readonly=False)
    l10n_om_company_mol_number = fields.Char(
        related="company_id.l10n_om_company_mol_number",
        readonly=False)
    l10n_om_salary_payer_mol_number = fields.Char(
        related="company_id.l10n_om_salary_payer_mol_number",
        readonly=False)
    l10n_om_bank_account_id = fields.Many2one(
        related="company_id.l10n_om_bank_account_id",
        domain="[('partner_id', '=', l10n_om_salary_payer)]",
        readonly=False)
