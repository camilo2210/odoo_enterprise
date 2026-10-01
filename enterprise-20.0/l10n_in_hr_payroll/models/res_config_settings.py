# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_in_deductor_tan = fields.Char(related='company_id.l10n_in_deductor_tan', readonly=False)
    l10n_in_deductor_pan = fields.Char(related='company_id.l10n_in_deductor_pan', readonly=False)
    l10n_in_deductor_type = fields.Selection(related='company_id.l10n_in_deductor_type', readonly=False)
    l10n_in_responsible_person_id = fields.Many2one(related='company_id.l10n_in_responsible_person_id', readonly=False)
    l10n_in_epf_employer_id = fields.Char(related='company_id.l10n_in_epf_employer_id', readonly=False)
    l10n_in_esic_ip_number = fields.Char(related='company_id.l10n_in_esic_ip_number', readonly=False)
    l10n_in_pt_number = fields.Char(related='company_id.l10n_in_pt_number', readonly=False)
    l10n_in_provident_fund = fields.Boolean(related='company_id.l10n_in_provident_fund', readonly=False)
    l10n_in_pt = fields.Boolean(related='company_id.l10n_in_pt', readonly=False)
    l10n_in_esic = fields.Boolean(related='company_id.l10n_in_esic', readonly=False)
    l10n_in_labour_welfare = fields.Boolean(related='company_id.l10n_in_labour_welfare', readonly=False)
    l10n_in_labour_identification_number = fields.Char(related='company_id.l10n_in_labour_identification_number', readonly=False)
