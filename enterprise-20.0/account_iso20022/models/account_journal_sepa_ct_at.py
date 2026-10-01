from lxml import etree
from odoo import models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def _get_InitgPty(self, payment_method_line):
        if payment_method_line.code == 'sepa_ct' and payment_method_line.sepa_pain_version == 'pain.001.001.03.austrian.004':
            InitgPty = etree.Element("InitgPty")
            InitgPty.extend(self._get_company_PartyIdentification32(postal_address=False, issr=False, payment_method_line=payment_method_line))
            return InitgPty
        return super()._get_InitgPty(payment_method_line)
