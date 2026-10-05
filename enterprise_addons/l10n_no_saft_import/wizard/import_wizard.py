from odoo import models


class AccountSaftImportWizard(models.TransientModel):
    _inherit = 'account.saft.import.wizard'

    def _get_account_code(self, element_account, nsmap):
        """ Override since the StandardAccountID is replaced by the grouping code in l10n_no_saft"""
        if self.company_id.account_fiscal_country_id.code == 'NO':
            return element_account.find('saft:GroupingCode', namespaces=nsmap).text
        return super()._get_account_code(element_account, nsmap)
