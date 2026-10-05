from lxml import etree

from odoo import models

from odoo.addons.account.tools import dict_to_xml
from odoo.addons.account_edi_ubl_cii.models.account_edi_common import FloatFmt
from odoo.addons.l10n_pe_edi_withholding.tools.ubl_retention import PeRetention


class AccountEdiXmlUbl_Pe_Withholding(models.AbstractModel):
    _name = "account.edi.xml.ubl_pe_withholding"
    _inherit = 'account.edi.xml.ubl_pe'
    _description = "UBL Retention Document"
    _explanation = "Builds the SUNAT Comprobante de Retención (UBL 2.0) for vendor payments subject to IGV retention."

    # -------------------------------------------------------------------------
    # Export
    # -------------------------------------------------------------------------

    def _get_retention_document_nsmap(self):
        return {
            None: "urn:sunat:names:specification:ubl:peru:schema:xsd:Retention-1",
            'cac': "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
            'cbc': "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
            'sac': "urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1",
            'ext': "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
        }

    def _export_retention(self, payment):
        vals = {'payment': payment}
        document_node = self._get_retention_nodes(vals)
        xml_content = dict_to_xml(document_node, template=PeRetention, nsmap=self._get_retention_document_nsmap())
        return etree.tostring(xml_content, xml_declaration=True, encoding='UTF-8')

    def _get_retention_nodes(self, vals):
        self._add_retention_config_vals(vals)

        document_node = {}
        self._add_retention_header_nodes(document_node, vals)
        self._add_retention_signature_nodes(document_node, vals)
        self._add_retention_agent_party_nodes(document_node, vals)
        self._add_retention_receiver_party_nodes(document_node, vals)
        self._add_retention_monetary_totals_nodes(document_node, vals)
        self._add_retention_document_reference_nodes(document_node, vals)
        return document_node

    # -------------------------------------------------------------------------
    # Config
    # -------------------------------------------------------------------------

    def _add_retention_config_vals(self, vals):
        payment = vals['payment']
        company = payment.company_id
        breakdown = payment._l10n_pe_edi_get_retention_breakdown()
        vals.update({
            'document_type': 'retention',
            'supplier': company.partner_id.commercial_partner_id,
            'customer': payment.partner_id,
            'company': company,
            'currency_id': payment.currency_id,
            'company_currency_id': company.currency_id,
            'breakdown': breakdown,
        })

    # -------------------------------------------------------------------------
    # Header
    # -------------------------------------------------------------------------

    def _add_retention_header_nodes(self, document_node, vals):
        payment = vals['payment']
        # In Peru, you can only have one WTH tax and one WTH line per payment.
        tax = payment.withholding_line_ids.tax_id[:1]

        document_node.update({
            'cbc:UBLVersionID': {'_text': '2.0'},
            'cbc:CustomizationID': {'_text': '1.0'},
            'cbc:ID': {'_text': payment.l10n_pe_edi_retention_number or payment.name},
            'cbc:IssueDate': {'_text': payment.date},
            'sac:SUNATRetentionSystemCode': {'_text': '01'},
            'sac:SUNATRetentionPercent': {'_text': FloatFmt(abs(tax.amount), min_dp=2)},
            'cbc:Note': {'_text': payment.memo or ''},
        })

    def _add_retention_signature_nodes(self, document_node, vals):
        supplier = vals['supplier']
        document_node['cac:Signature'] = {
            'cbc:ID': {'_text': 'IDSignKG'},
            'cac:SignatoryParty': {
                'cac:PartyIdentification': {
                    'cbc:ID': {'_text': supplier.vat},
                },
                'cac:PartyName': {
                    'cbc:Name': {'_text': supplier.name.upper()},
                },
            },
            'cac:DigitalSignatureAttachment': {
                'cac:ExternalReference': {
                    'cbc:URI': {'_text': '#SignVX'},
                },
            },
        }

    # -------------------------------------------------------------------------
    # Parties
    # -------------------------------------------------------------------------

    def _add_retention_agent_party_nodes(self, document_node, vals):
        self._ubl_add_agent_party_node({**vals, 'document_node': document_node})

    def _add_retention_receiver_party_nodes(self, document_node, vals):
        self._ubl_add_receiver_party_node({**vals, 'document_node': document_node})

    # -------------------------------------------------------------------------
    # Monetary totals
    # -------------------------------------------------------------------------

    def _add_retention_monetary_totals_nodes(self, document_node, vals):
        payment = vals['payment']
        company_currency = vals['company_currency_id']
        retention_total_pen = sum(entry['bill_retention_pen'] for entry in vals['breakdown'])
        payment_amount_pen = payment.currency_id._convert(
            payment.amount, company_currency, company=payment.company_id, date=payment.date,
        )
        net_paid_pen = payment_amount_pen - retention_total_pen

        document_node.update({
            'cbc:TotalInvoiceAmount': {
                '_text': FloatFmt(retention_total_pen, min_dp=2),
                'currencyID': company_currency.name,
            },
            'sac:SUNATTotalPaid': {
                '_text': FloatFmt(net_paid_pen, min_dp=2),
                'currencyID': company_currency.name,
            },
        })

    # -------------------------------------------------------------------------
    # Document references (per reconciled bill)
    # -------------------------------------------------------------------------

    def _add_retention_document_reference_nodes(self, document_node, vals):
        payment = vals['payment']
        breakdown = vals['breakdown']
        if not breakdown:
            return

        company_currency = vals['company_currency_id']

        references = []
        for index, entry in enumerate(breakdown, start=1):
            bill = entry['bill']
            reference = {
                'cbc:ID': {
                    '_text': bill.name.replace(' ', ''),
                    'schemeID': bill.l10n_latam_document_type_id.code or '01',
                },
                'cbc:IssueDate': {'_text': bill.invoice_date},
                'cbc:TotalInvoiceAmount': {
                    '_text': FloatFmt(bill.amount_total, min_dp=2),
                    'currencyID': bill.currency_id.name,
                },
                'cac:Payment': {
                    'cbc:ID': {'_text': str(index)},
                    'cbc:PaidAmount': {
                        '_text': FloatFmt(entry['bill_paid_currency'], min_dp=2),
                        'currencyID': bill.currency_id.name,
                    },
                    'cbc:PaidDate': {'_text': payment.date},
                },
                'sac:SUNATRetentionInformation': {
                    'sac:SUNATRetentionAmount': {
                        '_text': FloatFmt(entry['bill_retention_pen'], min_dp=2),
                        'currencyID': company_currency.name,
                    },
                    'sac:SUNATRetentionDate': {'_text': payment.date},
                    'sac:SUNATNetTotalPaid': {
                        '_text': FloatFmt(entry['net_total_paid_pen'], min_dp=2),
                        'currencyID': company_currency.name,
                    },
                },
            }

            if bill.currency_id != company_currency:
                reference['sac:SUNATRetentionInformation']['cac:ExchangeRate'] = {
                    'cbc:SourceCurrencyCode': {'_text': bill.currency_id.name},
                    'cbc:TargetCurrencyCode': {'_text': company_currency.name},
                    'cbc:CalculationRate': {'_text': FloatFmt(entry['exchange_rate'], min_dp=6)},
                    'cbc:Date': {'_text': payment.date},
                }

            references.append(reference)

        document_node['sac:SUNATRetentionDocumentReference'] = references
