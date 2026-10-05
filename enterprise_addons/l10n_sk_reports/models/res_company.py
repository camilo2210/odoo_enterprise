from odoo import fields, models, api, _
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_sk_nace_code = fields.Char(string="SK NACE Code")

    @api.constrains('l10n_sk_nace_code')
    def _check_l10n_sk_nace_code(self):
        for company in self:
            if company.l10n_sk_nace_code and len(company.l10n_sk_nace_code) != 5:
                raise UserError(_("Please make sure that the company's SK NACE Code has 5 digits."))
