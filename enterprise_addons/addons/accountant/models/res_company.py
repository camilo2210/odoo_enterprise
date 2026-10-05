from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    account_tax_return_journal_id = fields.Many2one(
        comodel_name='account.journal',
        inverse='_inverse_account_tax_return_journal_id',
    )

    def _inverse_account_tax_return_journal_id(self):
        self.account_tax_return_journal_id.show_on_dashboard = True
