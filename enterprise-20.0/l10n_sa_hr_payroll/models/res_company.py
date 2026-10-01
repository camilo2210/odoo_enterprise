# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.constrains('l10n_sa_unpaid_leave_eos_threshold')
    def _check_unpaid_leave_eos_threshold(self):
        for record in self:
            if record.l10n_sa_unpaid_leave_eos_threshold < 0:
                raise ValidationError(self.env._("The Unpaid Leave EOS Threshold cannot be negative."))

    l10n_sa_mol_establishment_code = fields.Char(string="MoL Establishment ID")
    l10n_sa_bank_account_id = fields.Many2one("res.partner.bank", string="Establishment's Bank Account")
    l10n_sa_probation_period_duration = fields.Integer(help="Set the probation duration of the employee")
    l10n_sa_annual_work_entry_type_id = fields.Many2one("hr.work.entry.type",
        string="SA Annual Leave Time-off Type",
        domain="[('id', 'in', allowed_work_entry_type_ids)]",
        default=lambda self: self.env.ref("hr_work_entry.sa_work_entry_type_legal_leave", raise_if_not_found=False))
    l10n_sa_unpaid_leave_eos_threshold = fields.Integer(string="Unpaid Leave EOS Threshold", default=20)
