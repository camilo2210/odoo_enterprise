from lxml import etree
from odoo import models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def get_document_namespace(self, payment_method_line):
        if payment_method_line.code == 'iso20022_ch' and payment_method_line.sepa_pain_version == 'pain.001.001.03':
            return 'http://www.six-interbank-clearing.com/de/pain.001.001.03.ch.02.xsd'
        return super().get_document_namespace(payment_method_line)

    def _get_schema_location(self, payment_method_line):
        self.ensure_one()
        if payment_method_line.code == 'iso20022_ch' and payment_method_line.sepa_pain_version == 'pain.001.001.09':
            return '{http://www.w3.org/2001/XMLSchema-instance}schemaLocation', 'urn:iso:std:iso:20022:tech:xsd:pain.001.001.09 pain.001.001.09.xsd'
        return super()._get_schema_location(payment_method_line)

    def _get_Dbtr(self, payment_method_line, effective_payment_method_code=None):
        Dbtr = super()._get_Dbtr(payment_method_line, effective_payment_method_code)
        payment_method_code = effective_payment_method_code or payment_method_line.code
        if payment_method_code == 'iso20022_ch':
            result = list(filter(lambda x: x.tag != 'Id', Dbtr))
            new_dbtr = etree.Element('Dbtr')
            new_dbtr.extend(result)
            return new_dbtr
        return Dbtr

    def _get_ClrSysMmbId(self, bank_account, payment_method_code):
        if payment_method_code != 'iso20022_ch' or not bank_account.bank_bic:
            return super()._get_ClrSysMmbId(bank_account, payment_method_code)
