# Part of Odoo. See LICENSE file for full copyright and licensing details.
from lxml import etree
from odoo import fields, models
from odoo.tools.business_data import street_split

from odoo.addons.account_batch_payment.models.sepa_mapping import sanitize_communication


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def _should_use_pain_09(self, payment_method_line, effective_payment_method_code=None):
        payment_method_code = effective_payment_method_code or payment_method_line.code
        force_iso_20022_pain_09 = bool(self.env['ir.config_parameter'].sudo().get_bool('account_iso20022.force_iso_20022_pain_09'))
        return (
            (payment_method_code in {'sepa_ct', 'iso20022_ch', 'iso20022_se'} and payment_method_line.sepa_pain_version == "pain.001.001.09") or
            (payment_method_code == 'iso20022' and force_iso_20022_pain_09)
        )

    def _get_ReqdExctnDt_content(self, payment_date, payment_method_line, effective_payment_method_code=None):
        ReqdExctnDt = etree.Element("ReqdExctnDt")
        if self._should_use_pain_09(payment_method_line, effective_payment_method_code):
            Dt = etree.SubElement(ReqdExctnDt, "Dt")
            Dt.text = fields.Date.to_string(payment_date)
            return ReqdExctnDt
        return super()._get_ReqdExctnDt_content(payment_date, payment_method_line, effective_payment_method_code=effective_payment_method_code)

    def _skip_CdtrAgt(self, partner_bank, payment_method_line, effective_payment_method_code=None):
        payment_method_code = effective_payment_method_code or payment_method_line.code
        if payment_method_code == 'sepa_ct' and payment_method_line.sepa_pain_version == "pain_de":
            return False
        return super()._skip_CdtrAgt(partner_bank, payment_method_line, effective_payment_method_code=effective_payment_method_code)

    def _get_CdtrAgt(self, bank_account, payment_method_line, effective_payment_method_code=None):
        CdtrAgt = super()._get_CdtrAgt(bank_account, payment_method_line, effective_payment_method_code=effective_payment_method_code)
        if self._should_use_pain_09(payment_method_line):
            FinInstnId = CdtrAgt.find(".//FinInstnId")
            partner_lei = bank_account.partner_id.iso20022_lei
            if partner_lei:
                # LEI needs to be inserted after BIC
                LEI = etree.SubElement(FinInstnId, "LEI")
                LEI.text = partner_lei
            return CdtrAgt
        return CdtrAgt

    def _get_ChrgBr(self, payment_method_code, forced_value):
        if payment_method_code == 'sepa_ct':
            ChrgBr = etree.Element("ChrgBr")
            ChrgBr.text = "SLEV"
            return ChrgBr
        return super()._get_ChrgBr(payment_method_code, forced_value)

    def _get_PstlAdr(self, partner_id, payment_method_line, effective_payment_method_code=None):
        if self._should_use_pain_09(payment_method_line):
            postal_address = self.get_postal_address(partner_id, payment_method_line, effective_payment_method_code)
            if postal_address is not None:
                PstlAdr = etree.Element("PstlAdr")
                street_details = street_split(postal_address['street'])
                if street_name := street_details.get('street_name'):
                    address_element = etree.SubElement(PstlAdr, 'StrtNm')
                    address_element.text = sanitize_communication(street_name, 70)
                if street_number := street_details.get('street_number'):
                    address_element = etree.SubElement(PstlAdr, 'BldgNb')
                    address_element.text = sanitize_communication(street_number, 16)

                for node_name, attr, size in [('PstCd', 'zip', 140), ('TwnNm', 'city', 140), ('Ctry', 'country', 2)]:
                    if postal_address[attr]:
                        address_element = etree.SubElement(PstlAdr, node_name)
                        address_element.text = sanitize_communication(postal_address[attr], size)
                return PstlAdr
        return super()._get_PstlAdr(partner_id, payment_method_line, effective_payment_method_code)

    def _get_CdtTrfTxInf(self, PmtInfId, payment, payment_method_line, include_charge_bearer=True, effective_payment_method_code=None):
        CdtTrfTxInf = super()._get_CdtTrfTxInf(PmtInfId, payment, payment_method_line, include_charge_bearer, effective_payment_method_code)
        payment_method_code = effective_payment_method_code or payment_method_line.code
        force_iso_20022_pain_09 = self.env['ir.config_parameter'].sudo().get_bool('account_iso20022.force_iso_20022_pain_09')
        partner = self.env['res.partner'].sudo().browse(payment['partner_id'])
        if payment_method_code == 'iso20022' and force_iso_20022_pain_09 and payment.get("iso20022_uetr"):
            PmtId = CdtTrfTxInf.find(".//PmtId")
            UETR = etree.SubElement(PmtId, "UETR")
            UETR.text = payment["iso20022_uetr"]
        if payment_method_code == 'sepa_ct' and partner.country_id.code and partner.city:
            Cdtr = CdtTrfTxInf.find("Cdtr")
            partner = self.env['res.partner'].sudo().browse(payment['partner_id'])
            PstlAdr = Cdtr.find(".//PstlAdr")
            if PstlAdr is not None:
                Cdtr.remove(PstlAdr)
            Cdtr.append(self._get_PstlAdr(partner, payment_method_line, effective_payment_method_code))
        return CdtTrfTxInf

    def _get_RmtInf_content(self, ref, reference_type=''):
        if reference_type == 'be':
            return self.get_strd_tree(ref, cd='SCOR', issr='BBA')
        elif reference_type == 'ch':
            ref = sanitize_communication(ref).rjust(27, '0')
            return self.get_strd_tree(ref, prtry='QRR')
        elif reference_type in ('fi', 'no', 'se'):
            return self.get_strd_tree(ref, cd='SCOR')
        return super()._get_RmtInf_content(ref, reference_type)

    def _get_RmtInf(self, payment_method_code, payment):
        # sanitize_communication() automatically removes leading slash
        # characters in payment references, due to the requirements of
        # European Payment Council, available here:
        # https://www.europeanpaymentscouncil.eu/document-library/implementation-guidelines/sepa-credit-transfer-customer-psp-implementation
        # (cfr Section 1.4 Character Set)

        # However, the /A/  four-character prefix is a requirement of belgian law.
        # The existence of such legal prefixes may be a reason why the leading slash
        # is forbidden in normal SEPA payment references, to avoid conflicts.

        # Legal references for Belgian salaries:
        # https://www.ejustice.just.fgov.be/eli/loi/1967/10/10/1967101056/justel#Art.1411bis
        # Article 1411bis of Belgian Judicial Code mandating the use of special codes
        # for identifying payments of protected amounts, and the related penalties
        # for payment originators, in case of misuse.

        # https://www.ejustice.just.fgov.be/eli/arrete/2006/07/04/2006009525/moniteur
        # Royal Decree defining "/A/ " as the code for salaries, in the context of
        # Article 1411bis
        if self.env.context.get('l10n_be_hr_payroll_sepa_salary_payment'):
            RmtInf = super()._get_RmtInf(payment_method_code, payment)
            if (Ustrd := RmtInf.find("Ustrd")) is None:
                Ustrd = etree.SubElement(RmtInf, "Ustrd")
            memo = sanitize_communication(payment['memo'])
            Ustrd.text = f"/A/ {memo}"
            return RmtInf
        return super()._get_RmtInf(payment_method_code, payment)

    def _get_bic_tag(self, payment_method_line, effective_payment_method_code=None):
        payment_method_code = effective_payment_method_code or payment_method_line.code
        use_pain_09 = payment_method_code == 'iso20022_se' and payment_method_line.sepa_pain_version == "pain.001.001.09"
        if use_pain_09 or self._should_use_pain_09(payment_method_line, effective_payment_method_code):
            return 'BICFI'
        return super()._get_bic_tag(payment_method_code)

    def _get_regex_for_bic_code(self, payment_method_line, effective_payment_method_code=None):
        if self._should_use_pain_09(payment_method_line, effective_payment_method_code):
            return '[A-Z0-9]{4,4}[A-Z]{2,2}[A-Z0-9]{2,2}([A-Z0-9]{3,3}){0,1}'
        return super()._get_regex_for_bic_code(payment_method_line, effective_payment_method_code)

    def _get_SvcLvlText(self, payment_method_code):
        if payment_method_code == 'sepa_ct':
            return 'SEPA'
        return super()._get_SvcLvlText(payment_method_code)
