import re
from lxml import etree

from odoo import models
from odoo.tools import float_repr
from odoo.addons.account_batch_payment.models.sepa_mapping import sanitize_communication


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def _is_se_bban(self, payment_method_code):
        """ Whenever this journal should be considered as a swedish bban, plusgiro or bankgiro
            in a batch payment.

            :param payment_method_code: The payment method used for the payment

            :return: True if the payment method is set to **iso20022_se** and the bank account
                     is not IBAN, else False.
        """
        return (
            payment_method_code == 'iso20022_se'
            and self.bank_account_id.account_type in {'bban_se', 'plusgiro', 'bankgiro'}
        ) or self.env.context.get('bban')

    def _get_organization_id_node_text(self, payment_method_code, postal_address):
        # EXTENDS account_iso_20022
        if payment_method_code == 'iso20022_se' and postal_address and self.company_id.additional_identifiers.get('SE_EN') and self.bank_bic == 'SWEDSESS':
            return f"06{re.sub(r'[^0-9]', '', self.company_id.additional_identifiers['SE_EN'])}B001"

        return super()._get_organization_id_node_text(payment_method_code, postal_address)

    def _get_CtgyPurp(self, payment_method_code):
        if not self._is_se_bban(payment_method_code):
            return super()._get_CtgyPurp(payment_method_code)

        CtgyPurp = etree.Element('CtgyPurp')
        Cd = etree.SubElement(CtgyPurp, 'Cd')
        Cd.text = 'SALA' if self.env.context.get('sepa_payroll_sala') else 'SUPP'
        return CtgyPurp

    def _get_DbtrAcctOthr(self, payment_method_code=None):
        # EXTEND of account_iso20022
        Othr = super()._get_DbtrAcctOthr(payment_method_code)
        if payment_method_code == 'iso20022_se':
            SchmeNm = etree.SubElement(Othr, "SchmeNm")
            # Nordea has a special rule for DbtrAcct as they only use IBAN or BBAN
            if self.bank_account_id.account_type == 'bankgiro' and 'nordea' not in self.bank_account_id.bank_name.lower():
                Prtry = etree.SubElement(SchmeNm, "Prtry")
                Prtry.text = 'BGNR'
            else:
                Cd = etree.SubElement(SchmeNm, "Cd")
                Cd.text = 'BBAN'
        return Othr

    def _get_CdtrAcctIdOthr(self, bank_account, payment_method_code=None):
        if payment_method_code != 'iso20022_se':
            return super()._get_CdtrAcctIdOthr(bank_account, payment_method_code)

        Othr = etree.Element("Othr")
        Id = etree.SubElement(Othr, "Id")
        Id.text = bank_account.sanitized_account_number
        SchmeNm = etree.SubElement(Othr, "SchmeNm")
        if bank_account.account_type == 'bankgiro':
            Prtry = etree.SubElement(SchmeNm, "Prtry")
            Prtry.text = 'BGNR'
        else:
            Cd = etree.SubElement(SchmeNm, "Cd")
            Cd.text = 'BBAN'
        return Othr

    def _get_FinInstnId(self, bank_account, payment_method_line, mode=None, effective_payment_method_code=None):
        payment_method_code = effective_payment_method_code or payment_method_line.code

        if not self._is_se_bban(payment_method_code):
            return super()._get_FinInstnId(bank_account, payment_method_line, mode=mode, effective_payment_method_code=effective_payment_method_code)

        FinInstnId = etree.Element("FinInstnId")
        bic_code = self._get_cleaned_bic_code(bank_account, payment_method_line, effective_payment_method_code)
        if mode == 'DbtrAgt':
            BIC = etree.SubElement(FinInstnId, self._get_bic_tag(payment_method_line, effective_payment_method_code=effective_payment_method_code))
            BIC.text = bic_code
            return FinInstnId

        ClrSysMmbId = etree.SubElement(FinInstnId, "ClrSysMmbId")
        ClrSysId = etree.SubElement(ClrSysMmbId, "ClrSysId")
        Cd = etree.SubElement(ClrSysId, "Cd")
        Cd.text = "SESBA"
        MmbId = etree.SubElement(ClrSysMmbId, "MmbId")
        if bank_account.account_type == 'bankgiro':
            MmbId.text = '9900'
        elif bank_account.account_type == 'plusgiro':
            bank_code, _acc_num, _checksum = bank_account._se_get_acc_number_data(bank_account.account_number)
            MmbId.text = '9960' if bank_code and bank_code.startswith('996') else '9500'
        else:
            if not bank_account.account_number.isdigit():
                _bban, bank_code = bank_account._se_get_bban_from_iban()
            else:
                bank_code, _acc_num, _checksum = bank_account._se_get_acc_number_data(bank_account.account_number)
            MmbId.text = bank_code
        return FinInstnId

    def _get_RmtInf(self, payment_method_code, payment):
        RmtInf = super()._get_RmtInf(payment_method_code, payment)
        if RmtInf is False or not self._is_se_bban(payment_method_code):
            return RmtInf

        strd = RmtInf.find('Strd')
        if strd is not None:
            partner_bank_id = payment.get('partner_bank_id')
            if partner_bank_id:
                partner_bank = self.env['res.partner.bank'].browse(partner_bank_id)
                if partner_bank and partner_bank.account_type == 'bankgiro':
                    # if we got structured reference and the recipient has an account of type bankgiro, we need RfdDocAmt.
                    currency_id = payment.get('currency_id')
                    if currency_id:
                        ccy = self.env['res.currency'].browse(currency_id)
                        RfrdDocAmt = etree.Element('RfrdDocAmt')
                        if payment['payment_type'] == 'inbound':
                            CdtNoteAmt = etree.SubElement(RfrdDocAmt, 'CdtNoteAmt', Ccy=ccy.name)
                            CdtNoteAmt.text = float_repr(ccy.round(payment['amount']), 2)
                            RmtdAmt = etree.SubElement(RfrdDocAmt, 'RmtdAmt', Ccy=ccy.name)
                            RmtdAmt.text = '0.00'
                        elif payment['payment_type'] == 'outbound':
                            CdtNoteAmt = etree.SubElement(RfrdDocAmt, 'CdtNoteAmt', Ccy=ccy.name)
                            CdtNoteAmt.text = '0.00'
                            RmtdAmt = etree.SubElement(RfrdDocAmt, 'RmtdAmt', Ccy=ccy.name)
                            RmtdAmt.text = float_repr(ccy.round(payment['amount']), 2)
                        strd.insert(0, RfrdDocAmt)
        return RmtInf

    def _get_PstlAdr(self, partner_id, payment_method_line, effective_payment_method_code=None):
        # EXTEND account_iso20022
        if payment_method_line.code == 'iso20022_se':
            postal_address = self.get_postal_address(partner_id, payment_method_line)
            if postal_address is not None:
                PstlAdr = etree.Element("PstlAdr")
                for node_name, attr, size in [('StrtNm', 'street', 70), ('PstCd', 'zip', 140), ('TwnNm', 'city', 140), ('Ctry', 'country', 2)]:
                    if postal_address[attr]:
                        address_element = etree.SubElement(PstlAdr, node_name)
                        address_element.text = sanitize_communication(postal_address[attr], size)
                return PstlAdr

        return super()._get_PstlAdr(partner_id, payment_method_line, effective_payment_method_code)

    def _skip_CdtrAgt(self, partner_bank, payment_method_line, effective_payment_method_code=None):
        """
        Determine whether to skip the Creditor Agent (CdtrAgt) element in SEPA XML.

        This override ensures that for Swedish Bankgiro and Plusgiro accounts,
        the CdtrAgt element is always included, even if the BIC is missing.

        For other accounts or payment methods, the standard behavior is preserved.

        :param partner_bank: The partner's bank account record.
        :type partner_bank: res.partner.bank
        :param payment_method_code: The payment method code, e.g., 'iso20022_se'.
        :type payment_method_code: str
        :return: False to indicate that CdtrAgt should not be skipped, or the
                 result of the standard implementation.
        :rtype: bool
        """
        payment_method_code = effective_payment_method_code or payment_method_line.code
        if payment_method_code == 'iso20022_se':
            return False
        return super()._skip_CdtrAgt(partner_bank, payment_method_line, effective_payment_method_code=effective_payment_method_code)
