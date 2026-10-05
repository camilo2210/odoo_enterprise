from odoo import api, models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_om_annual_work_entry_type_id = fields.Many2one(
        "hr.work.entry.type",
        string="OM Annual Leave Time-off Type",
        default=lambda self: self.env.ref("hr_holidays.leave_type_paid_time_off", raise_if_not_found=False)
    )
    l10n_om_salary_payer = fields.Many2one(
        "res.partner",
        string="OM Salary Payer",
        compute='_compute_l10n_om_salary_payer',
        store=True,
        readonly=False,
    )
    l10n_om_company_mol_number = fields.Char(
        string="Company MOL Number",
        size=17,
        help="Ministry of Labour registration number for this entity, used in the Oman WPS export.",
    )
    l10n_om_salary_payer_mol_number = fields.Char(
        string="Salary Payer MOL Number",
        size=17,
        help="Ministry of Labour registration number for the Salary Payer, used in the Oman WPS export.",
    )
    l10n_om_bank_account_id = fields.Many2one(
        "res.partner.bank",
        string="WPS Disbursement Bank Account",
        help="Bank account used to disburse salaries in the WPS export. "
             "Must belong to the Salary Payer, not necessarily to this company as employer.")

    @api.depends('partner_id')
    def _compute_l10n_om_salary_payer(self):
        for company in self:
            if not company.l10n_om_salary_payer:
                company.l10n_om_salary_payer = company.partner_id
