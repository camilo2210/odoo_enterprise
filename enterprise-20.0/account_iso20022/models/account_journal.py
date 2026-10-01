# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re
import time
from collections import defaultdict
from lxml import etree
from uuid import uuid4

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_repr, float_round

from odoo.tools.bank_account_number import get_iban_part
import odoo.addons.account.tools.structured_reference as sr
from odoo.addons.account_batch_payment.models.sepa_mapping import sanitize_communication
from odoo.addons.account_iso20022.models.account_payment import ISO20022_CHARGE_BEARER_SELECTION, ISO20022_PRIORITY_SELECTION, ISO20022_PRIORITY_HELP

class AccountJournal(models.Model):
    _inherit = "account.journal"

    has_sepa_ct_payment_method = fields.Boolean(compute='_compute_has_sepa_ct_payment_method')
    iso20022_default_priority = fields.Selection(
        selection=ISO20022_PRIORITY_SELECTION,
        string='Default Priority',
        default='NORM',
        help=ISO20022_PRIORITY_HELP,
        required=True,
    )
    iso20022_charge_bearer = fields.Selection(
        string="ISO 20022 Charge Bearer",
        selection=ISO20022_CHARGE_BEARER_SELECTION,
        default='SHAR',
        help="Specifies which party/parties will bear the charges associated with the processing of ISO 20022 payment transactions from this journal."
    )
    has_iso20022_payment_method = fields.Boolean(compute='_compute_has_iso20022_payment_method')

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    @api.depends('outbound_payment_method_line_ids.payment_method_id.code')
    def _compute_has_sepa_ct_payment_method(self):
        for rec in self:
            payment_method_codes = rec.mapped('outbound_payment_method_line_ids.payment_method_id.code')
            rec.has_sepa_ct_payment_method = (
                'sepa_ct' in payment_method_codes
                or 'iso20022_ch' in payment_method_codes and self.env['ir.config_parameter'].sudo().get_bool('iso20022_ch_force_sepa')
            )

    @api.depends('outbound_payment_method_line_ids.payment_method_id.code')
    def _compute_has_iso20022_payment_method(self):
        for journal in self:
            journal.has_iso20022_payment_method = any(
                journal.mapped('outbound_payment_method_line_ids.payment_method_id.is_iso20022')
            )

    # -------------------------------------------------------------------------
    # GENERIC OVERRIDES
    # -------------------------------------------------------------------------
    def _default_outbound_payment_methods(self):
        res = super()._default_outbound_payment_methods()
        if self._is_payment_method_available('sepa_ct'):
            res |= self.env.ref('account_iso20022.account_payment_method_sepa_ct')
        elif self._is_payment_method_available('iso20022_se'):
            res |= self.env.ref('account_iso20022.account_payment_method_iso20022_se')
        elif self._is_payment_method_available('iso20022_ch'):
            res |= self.env.ref('account_iso20022.account_payment_method_iso20022_ch')
        elif self._is_payment_method_available('iso20022_us'):
            res |= self.env.ref('account_iso20022.account_payment_method_iso20022_us')
        elif self._is_payment_method_available('iso20022'):
            res |= self.env.ref('account_iso20022.account_payment_method_iso20022')

        return res

    # -------------------------------------------------------------------------
    # DOCUMENT CREATION
    # -------------------------------------------------------------------------

    def create_iso20022_credit_transfer(self, payments, payment_method_line, batch_booking=False):
        """Returns the content of the XML file."""
        Document = self.create_iso20022_credit_transfer_content(payments, payment_method_line, batch_booking=batch_booking)
        return etree.tostring(Document, pretty_print=True, xml_declaration=True, encoding='UTF-8')

    def create_iso20022_credit_transfer_content(self, payments, payment_method_line, batch_booking=False):
        """
            Creates the body of the XML file for the ISO20022 document.
        """
        if payment_method_line.sepa_pain_version not in payment_method_line._fields['sepa_pain_version'].get_values(self.env):
            # Might happen because of a migration issue (fixed in https://github.com/odoo/upgrade/pull/9771).
            payment_method_line.sepa_pain_version = 'pain.001.001.09'

        Document = etree.Element("Document", nsmap={
            None: self.get_document_namespace(payment_method_line),
            'xsi': "http://www.w3.org/2001/XMLSchema-instance"
        })

        if schema_location := self._get_schema_location(payment_method_line):
            Document.set(schema_location[0], schema_location[1])

        CstmrCdtTrfInitn = etree.SubElement(Document, "CstmrCdtTrfInitn")

        # Create the GrpHdr XML block
        GrpHdr = etree.SubElement(CstmrCdtTrfInitn, "GrpHdr")
        MsgId = etree.SubElement(GrpHdr, "MsgId")
        val_MsgId = str(time.time())
        MsgId.text = val_MsgId
        CreDtTm = etree.SubElement(GrpHdr, "CreDtTm")
        CreDtTm.text = time.strftime("%Y-%m-%dT%H:%M:%S")
        NbOfTxs = etree.SubElement(GrpHdr, "NbOfTxs")
        val_NbOfTxs = str(len(payments))
        if len(val_NbOfTxs) > 15:
            raise ValidationError(_("Too many transactions for a single file."))
        NbOfTxs.text = val_NbOfTxs
        CtrlSum = etree.SubElement(GrpHdr, "CtrlSum")
        CtrlSum.text = self._get_CtrlSum(payments)
        GrpHdr.append(self._get_InitgPty(payment_method_line))

        # Create one PmtInf XML block per execution date, per currency
        eur_currency = self.env.ref('base.EUR')
        chf_currency = self.env.ref('base.CHF')
        payments_date_instr_wise = defaultdict(list)
        today = fields.Date.context_today(self)
        iso20022_ch_force_sepa = self.env['ir.config_parameter'].sudo().get_bool('iso20022_ch_force_sepa')
        iso20022_force_sepa = self.env['ir.config_parameter'].sudo().get_bool('account_iso20022.force_sepa_for_eur')
        for payment in payments:
            required_payment_date = max(payment['payment_date'], today)
            currency_id = payment['currency_id'] or self.company_id.currency_id.id
            priority = payment['iso20022_priority']
            sepa_priority = payment.get('sepa_priority', 'std')
            payments_date_instr_wise[required_payment_date, currency_id, priority, sepa_priority].append(payment)
        for count, ((payment_date, currency_id, priority, sepa_priority), payments_list) in enumerate(payments_date_instr_wise.items()):
            PmtInf = etree.SubElement(CstmrCdtTrfInitn, "PmtInf")
            PmtInfId = etree.SubElement(PmtInf, "PmtInfId")
            PmtInfId.text = (val_MsgId + str(self.id) + str(count))[-30:]
            PmtMtd = etree.SubElement(PmtInf, "PmtMtd")
            PmtMtd.text = 'TRF' if sepa_priority != 'sct' else 'INST'
            BtchBookg = etree.SubElement(PmtInf, "BtchBookg")
            BtchBookg.text = batch_booking and 'true' or 'false'
            NbOfTxs = etree.SubElement(PmtInf, "NbOfTxs")
            NbOfTxs.text = str(len(payments_list))
            CtrlSum = etree.SubElement(PmtInf, "CtrlSum")
            CtrlSum.text = self._get_CtrlSum(payments_list)

            group_payment_method_code = payment_method_line.code
            if iso20022_ch_force_sepa and group_payment_method_code == 'iso20022_ch':
                # The Swiss ISO20022 implementation considers SEPA as a subset of what it allows (payment type S),
                # as well as more generic ISO20022 payments (payment type X). To handle that, we change the payment_method_code
                # dynamically when adding the grouped payments to the XML file.
                if currency_id == eur_currency.id:
                    group_payment_method_code = 'sepa_ct'
                elif currency_id != chf_currency.id:
                    group_payment_method_code = 'iso20022'
            elif iso20022_force_sepa and group_payment_method_code == 'iso20022' and currency_id == eur_currency.id:
                # The SEPA Credit Transfer payment method is only offered on EUR journals, so a journal in
                # another currency (like SEK, USD, GBP) that occasionally pays a SEPA-zone IBAN in EUR falls
                # back to the generic ISO20022 payment method, which otherwise always reports a NURG service
                # level and a SHAR charge bearer. This flag lets those EUR batches be treated
                # as genuine SEPA Credit Transfers, like the iso20022_ch_force_sepa mechanism above.
                group_payment_method_code = 'sepa_ct'

            PmtTpInf = self._get_PmtTpInf(group_payment_method_code, priority)
            if len(PmtTpInf) != 0:  # Boolean conversion from etree element triggers a deprecation warning ; this is the proper way
                PmtInf.append(PmtTpInf)

            ReqdExctnDt = self._get_ReqdExctnDt_content(payment_date, payment_method_line, effective_payment_method_code=group_payment_method_code)
            PmtInf.append(ReqdExctnDt)

            PmtInf.append(self._get_Dbtr(payment_method_line, group_payment_method_code))
            PmtInf.append(self._get_DbtrAcct(group_payment_method_code))
            DbtrAgt = etree.SubElement(PmtInf, "DbtrAgt")
            DbtrAgt.append(self._get_FinInstnId(self.bank_account_id, payment_method_line, mode='DbtrAgt', effective_payment_method_code=group_payment_method_code))
            unique_chrgbr_values = {payment.get('iso20022_charge_bearer') for payment in payments_list}
            unique_chrgbr = unique_chrgbr_values.pop() if len(unique_chrgbr_values) == 1 else None
            if unique_chrgbr:
                PmtInf.append(self._get_ChrgBr(group_payment_method_code, unique_chrgbr))

            # One CdtTrfTxInf per transaction
            for payment in payments_list:
                PmtInf.append(self._get_CdtTrfTxInf(
                    PmtInfId, payment, payment_method_line, include_charge_bearer=not unique_chrgbr, effective_payment_method_code=group_payment_method_code,
                ))
        return Document

    # -------------------------------------------------------------------------
    # NODES CREATION
    # -------------------------------------------------------------------------
    def _get_CtrlSum(self, payments):
        # To override per pain version
        return float_repr(float_round(sum(payment['amount'] for payment in payments), 2), 2)

    def _get_InitgPty(self, payment_method_line):
        InitgPty = etree.Element("InitgPty")
        InitgPty.extend(self._get_company_PartyIdentification32(postal_address=False, issr=True, payment_method_line=payment_method_line))
        return InitgPty

    def _get_PmtTpInf(self, payment_method_code, priority):
        PmtTpInf = etree.Element("PmtTpInf")
        if priority:
            InstrPrty = etree.SubElement(PmtTpInf, "InstrPrty")
            InstrPrty.text = priority
        SvcLvlTxt = self._get_SvcLvlText(payment_method_code)
        if SvcLvlTxt:
            SvcLvl = etree.SubElement(PmtTpInf, "SvcLvl")
            Cd = etree.SubElement(SvcLvl, "Cd")
            Cd.text = SvcLvlTxt

        CtgyPurp = self._get_CtgyPurp(payment_method_code)
        if CtgyPurp is not None:  # avoid FutureWarning
            PmtTpInf.append(CtgyPurp)

        LclInstrm = self._get_LclInstrm(payment_method_code)
        if LclInstrm is not None:
            PmtTpInf.append(LclInstrm)
        return PmtTpInf

    def _get_LclInstrm(self, payment_method_code):
        if payment_method_code == 'iso20022' and (local_instrument_code := self.env['ir.config_parameter'].sudo().get_str('account_iso20022.local_instrument_code')):
            LclInstrm = etree.Element("LclInstrm")
            Cd = etree.SubElement(LclInstrm, 'Cd')
            Cd.text = local_instrument_code
            return LclInstrm

    def _get_CtgyPurp(self, payment_method_code):
        if self.env.context.get('sepa_payroll_sala'):
            # The SALA purpose code is standard for all SEPA, and guarantees a series
            # of things in instant payment: https://www.sepaforcorporates.com/sepa-payments/sala-sepa-salary-payments.
            CtgyPurp = etree.Element("CtgyPurp")
            Cd = etree.SubElement(CtgyPurp, "Cd")
            Cd.text = 'SALA'
            return CtgyPurp

    def _get_ReqdExctnDt_content(self, payment_date, payment_method_line, effective_payment_method_code=None):
        ReqdExctnDt = etree.Element("ReqdExctnDt")
        ReqdExctnDt.text = fields.Date.to_string(payment_date)
        return ReqdExctnDt

    def _get_Dbtr(self, payment_method_line, effective_payment_method_code=None):
        Dbtr = etree.Element("Dbtr")
        Dbtr.extend(self._get_company_PartyIdentification32(postal_address=True, payment_method_line=payment_method_line, effective_payment_method_code=effective_payment_method_code))
        return Dbtr

    def _get_DbtrAcct(self, payment_method_code=None):
        if not self.bank_account_id.sanitized_account_number:
            raise UserError(_("This journal does not have a bank account defined."))
        DbtrAcct = etree.Element("DbtrAcct")
        Id = etree.SubElement(DbtrAcct, "Id")
        if self.bank_account_id.account_type != 'iban' or self._is_bank_account_qr_iban(self.bank_account_id):
            Id.append(self._get_DbtrAcctOthr(payment_method_code))
        else:
            IBAN = etree.SubElement(Id, "IBAN")
            IBAN.text = self.bank_account_id.sanitized_account_number
        Ccy = etree.SubElement(DbtrAcct, "Ccy")
        Ccy.text = self.currency_id and self.currency_id.name or self.company_id.currency_id.name
        return DbtrAcct

    def _get_DbtrAcctOthr(self, payment_method_code=None):
        Othr = etree.Element("Othr")
        OthrId = etree.SubElement(Othr, "Id")
        OthrId.text = self.bank_account_id.sanitized_account_number
        return Othr

    def _get_ChrgBr(self, payment_method_code, forced_value):
        ChrgBr = etree.Element("ChrgBr")
        ChrgBr.text = forced_value or "SHAR"
        return ChrgBr

    def _get_CdtTrfTxInf(self, PmtInfId, payment, payment_method_line, include_charge_bearer=True, effective_payment_method_code=None):
        payment_method_code = effective_payment_method_code or payment_method_line.code
        CdtTrfTxInf = etree.Element("CdtTrfTxInf")
        PmtId = etree.SubElement(CdtTrfTxInf, "PmtId")
        if payment['name']:
            InstrId = etree.SubElement(PmtId, "InstrId")
            InstrId.text = sanitize_communication(payment['name'].replace('&', '+'), 35)
        EndToEndId = etree.SubElement(PmtId, "EndToEndId")
        EndToEndId.text = payment.get('transaction_uuid') or uuid4().hex
        Amt = etree.SubElement(CdtTrfTxInf, "Amt")

        journal_id = self.env['account.journal'].search([('id', '=', payment['journal_id'])], limit=1)
        currency_id = self.env['res.currency'].search([('id', '=', payment['currency_id'])], limit=1) or journal_id.company_id.currency_id
        val_Ccy = currency_id.name
        val_InstdAmt = float_repr(currency_id.round(payment['amount']), currency_id.decimal_places)
        InstdAmt = etree.SubElement(Amt, "InstdAmt", Ccy=val_Ccy)
        InstdAmt.text = val_InstdAmt

        if include_charge_bearer:
            CdtTrfTxInf.append(self._get_ChrgBr(payment_method_code, payment['iso20022_charge_bearer']))

        partner = self.env['res.partner'].sudo().browse(payment['partner_id'])

        partner_bank_id = payment.get('partner_bank_id')
        if not partner_bank_id:
            raise UserError(_('Partner %s has not bank account defined.', partner.name))

        partner_bank = self.env['res.partner.bank'].sudo().browse(partner_bank_id)

        if not self._skip_CdtrAgt(partner_bank, payment_method_line, effective_payment_method_code):
            CdtTrfTxInf.append(self._get_CdtrAgt(partner_bank, payment_method_line, effective_payment_method_code))

        Cdtr = etree.SubElement(CdtTrfTxInf, "Cdtr")
        Nm = etree.SubElement(Cdtr, "Nm")
        Nm.text = sanitize_communication((
            partner_bank.holder_name or partner.name or partner.commercial_partner_id.name or '/'
        )[:70]).strip() or '/'

        PstlAdr = self._get_PstlAdr(partner, payment_method_line, effective_payment_method_code)
        if PstlAdr is not None:
            Cdtr.append(PstlAdr)

        CdtTrfTxInf.append(self._get_CdtrAcct(partner_bank, payment_method_code))

        val_RmtInf = self._get_RmtInf(payment_method_code, payment)
        if val_RmtInf is not False:
            CdtTrfTxInf.append(val_RmtInf)
        return CdtTrfTxInf

    def _get_CdtrAgt(self, bank_account, payment_method_line, effective_payment_method_code=None):
        CdtrAgt = etree.Element("CdtrAgt")
        CdtrAgt.append(self._get_FinInstnId(bank_account, payment_method_line, mode='CdtrAgt', effective_payment_method_code=effective_payment_method_code))
        return CdtrAgt

    def _get_FinInstnId(self, bank_account, payment_method_line, mode=None, effective_payment_method_code=None):
        payment_method_code = effective_payment_method_code or payment_method_line.code
        FinInstnId = etree.Element("FinInstnId")
        bic_code = self._get_cleaned_bic_code(bank_account, payment_method_line, effective_payment_method_code)
        if bic_code:
            BIC = etree.SubElement(FinInstnId, self._get_bic_tag(payment_method_line, effective_payment_method_code))
            BIC.text = bic_code
        else:
            Othr = etree.SubElement(FinInstnId, "Othr")
            Id = etree.SubElement(Othr, "Id")
            Id.text = "NOTPROVIDED"
        ClrSysMmbId = self._get_ClrSysMmbId(bank_account, payment_method_code)
        if ClrSysMmbId is not None:
            FinInstnId.append(ClrSysMmbId)
        return FinInstnId

    def _get_ClrSysMmbId(self, bank_account, payment_method_code):
        if bank_account._get_clearing_number():
            ClrSysMmbId = etree.Element("ClrSysMmbId")
            MmbId = etree.SubElement(ClrSysMmbId, "MmbId")
            MmbId.text = bank_account._get_clearing_number()
            return ClrSysMmbId

    def _get_CdtrAcct(self, bank_account, payment_method_code=None):
        CdtrAcct = etree.Element("CdtrAcct")
        Id = etree.SubElement(CdtrAcct, "Id")
        if bank_account.account_type == 'iban':
            IBAN = etree.SubElement(Id, "IBAN")
            IBAN.text = bank_account.sanitized_account_number
        else:
            Id.append(self._get_CdtrAcctIdOthr(bank_account, payment_method_code))
        return CdtrAcct

    def _get_CdtrAcctIdOthr(self, bank_account, payment_method_code=None):
        Othr = etree.Element("Othr")
        Id = etree.SubElement(Othr, "Id")
        account_number = bank_account.sanitized_account_number

        # CH case when we have non-unique account numbers
        if " " in bank_account.sanitized_account_number and " " in bank_account.account_number:
            account_number = bank_account.account_number.split(" ")[0]
        Id.text = account_number
        return Othr

    def _get_RmtInf(self, payment_method_code, payment):
        def detect_reference_type(reference, partner_country_code):
            if partner_country_code == 'BE' and sr.is_valid_structured_reference_be(reference):
                return 'be'
            elif self._is_qr_iban(payment):
                return 'ch'
            elif partner_country_code == 'DK' and sr.is_valid_structured_reference_dk(reference):
                return 'dk'
            elif partner_country_code == 'FI' and sr.is_valid_structured_reference_fi(reference):
                return 'fi'
            elif partner_country_code == 'NO' and sr.is_valid_structured_reference_no_se(reference):
                return 'no'
            elif partner_country_code == 'SE' and sr.is_valid_structured_reference_no_se(reference):
                return 'se'
            elif sr.is_valid_structured_reference_iso(reference):
                return 'iso'
            else:
                return None

        if not payment['memo']:
            return False
        RmtInf = etree.Element('RmtInf')
        ref = sr.sanitize_structured_reference(payment['memo'])
        partner_country_code = payment.get('partner_country_code')
        reference_type = detect_reference_type(ref, partner_country_code)
        if reference_type:
            RmtInf.append(self._get_RmtInf_content(ref, reference_type))
        # Check whether we have a structured communication
        else:
            Ustrd = etree.SubElement(RmtInf, "Ustrd")
            Ustrd.text = sanitize_communication(payment['memo'].replace('&', '+'))
        return RmtInf

    def _get_organization_id_node_text(self, payment_method_code, postal_address):
        return self.company_id.iso20022_orgid_id

    def _get_company_PartyIdentification32(self, payment_method_line, postal_address=True, nm=True, issr=True, schme_nm=False, effective_payment_method_code=None):
        """ Returns a PartyIdentification32 element identifying the current journal's company
        """
        ret = []

        Nm = etree.Element("Nm")
        Nm.text = self.iso20022_get_company_name()
        ret.append(Nm)

        if postal_address:
            PstlAdr = self._get_PstlAdr(self.company_id.partner_id, payment_method_line, effective_payment_method_code=effective_payment_method_code)
            if PstlAdr is not None:
                ret.append(PstlAdr)

        if self.company_id.iso20022_orgid_id:
            Id = etree.Element("Id")
            OrgId = etree.SubElement(Id, "OrgId")
            company = self.company_id
            if payment_method_line.sepa_pain_version == "pain.001.001.09" and company.iso20022_lei:
                LEI = etree.Element("LEI")
                LEI.text = self.company_id.iso20022_lei
                OrgId.insert(0, LEI)
            Othr = etree.SubElement(OrgId, "Othr")
            _Id = etree.SubElement(Othr, "Id")
            _Id.text = sanitize_communication(self._get_organization_id_node_text(payment_method_line.code, postal_address))
            if issr and company.iso20022_orgid_issr:
                Issr = etree.SubElement(Othr, "Issr")
                Issr.text = sanitize_communication(company.iso20022_orgid_issr)
            if schme_nm:
                SchmeNm = etree.SubElement(Othr, "SchmeNm")
                Cd = etree.SubElement(SchmeNm, "Cd")
                Cd.text = schme_nm
            ret.append(Id)

        return ret

    # -------------------------------------------------------------------------
    # HELPERS/HOOKS
    # -------------------------------------------------------------------------

    def get_document_namespace(self, payment_method_line):
        namespace = 'pain.001.001.03'
        if payment_method_line.sepa_pain_version == 'pain.001.001.09':
            namespace = 'pain.001.001.09'
        return "urn:iso:std:iso:20022:tech:xsd:%s" % namespace

    def _get_schema_location(self, payment_method_line):
        # To override
        """
        Retrieve the XML Schema Location attributes for the payment file for validators.
        :return: A tuple containing the schemaInstance attribute and the location string
        or None if we don't need a schema location.
        """
        return None

    def _get_bic_tag(self, payment_method_line, effective_payment_method_code=None):
        # To override per pain version
        return 'BIC'

    def iso20022_get_company_name(self):
        company = self.company_id
        name_length = 35 if company.iso20022_initiating_party_name else 70
        name = company.iso20022_initiating_party_name or company.name
        return sanitize_communication(name[:name_length])

    def _get_SvcLvlText(self, payment_method_code):
        if payment_method_code == 'iso20022':
            return 'NURG'
        return None

    def _get_PstlAdr(self, partner_id, payment_method_line, effective_payment_method_code=None):
        payment_method_code = effective_payment_method_code or payment_method_line.code
        partner_address = self.get_postal_address(partner_id, payment_method_line, effective_payment_method_code=payment_method_code)
        if partner_address:
            PstlAdr = etree.Element("PstlAdr")
            Ctry = etree.SubElement(PstlAdr, "Ctry")
            Ctry.text = partner_address['country']
            # Some banks seem allergic to having the zip in a separate tag, so we do as before
            street = ", ".join(part for part in (partner_address.get('street'), partner_address.get('street2')) if part)
            if street:
                AdrLine = etree.SubElement(PstlAdr, "AdrLine")
                AdrLine.text = sanitize_communication(street[:70])
            if partner_address.get('zip') and partner_address.get('city'):
                AdrLine = etree.SubElement(PstlAdr, "AdrLine")
                AdrLine.text = sanitize_communication((partner_address['zip'] + " " + partner_address['city'])[:70])
            return PstlAdr
        return None

    def get_postal_address(self, partner_id, payment_method_line, effective_payment_method_code=None):
        pstl_addr_list = [address for address in partner_id._get_all_addr() if address['country']]
        if not pstl_addr_list:
            if partner_id.is_company:
                raise ValidationError(_('Partner %s has no country code defined.', partner_id.name))
            else:
                raise ValidationError(_('Employee %s has no country in their address.', partner_id.name))
        pstl_addr_list = [addr for addr in pstl_addr_list if addr['city']]
        if not pstl_addr_list:
            return None
        for addr_dict in pstl_addr_list:
            if addr_dict['contact_type'] == 'employee':
                return addr_dict
        return pstl_addr_list[0]

    def _skip_CdtrAgt(self, partner_bank, payment_method_line, effective_payment_method_code=None):
        return self.env.context.get('skip_bic', False) or not partner_bank.bank_bic

    def _get_RmtInf_content(self, ref, reference_type=''):
        return self.get_strd_tree(ref, cd='SCOR', issr='ISO')

    def _get_cleaned_bic_code(self, bank_account, payment_method_line, effective_payment_method_code=None):
        """
        Checks if the BIC code is matching the pattern from the XSD to avoid having files generated here that are
        refused by banks after.
        It also returns a cleaned version of the BIC as a convenient use.
        """
        if not bank_account.bank_bic:
            return
        regex = self._get_regex_for_bic_code(payment_method_line, effective_payment_method_code)
        if not re.match(regex, bank_account.bank_bic):
            raise UserError(_("The BIC code '%(bic_code)s' associated to the bank '%(bank)s' of bank account '%(account)s' "
                              "of partner '%(partner)s' does not respect the required convention.\n"
                              "It must contain 8 or 11 characters and match the following structure:\n"
                              "- 4 letters: institution code or bank code\n"
                              "- 2 letters: country code\n"
                              "- 2 letters or digits: location code\n"
                              "- 3 letters or digits: branch code, optional\n",
                              bic_code=bank_account.bank_bic, bank=bank_account.bank_name,
                              account=bank_account.sanitized_account_number, partner=bank_account.partner_id.name))
        return bank_account.bank_bic.replace(' ', '').upper()

    def _get_regex_for_bic_code(self, payment_method_line, effective_payment_method_code=None):
        return '[A-Z]{6,6}[A-Z2-9][A-NP-Z0-9]([A-Z0-9]{3,3}){0,1}'

    def _is_qr_iban(self, payment_dict):
        """ Tells if the bank account linked to the payment has a QR-IBAN account number.
        QR-IBANs are specific identifiers used in Switzerland as references in
        QR-codes. They are formed like regular IBANs, but are actually something
        different.
        """
        partner_bank = self.env['res.partner.bank'].browse(payment_dict['partner_bank_id'])
        company = self.env['account.journal'].browse(payment_dict['journal_id']).company_id
        if partner_bank.company_id.id not in (False, company.id):
            return False
        return self._is_bank_account_qr_iban(partner_bank)

    def _is_bank_account_qr_iban(self, bank_account):
        iban = bank_account.sanitized_account_number
        if iban[:2] not in ('CH', 'LI') or len(iban) < 9:
            return False
        iid = get_iban_part(iban, 'bank')
        return re.match(r'\d+', iid) \
            and 30000 <= int(iid) <= 31999  # Those values for iid are reserved for QR-IBANs only

    def get_strd_tree(self, ref, cd=None, prtry=None, issr=None):
        strd = etree.Element("Strd")
        CdtrRefInf = etree.SubElement(strd, "CdtrRefInf")
        Tp = etree.SubElement(CdtrRefInf, "Tp")
        CdOrPrtry = etree.SubElement(Tp, "CdOrPrtry")
        if cd:
            Cd = etree.SubElement(CdOrPrtry, "Cd")
            Cd.text = cd
        if prtry:
            Prtry = etree.SubElement(CdOrPrtry, "Prtry")
            Prtry.text = prtry
        if issr:
            Issr = etree.SubElement(Tp, "Issr")
            Issr.text = issr
        Ref = etree.SubElement(CdtrRefInf, "Ref")
        Ref.text = ref
        return strd
