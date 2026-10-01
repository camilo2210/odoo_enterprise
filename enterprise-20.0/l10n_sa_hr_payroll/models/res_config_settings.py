from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_sa_mol_establishment_code = fields.Char(related="company_id.l10n_sa_mol_establishment_code", readonly=False)
    l10n_sa_bank_account_id = fields.Many2one(related="company_id.l10n_sa_bank_account_id", readonly=False)
    l10n_sa_bank_establishment_code = fields.Char(related="l10n_sa_bank_account_id.l10n_sa_bank_establishment_code", readonly=False)
    l10n_sa_sarie_code = fields.Char(compute='_compute_l10n_sa_sarie_code')
    company_partner_id = fields.Many2one(related="company_id.partner_id")
    l10n_sa_probation_period_duration = fields.Integer(related="company_id.l10n_sa_probation_period_duration", readonly=False, help="Set the probation duration of the employee")
    allowed_work_entry_type_ids = fields.Many2many(related='company_id.allowed_work_entry_type_ids')
    l10n_sa_annual_work_entry_type_id = fields.Many2one(related="company_id.l10n_sa_annual_work_entry_type_id",
        readonly=False, domain="[('id', 'in', allowed_work_entry_type_ids)]")
    l10n_sa_unpaid_leave_eos_threshold = fields.Integer(related="company_id.l10n_sa_unpaid_leave_eos_threshold", readonly=False)

    def _compute_l10n_sa_sarie_code(self):
        for record in self:
            record.l10n_sa_sarie_code = record.l10n_sa_bank_account_id._get_clearing_number('SA')
