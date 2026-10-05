# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_ae_employer_code = fields.Char(related="company_id.l10n_ae_employer_code", readonly=False)
    company_partner_id = fields.Many2one(related="company_id.partner_id")
    l10n_ae_bank_account_id = fields.Many2one(related="company_id.l10n_ae_bank_account_id", readonly=False)
    l10n_ae_is_private_sector = fields.Boolean(related="company_id.l10n_ae_is_private_sector", readonly=False)
    l10n_ae_probation_period_duration = fields.Integer(related="company_id.l10n_ae_probation_period_duration", readonly=False, help="Set the probation duration of the employee")
    allowed_work_entry_type_ids = fields.Many2many(related='company_id.allowed_work_entry_type_ids')
    l10n_ae_annual_work_entry_type_id = fields.Many2one(related="company_id.l10n_ae_annual_work_entry_type_id", string="Annual Leave Type",
        readonly=False, domain="[('id', 'in', allowed_work_entry_type_ids)]")
