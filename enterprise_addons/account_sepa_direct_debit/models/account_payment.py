# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time

from datetime import datetime

from odoo import models, fields, api, _

from odoo.exceptions import UserError
from odoo.tools.business_data import street_split

from odoo.tools.float_utils import float_repr
from odoo.tools.xml_utils import create_xml_node, create_xml_node_chain
from odoo.addons.account_batch_payment.models.sepa_mapping import sanitize_communication
from lxml import etree


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    sdd_mandate_scheme = fields.Selection(related='mandate_id.sdd_scheme', readonly=True)

    @api.depends('currency_id')
    def _compute_alerts(self):
        super()._compute_alerts()
        for payment in self.filtered(lambda p: p.payment_method_code in ('sdd', 'sepa_direct_debit')):
            payment.alerts = {
                **(payment.alerts or {}),
                **payment.payment_method_id._get_sdd_alerts(payment.currency_id),
            }

    @api.model
    def split_node(self, string_node, max_size):
        # Split a string node according to its max_size in byte
        string_node = sanitize_communication(string_node)
        byte_node = string_node.encode()
        if len(byte_node) <= max_size:
            return string_node, ''
        while byte_node[max_size] >= 0x80 and byte_node[max_size] < 0xc0:
            max_size -= 1
        return byte_node[0:max_size].decode(), byte_node[max_size:].decode()

    def generate_xml(self, company_id, required_collection_date, askBatchBooking):
        """ Generates a SDD XML file containing the payments corresponding to this recordset,
        associating them to the given company, with the specified
        collection date.
        """
        version = self.journal_id.debit_sepa_pain_version
        if not version:
            raise UserError(_("Select a SEPA Direct Debit version before generating the XML."))
        document = etree.Element("Document", nsmap={None: f'urn:iso:std:iso:20022:tech:xsd:{version}', 'xsi': "http://www.w3.org/2001/XMLSchema-instance"})
        CstmrDrctDbtInitn = etree.SubElement(document, 'CstmrDrctDbtInitn')

        self._sdd_xml_gen_header(company_id, CstmrDrctDbtInitn)

        payments_per_journal = self._group_payments_per_bank_journal()
        payment_info_counter = 0
        for (journal, journal_payments) in payments_per_journal.items():
            journal_payments._sdd_xml_gen_payment_group(company_id, required_collection_date, askBatchBooking, payment_info_counter, journal, CstmrDrctDbtInitn)
            payment_info_counter += 1


        return etree.tostring(document, pretty_print=True, xml_declaration=True, encoding='utf-8')

    def _sdd_xml_gen_header(self, company_id, CstmrDrctDbtInitn):
        """ Generates the header of the SDD XML file.
        """
        GrpHdr = create_xml_node(CstmrDrctDbtInitn, 'GrpHdr')
        create_xml_node(GrpHdr, 'MsgId', str(time.time()))  # Using time makes sure the identifier is unique in an easy way
        create_xml_node(GrpHdr, 'CreDtTm', datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))
        create_xml_node(GrpHdr, 'NbOfTxs', str(len(self)))
        create_xml_node(GrpHdr, 'CtrlSum', float_repr(sum(x.amount for x in self), precision_digits=2))  # This sum ignores the currency, it is used as a checksum (see SEPA rulebook)
        InitgPty = create_xml_node(GrpHdr, 'InitgPty')
        create_xml_node(InitgPty, 'Nm', self.split_node(company_id.name, 70)[0])
        nodes = create_xml_node_chain(InitgPty, ['Id', 'OrgId', 'Othr', 'Id'], company_id.sdd_creditor_identifier)
        # Those countries need to use the format for Nordea
        if company_id.account_fiscal_country_id.code in {'SE', 'FI', 'DK', 'NO'}:
            Othr = nodes[2]
            create_xml_node_chain(Othr, ['SchmeNm', 'Cd'], 'CUST')

    def _sdd_xml_gen_address(self, root_node, partner, sdd_version):
        # Starting from November 2025, structured addresses will become the norm,
        # and unstructured addresses will not be allowed anymore.

        contact_address = partner._display_address(without_name=True, separator=' ')
        if contact_address:
            PstlAdr = create_xml_node(root_node, 'PstlAdr')
            if sdd_version == 'pain.008.001.02':
                if partner.country_id and partner.country_id.code:
                    create_xml_node(PstlAdr, 'Ctry', partner.country_id.code)
                n_line = 0
                while contact_address and n_line < 2:
                    left_split, right_split = self.split_node(contact_address, 70)
                    create_xml_node(PstlAdr, 'AdrLine', left_split)
                    contact_address = right_split
                    n_line = n_line + 1
            elif sdd_version == 'pain.008.001.08':
                if partner.street:
                    street_details = street_split(partner.street)
                    street_name = street_details['street_name'] if not partner.street2 else f"{street_details['street_name']}, {partner.street2}"
                    create_xml_node(PstlAdr, 'StrtNm', self.split_node(street_name, 70)[0])  # Number and box in street
                    if bldg_nb := street_details['street_number']:
                        create_xml_node(PstlAdr, 'BldgNb', bldg_nb)
                if partner.zip:
                    create_xml_node(PstlAdr, 'PstCd', partner.zip)
                if partner.city:
                    create_xml_node(PstlAdr, 'TwnNm', partner.city)
                else:
                    raise UserError(_('The debtor and creditor city name is a compulsary information when generating the SDD XML.'))
                if partner.state_id and partner.state_id.name:
                    create_xml_node(PstlAdr, 'CtrySubDvsn', partner.state_id.name)
                if partner.country_id and partner.country_id.code:
                    create_xml_node(PstlAdr, 'Ctry', partner.country_id.code)
                else:
                    raise UserError(_('The debtor and creditor country is a compulsary information when generating the SDD XML.'))
            else:
                raise UserError(_('A SEPA direct debit version should be selected to generate the addresses in the export file.'))

    def _sdd_xml_gen_payment_group(self, company_id, required_collection_date, askBatchBooking, payment_info_counter, journal, CstmrDrctDbtInitn):
        """ Generates a group of payments in the same PmtInfo node, provided
        that they share the same journal."""
        sdd_version = self.journal_id.debit_sepa_pain_version
        if not sdd_version:
            raise UserError(_('A SEPA direct debit version should be selected to generate the export file.'))

        PmtInf = create_xml_node(CstmrDrctDbtInitn, 'PmtInf')
        create_xml_node(PmtInf, 'PmtInfId', CstmrDrctDbtInitn.find('GrpHdr/MsgId').text + '/' + str(payment_info_counter))
        create_xml_node(PmtInf, 'PmtMtd', 'DD')
        create_xml_node(PmtInf, 'BtchBookg', askBatchBooking and 'true' or 'false')
        create_xml_node(PmtInf, 'NbOfTxs', str(len(self)))
        create_xml_node(PmtInf, 'CtrlSum', float_repr(sum(x.amount for x in self), precision_digits=2))  # This sum ignores the currency, it is used as a checksum (see SEPA rulebook)

        PmtTpInf = create_xml_node_chain(PmtInf, ['PmtTpInf', 'SvcLvl', 'Cd'], 'SEPA')[0]

        sdd_scheme = self[0].mandate_id.sdd_scheme or 'CORE'
        create_xml_node_chain(PmtTpInf, ['LclInstrm', 'Cd'], sdd_scheme)

        create_xml_node(PmtTpInf, 'SeqTp', 'RCUR')
        # Note: RCUR refers to the COLLECTION of payments, not the type of mandate used
        # This value is only used for informatory purpose.

        create_xml_node(PmtInf, 'ReqdColltnDt', fields.Date.from_string(required_collection_date).strftime("%Y-%m-%d"))
        Cdtr = create_xml_node_chain(PmtInf, ['Cdtr', 'Nm'], self.split_node(company_id.name, 70)[0])[0]  # SEPA regulation gives a maximum size of 70 characters for this field

        if sdd_version == 'pain.008.001.08':
            self._sdd_xml_gen_address(Cdtr, company_id.partner_id, sdd_version)

        create_xml_node_chain(PmtInf, ['CdtrAcct', 'Id', 'IBAN'], journal.bank_account_id.sanitized_account_number)

        if journal.bank_account_id and journal.bank_account_id.bank_bic:
            bic_tag = 'BIC' if sdd_version == 'pain.008.001.02' else 'BICFI'
            create_xml_node_chain(PmtInf, ['CdtrAgt', 'FinInstnId', bic_tag], journal.bank_account_id.bank_bic.replace(' ', '').upper())
        else:
            create_xml_node_chain(PmtInf, ['CdtrAgt', 'FinInstnId', 'Othr', 'Id'], "NOTPROVIDED")

        CdtrSchmeId_Othr = create_xml_node_chain(PmtInf, ['CdtrSchmeId', 'Id', 'PrvtId', 'Othr', 'Id'], company_id.sdd_creditor_identifier)[-2]
        create_xml_node_chain(CdtrSchmeId_Othr, ['SchmeNm', 'Prtry'], 'SEPA')

        for payment in self:
            payment.sdd_xml_gen_payment(company_id, payment.partner_id, self.split_node(payment.name, 35)[0], PmtInf)

    def sdd_xml_gen_payment(self, company_id, partner, end2end_name, PmtInf):
        """ Appends to a SDD XML file being generated all the data related to the
        payments of a given partner.
        """
        # The two following conditions should never execute.
        # They are here to be sure future modifications won't ever break everything.
        if company_id not in self.company_id.parent_ids:
            raise UserError(_("Trying to generate a Direct Debit XML file containing payments from another company than that file's creditor."))

        if self.payment_method_line_id.code not in self.payment_method_id._get_sdd_payment_method_code():
            raise UserError(_("Trying to generate a Direct Debit XML for payments coming from another payment method than SEPA Direct Debit."))

        if not self.mandate_id:
            raise UserError(_("The payment must be linked to a SEPA Direct Debit mandate in order to generate a Direct Debit XML."))

        if self.mandate_id.state == 'revoked':
            raise UserError(_("The SEPA Direct Debit mandate associated to the payment has been revoked and cannot be used anymore."))

        sdd_version = self.journal_id.debit_sepa_pain_version
        if not sdd_version:
            raise UserError(_('A SEPA direct debit version should be selected to generate the export file.'))

        DrctDbtTxInf = create_xml_node_chain(PmtInf, ['DrctDbtTxInf', 'PmtId', 'EndToEndId'], end2end_name)[0]

        InstdAmt = create_xml_node(DrctDbtTxInf, 'InstdAmt', float_repr(self.amount, precision_digits=2))
        InstdAmt.attrib['Ccy'] = self.currency_id.name

        MndtRltdInf = create_xml_node_chain(DrctDbtTxInf, ['DrctDbtTx', 'MndtRltdInf', 'MndtId'], self.mandate_id.name)[-2]
        create_xml_node(MndtRltdInf, 'DtOfSgntr', fields.Date.to_string(self.mandate_id.start_date))

        if self.mandate_id.partner_bank_id.bank_bic:
            bic_tag = 'BIC' if sdd_version == 'pain.008.001.02' else 'BICFI'
            create_xml_node_chain(DrctDbtTxInf, ['DbtrAgt', 'FinInstnId', bic_tag], self.mandate_id.partner_bank_id.bank_bic.replace(' ', '').upper())
        else:
            create_xml_node_chain(DrctDbtTxInf, ['DbtrAgt', 'FinInstnId', 'Othr', 'Id'], 'NOTPROVIDED')

        debtor_name = self.mandate_id.partner_bank_id.holder_name or partner.name or partner.parent_id.name
        Dbtr = create_xml_node_chain(DrctDbtTxInf, ['Dbtr', 'Nm'], self.split_node(debtor_name, 70)[0])[0]

        self._sdd_xml_gen_address(Dbtr, partner, sdd_version)

        if debtor_id := self.mandate_id.sdd_debtor_id_code:
            chain_keys = ['Id', 'PrvtId', 'Othr', 'Id']
            if partner.commercial_partner_id.is_company:
                chain_keys = ['Id', 'OrgId', 'Othr', 'Id']
            create_xml_node_chain(Dbtr, chain_keys, debtor_id)

        create_xml_node_chain(DrctDbtTxInf, ['DbtrAcct', 'Id', 'IBAN'], self.mandate_id.partner_bank_id.sanitized_account_number)

        if self.memo:
            create_xml_node_chain(DrctDbtTxInf, ['RmtInf', 'Ustrd'], self.split_node(self.memo, 140)[0])

    def _group_payments_per_bank_journal(self):
        """ Groups the payments of this recordset per associated journal, in a dictionnary of recordsets.
        """
        rslt = {}
        for payment in self:
            if rslt.get(payment.journal_id, False):
                rslt[payment.journal_id] += payment
            else:
                rslt[payment.journal_id] = payment
        return rslt
