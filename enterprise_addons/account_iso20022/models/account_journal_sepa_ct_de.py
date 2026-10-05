from odoo import models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def _skip_CdtrAgt(self, partner_bank, payment_method_line, effective_payment_method_code=None):
        payment_method_code = effective_payment_method_code or payment_method_line.code
        if payment_method_code == 'sepa_ct' and payment_method_line.sepa_pain_version == "pain.001.001.03.de":
            return False
        return super()._skip_CdtrAgt(partner_bank, payment_method_line, effective_payment_method_code=effective_payment_method_code)
