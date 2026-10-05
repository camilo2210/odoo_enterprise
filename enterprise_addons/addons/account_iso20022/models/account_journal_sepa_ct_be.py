from lxml import etree

from odoo import models

from odoo.addons.account_batch_payment.models.sepa_mapping import sanitize_communication


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def _get_CdtTrfTxInf(self, PmtInfId, payment, payment_method_line, include_charge_bearer=True, effective_payment_method_code=None):
        CdtTrfTxInf = super()._get_CdtTrfTxInf(PmtInfId, payment, payment_method_line, include_charge_bearer, effective_payment_method_code)
        payment_method_code = effective_payment_method_code or payment_method_line.code
        partner = self.env['res.partner'].sudo().browse(payment['partner_id'])
        partner_bank = self.env['res.partner.bank'].sudo().browse(payment['partner_bank_id'])

        if payment_method_code != 'sepa_ct' or not partner.country_id.code:
            return CdtTrfTxInf

        Cdtr = CdtTrfTxInf.find("Cdtr")
        if partner_bank.is_third_party and partner_bank.third_party_beneficiary_id:
            partner = partner_bank.third_party_beneficiary_id
            Nm = Cdtr.find(".//Nm")
            if Nm is not None:
                Cdtr.remove(Nm)
            PstlAdr = Cdtr.find(".//PstlAdr")
            if PstlAdr is not None:
                Cdtr.remove(PstlAdr)
            Nm = etree.SubElement(Cdtr, "Nm")
            Nm.text = sanitize_communication((
                partner_bank.holder_name or partner.name or partner.commercial_partner_id.name or '/'
            )[:70]).strip() or '/'
            Cdtr.append(self._get_PstlAdr(partner, payment_method_line, effective_payment_method_code))
        return CdtTrfTxInf
