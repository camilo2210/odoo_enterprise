from lxml import etree
from odoo import models

SCHEM_NAME_PER_BANK_BIC = {
    'init': {
        'BANK': {'SWEDSESS'},
        'CUST': {'NDEASESS'},
    },
    'dbtr': {
        'BANK': {'NDEASESS', 'SWEDSESS'},
        'CUST': {},
    },
}


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def _get_SvcLvlText(self, payment_method_code):
        if payment_method_code == 'iso20022_se':
            return 'NURG'
        return super()._get_SvcLvlText(payment_method_code)

    def _get_company_PartyIdentification32(self, payment_method_line, postal_address=True, nm=True, issr=True, schme_nm=False, effective_payment_method_code=None):
        result = super()._get_company_PartyIdentification32(payment_method_line, postal_address=postal_address, issr=issr, schme_nm=schme_nm, effective_payment_method_code=effective_payment_method_code)
        payment_method_code = effective_payment_method_code or payment_method_line.code
        if payment_method_code == 'iso20022_se':
            if not nm:
                result = list(filter(lambda x: x.tag != 'Nm', result))
        return result

    def _get_InitgPty(self, payment_method_line):
        if payment_method_line.code == 'iso20022_se':
            InitgPty = etree.Element("InitgPty")
            schme_nm = 'CUST' if self.bank_bic in SCHEM_NAME_PER_BANK_BIC['init']['CUST'] else 'BANK'
            InitgPty.extend(self._get_company_PartyIdentification32(postal_address=False, issr=False, nm=False, schme_nm=schme_nm, payment_method_line=payment_method_line))
            return InitgPty
        return super()._get_InitgPty(payment_method_line)

    def _get_Dbtr(self, payment_method_line, effective_payment_method_code=None):
        payment_method_code = effective_payment_method_code or payment_method_line.code
        if payment_method_code == 'iso20022_se':
            Dbtr = etree.Element("Dbtr")
            schme_nm = 'BANK' if self.bank_bic in SCHEM_NAME_PER_BANK_BIC['dbtr']['BANK'] else 'CUST'
            Dbtr.extend(self._get_company_PartyIdentification32(postal_address=True, issr=False, schme_nm=schme_nm, payment_method_line=payment_method_line, effective_payment_method_code=effective_payment_method_code))
            return Dbtr
        return super()._get_Dbtr(payment_method_line, effective_payment_method_code)

    def get_postal_address(self, partner_id, payment_method_line, effective_payment_method_code=None):
        payment_method_code = effective_payment_method_code or payment_method_line.code
        if payment_method_code == 'iso20022_se':
            pstl_addr_list = [address for address in partner_id._get_all_addr() if address['country']]
            if not pstl_addr_list:
                return None
            for addr_dict in pstl_addr_list:
                if addr_dict['contact_type'] == 'employee':
                    return addr_dict
            return pstl_addr_list[0]
        return super().get_postal_address(partner_id, payment_method_line, effective_payment_method_code)

    def _get_CdtTrfTxInf(self, PmtInfId, payment, payment_method_line, include_charge_bearer=True, effective_payment_method_code=None):
        # For Sweden, country is sufficient ; handle the case where the city was not specified beforehand
        payment_method_code = effective_payment_method_code or payment_method_line.code
        CdtTrfTxInf = super()._get_CdtTrfTxInf(PmtInfId, payment, payment_method_line, include_charge_bearer, effective_payment_method_code)
        if payment_method_code == 'iso20022_se':
            partner = self.env['res.partner'].sudo().browse(payment['partner_id'])
            if not partner.city and partner.country_id.code:
                Cdtr = CdtTrfTxInf.find("Cdtr")
                PstlAdr = Cdtr.find("PstlAdr")
                if PstlAdr is None:
                    Cdtr.append(self._get_PstlAdr(partner, payment_method_line, effective_payment_method_code))
        return CdtTrfTxInf
