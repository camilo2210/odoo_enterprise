# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    default_l10n_hk_internet = fields.Monetary(
        string="Internet Allowance",
        default_model="hr.version",
    )
    l10n_hk_autopay_partner_bank_id = fields.Many2one(
        related='company_id.l10n_hk_autopay_partner_bank_id',
        comodel_name='res.partner.bank',
        string="Autopay Account", readonly=False,
    )
    l10n_hk_employer_name = fields.Char(
        "Employer's Name shown on reports",
        related='company_id.l10n_hk_employer_name',
        readonly=False,
        help='This name will be shown on the ird report.'
    )
    l10n_hk_employer_file_number = fields.Char("Employer's File Number", related='company_id.l10n_hk_employer_file_number', readonly=False)
    l10n_hk_eoy_pay_month = fields.Selection(related='company_id.l10n_hk_eoy_pay_month', readonly=False)

    def open_mpf_scheme_list(self):
        self.ensure_one()
        return self.env['l10n_hk.mpf.scheme'].search([])._get_records_action(name=self.env._("MPF Schemes"))
