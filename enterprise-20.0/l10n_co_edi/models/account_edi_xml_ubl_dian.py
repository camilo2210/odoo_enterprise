import copy
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta
from hashlib import sha384
from zoneinfo import ZoneInfo

from lxml import etree
from stdnum.co.nit import compact

from odoo import api, models, fields
from odoo.exceptions import UserError
from odoo.tools import cleanup_xml_node, frozendict
from odoo.addons.account_edi_ubl_cii.models.account_edi_common import FloatFmt
from odoo.addons.account.tools import dict_to_xml
from odoo.addons.l10n_co.tools.partner_identifiers import CO_NIT_DIAN_CODE
from odoo.addons.l10n_co_edi import xml_utils
from odoo.addons.l10n_co_edi.models.res_partner import FINAL_CONSUMER_VAT
from odoo.addons.l10n_co_edi.models.account_invoice import L10N_CO_EDI_TYPE


_logger = logging.getLogger(__name__)


COUNTRIES_ES = {
    "AF": "Afganistán",
    "AX": "Åland",
    "AL": "Albania",
    "DE": "Alemania",
    "AD": "Andorra",
    "AO": "Angola",
    "AI": "Anguila",
    "AQ": "Antártida",
    "AG": "Antigua y Barbuda",
    "SA": "Arabia Saudita",
    "DZ": "Argelia",
    "AR": "Argentina",
    "AM": "Armenia",
    "AW": "Aruba",
    "AU": "Australia",
    "AT": "Austria",
    "AZ": "Azerbaiyán",
    "BS": "Bahamas",
    "BD": "Bangladés",
    "BB": "Barbados",
    "BH": "Baréin",
    "BE": "Bélgica",
    "BZ": "Belice",
    "BJ": "Benín",
    "BM": "Bermudas",
    "BY": "Bielorrusia",
    "BO": "Bolivia",
    "BQ": "Bonaire, San Eustaquio y Saba",
    "BA": "Bosnia y Herzegovina",
    "BW": "Botsuana",
    "BR": "Brasil",
    "BN": "Brunéi",
    "BG": "Bulgaria",
    "BF": "Burkina Faso",
    "BI": "Burundi",
    "BT": "Bután",
    "CV": "Cabo Verde",
    "KH": "Camboya",
    "CM": "Camerún",
    "CA": "Canadá",
    "QA": "Catar",
    "TD": "Chad",
    "CL": "Chile",
    "CN": "China",
    "CY": "Chipre",
    "CO": "Colombia",
    "KM": "Comoras",
    "KP": "Corea del Norte",
    "KR": "Corea del Sur",
    "CI": "Costa de Marfil",
    "CR": "Costa Rica",
    "HR": "Croacia",
    "CU": "Cuba",
    "CW": "Curazao",
    "DK": "Dinamarca",
    "DM": "Dominica",
    "EC": "Ecuador",
    "EG": "Egipto",
    "SV": "El Salvador",
    "AE": "Emiratos Árabes Unidos",
    "ER": "Eritrea",
    "SK": "Eslovaquia",
    "SI": "Eslovenia",
    "ES": "España",
    "US": "Estados Unidos",
    "EE": "Estonia",
    "ET": "Etiopía",
    "PH": "Filipinas",
    "FI": "Finlandia",
    "FJ": "Fiyi",
    "FR": "Francia",
    "GA": "Gabón",
    "GM": "Gambia",
    "GE": "Georgia",
    "GH": "Ghana",
    "GI": "Gibraltar",
    "GD": "Granada",
    "GR": "Grecia",
    "GL": "Groenlandia",
    "GP": "Guadalupe",
    "GU": "Guam",
    "GT": "Guatemala",
    "GF": "Guayana Francesa",
    "GG": "Guernsey",
    "GN": "Guinea",
    "GW": "Guinea-Bisáu",
    "GQ": "Guinea Ecuatorial",
    "GY": "Guyana",
    "HT": "Haití",
    "HN": "Honduras",
    "HK": "Hong Kong",
    "HU": "Hungría",
    "IN": "India",
    "ID": "Indonesia",
    "IQ": "Irak",
    "IR": "Irán",
    "IE": "Irlanda",
    "BV": "Isla Bouvet",
    "IM": "Isla de Man",
    "CX": "Isla de Navidad",
    "IS": "Islandia",
    "KY": "Islas Caimán",
    "CC": "Islas Cocos",
    "CK": "Islas Cook",
    "FO": "Islas Feroe",
    "GS": "Islas Georgias del Sur y Sandwich del Sur",
    "HM": "Islas Heard y McDonald",
    "FK": "Islas Malvinas",
    "MP": "Islas Marianas del Norte",
    "MH": "Islas Marshall",
    "PN": "Islas Pitcairn",
    "SB": "Islas Salomón",
    "TC": "Islas Turcas y Caicos",
    "UM": "Islas ultramarinas de Estados Unidos",
    "VG": "Islas Vírgenes Británicas",
    "VI": "Islas Vírgenes de los Estados Unidos",
    "IL": "Israel",
    "IT": "Italia",
    "JM": "Jamaica",
    "JP": "Japón",
    "JE": "Jersey",
    "JO": "Jordania",
    "KZ": "Kazajistán",
    "KE": "Kenia",
    "KG": "Kirguistán",
    "KI": "Kiribati",
    "XK": "Kosovo",
    "KW": "Kuwait",
    "LA": "Laos",
    "LS": "Lesoto",
    "LV": "Letonia",
    "LB": "Líbano",
    "LR": "Liberia",
    "LY": "Libia",
    "LI": "Liechtenstein",
    "LT": "Lituania",
    "LU": "Luxemburgo",
    "MO": "Macao",
    "MK": "Macedonia",
    "MG": "Madagascar",
    "MY": "Malasia",
    "MW": "Malaui",
    "MV": "Maldivas",
    "ML": "Malí",
    "MT": "Malta",
    "MA": "Marruecos",
    "MQ": "Martinica",
    "MU": "Mauricio",
    "MR": "Mauritania",
    "YT": "Mayotte",
    "MX": "México",
    "FM": "Micronesia",
    "MD": "Moldavia",
    "MC": "Mónaco",
    "MN": "Mongolia",
    "ME": "Montenegro",
    "MS": "Montserrat",
    "MZ": "Mozambique",
    "MM": "Myanmar",
    "NA": "Namibia",
    "NR": "Nauru",
    "NP": "Nepal",
    "NI": "Nicaragua",
    "NE": "Níger",
    "NG": "Nigeria",
    "NU": "Niue",
    "NF": "Norfolk",
    "NO": "Noruega",
    "NC": "Nueva Caledonia",
    "NZ": "Nueva Zelanda",
    "OM": "Omán",
    "NL": "Países Bajos",
    "PK": "Pakistán",
    "PW": "Palaos",
    "PS": "Palestina",
    "PA": "Panamá",
    "PG": "Papúa Nueva Guinea",
    "PY": "Paraguay",
    "PE": "Perú",
    "PF": "Polinesia Francesa",
    "PL": "Polonia",
    "PT": "Portugal",
    "PR": "Puerto Rico",
    "GB": "Reino Unido",
    "EH": "República Árabe Saharaui Democrática",
    "CF": "República Centroafricana",
    "CZ": "República Checa",
    "CG": "República del Congo",
    "CD": "República Democrática del Congo",
    "DO": "República Dominicana",
    "RE": "Reunión",
    "RW": "Ruanda",
    "RO": "Rumania",
    "RU": "Rusia",
    "WS": "Samoa",
    "AS": "Samoa Americana",
    "BL": "San Bartolomé",
    "KN": "San Cristóbal y Nieves",
    "SM": "San Marino",
    "MF": "San Martín",
    "PM": "San Pedro y Miquelón",
    "VC": "San Vicente y las Granadinas",
    "SH": "Santa Elena, Ascensión y Tristán de Acuña",
    "LC": "Santa Lucía",
    "ST": "Santo Tomé y Príncipe",
    "SN": "Senegal",
    "RS": "Serbia",
    "SC": "Seychelles",
    "SL": "Sierra Leona",
    "SG": "Singapur",
    "SX": "Sint Maarten",
    "SY": "Siria",
    "SO": "Somalia",
    "LK": "Sri Lanka",
    "SZ": "Suazilandia",
    "ZA": "Sudáfrica",
    "SD": "Sudán",
    "SS": "Sudán del Sur",
    "SE": "Suecia",
    "CH": "Suiza",
    "SR": "Surinam",
    "SJ": "Svalbard y Jan Mayen",
    "TH": "Tailandia",
    "TW": "Taiwán (República de China)",
    "TZ": "Tanzania",
    "TJ": "Tayikistán",
    "IO": "Territorio Británico del Océano Índico",
    "TF": "Tierras Australes y Antárticas Francesas",
    "TL": "Timor Oriental",
    "TG": "Togo",
    "TK": "Tokelau",
    "TO": "Tonga",
    "TT": "Trinidad y Tobago",
    "TN": "Túnez",
    "TM": "Turkmenistán",
    "TR": "Turquía",
    "TV": "Tuvalu",
    "UA": "Ucrania",
    "UG": "Uganda",
    "UY": "Uruguay",
    "UZ": "Uzbekistán",
    "VU": "Vanuatu",
    "VA": "Vaticano, Ciudad del",
    "VE": "Venezuela",
    "VN": "Vietnam",
    "WF": "Wallis y Futuna",
    "YE": "Yemen",
    "DJ": "Yibuti",
    "ZM": "Zambia",
    "ZW": "Zimbabue",
}


class AccountEdiXmlUbl_Dian(models.AbstractModel):
    """ The technical documentation is available on the dian.gov.co website. Latest version is 1.9:
    https://www.dian.gov.co/impuestos/factura-electronica/Documents/Anexo-Tecnico-Factura-Electronica-de-Venta-vr-1-9.pdf
    """
    _name = 'account.edi.xml.ubl_dian'
    _inherit = ['account.edi.xml.ubl_21']
    _description = "UBL DIAN"

    # -------------------------------------------------------------------------
    # EXPORT
    # -------------------------------------------------------------------------

    def _export_invoice_filename(self, invoice):
        # OVERRIDE account.edi.xml.ubl_21
        return 'dian_%s.xml' % (re.sub(r'[\W_]', '', invoice.name))

    def _export_invoice(self, invoice):
        # EXTENDS account.edi.xml.ubl_21
        xml, errors = super()._export_invoice(invoice)

        certificates_sudo = invoice.company_id.sudo().l10n_co_edi_certificate_ids
        if not certificates_sudo:
            raise UserError(self.env._("No DIAN certificate is configured on the company."))
        cert_sudo = certificates_sudo[-1]
        root = etree.fromstring(xml)

        self._dian_fill_signed_info_and_signature(root, cert_sudo)
        return etree.tostring(root, encoding='UTF-8'), errors

    def _get_document_nsmap(self, vals):
        nsmap = super()._get_document_nsmap(vals)
        nsmap.update({
            'ds': "http://www.w3.org/2000/09/xmldsig#",
            'sts': self._get_sts_namespace(vals),
            'xades': "http://uri.etsi.org/01903/v1.3.2#",
            'xades141': "http://uri.etsi.org/01903/v1.4.1#",
            'xsi': "http://www.w3.org/2001/XMLSchema-instance",
            **self._get_document_extensions_nsmap(vals),
        })
        return nsmap

    def _add_invoice_config_vals(self, vals):
        super()._add_invoice_config_vals(vals)

        invoice = vals['invoice']

        vals.update({
            'document_type': 'debit_note' if invoice.l10n_co_edi_debit_note
                else 'credit_note' if invoice.is_refund()
                else 'invoice',

            'l10n_co_edi_type': invoice.l10n_co_edi_type,
            'l10n_co_edi_operation_type': invoice.l10n_co_edi_operation_type,
            'l10n_co_edi_identifier_type': invoice.l10n_co_edi_identifier_type,
            'l10n_co_edi_is_support_document': invoice.l10n_co_edi_is_support_document,

            'name': invoice.name,
            'prepayments': invoice._l10n_co_edi_get_invoice_prepayments(),
        })
        self._add_document_config_vals(vals)

    def _add_document_config_vals(self, vals):
        vals.update({
            # All amounts are reported in company currency (which should be COP)
            # If the invoice is in foreign currency, we just provide the exchange rate in PaymentExchangeRate.
            'use_company_currency': True,

            # Fixed tax (e.g. IBUA) amounts should be accounted not as AllowanceCharges but as taxes
            'fixed_taxes_as_allowance_charges': False,
        })

        mode = 'invoice' if vals['l10n_co_edi_identifier_type'] != 'cuds' else 'bill'
        vals['l10n_co_edi_operation_mode'] = vals['company'].l10n_co_edi_operation_mode_ids.filtered(
            lambda operation_mode: operation_mode.dian_software_operation_mode == mode
        )

    def _add_invoice_base_lines_vals(self, vals):
        # EXTEND account.edi.xml.ubl_21
        super()._add_invoice_base_lines_vals(vals)

        AccountTax = self.env['account.tax']
        company = vals['invoice'].company_id
        base_lines = vals['base_lines']

        for base_line in base_lines:
            self._transform_iva_withholding_base_amount(base_line)

        # Mark negative lines as global discounts and redistribute them across positive lines.
        for base_line in base_lines:
            is_negative = base_line['tax_details']['raw_total_excluded_currency'] < 0.0
            if is_negative and not base_line['special_type']:
                base_line['special_type'] = 'global_discount'

        vals['base_lines'] = AccountTax._dispatch_global_discount_lines(base_lines, company)
        AccountTax._squash_global_discount_lines(vals['base_lines'], company)
        AccountTax._add_and_round_raw_gross_total_excluded_and_discount(vals['base_lines'], company, account_discount_base_lines=True, apply_strict_tolerance=True)
        AccountTax._add_and_round_raw_gross_total_excluded_and_discount(vals['base_lines'], company, account_discount_base_lines=True, apply_strict_tolerance=True, in_foreign_currency=False)

    def _transform_iva_withholding_base_amount(self, base_line):
        # Taxes with type '05' are retention taxes (15 %) that apply on the *tax amount* of a regular VAT tax
        # Hence, the tax "15% RteVAT 19%" is encoded as a -2.85% tax in Odoo

        # We now transform those taxes back to have their proper base amounts.
        # On invoice line, look at the sibling tax detail '01' and extract its exact tax amount.

        # see constraint DSAY05: the Taxable Amount for the taxes with type '05' should be equal to
        # the Tax Amount on which the taxes with type '01' were applied

        def get_tax_data(l10n_co_edi_type_code):
            return next(
                (
                    tax_data
                    for tax_data in base_line['tax_details']['taxes_data']
                    if tax_data['tax'].l10n_co_edi_type.code == l10n_co_edi_type_code
                ),
                None,
            )

        tax_data_05 = get_tax_data('05')
        if tax_data_05:
            tax_data_01 = get_tax_data('01')
            tax_data_05['base_amount'] = tax_data_01['tax_amount'] if tax_data_01 else 0.0

    def _add_invoice_tax_grouping_function_vals(self, vals):
        invoice = vals['invoice']
        self._add_document_tax_grouping_function_vals(vals)

        total_grouping_function = vals['total_grouping_function']
        tax_grouping_function = vals['tax_grouping_function']

        def total_grouping_function_excluding_support_document_and_free_sample(base_line, tax_data):
            tax = tax_data and tax_data['tax']

            # For support document, only the taxes IVA (01), ReteICA (05), ReteRenta (06) should be included
            if invoice.l10n_co_edi_is_support_document and tax and tax.l10n_co_edi_type.code not in {'01', '05', '06'}:
                return None

            # Exclude Free Sample taxes
            if tax and tax.l10n_co_edi_type.code == 'ZY':
                return None

            return total_grouping_function(base_line, tax_data)

        def tax_grouping_function_excluding_support_document_and_free_sample(base_line, tax_data):
            tax = tax_data and tax_data['tax']

            # For support document, only the taxes IVA (01), ReteICA (05), ReteRenta (06) should be included
            if invoice.l10n_co_edi_is_support_document and tax and tax.l10n_co_edi_type.code not in {'01', '05', '06'}:
                return None

            # Exclude Free Sample taxes
            if tax and tax.l10n_co_edi_type.code == 'ZY':
                return None

            return tax_grouping_function(base_line, tax_data)

        vals['total_grouping_function'] = total_grouping_function_excluding_support_document_and_free_sample
        vals['tax_grouping_function'] = tax_grouping_function_excluding_support_document_and_free_sample

    def _add_document_tax_grouping_function_vals(self, vals):
        def total_grouping_function(base_line, tax_data):
            tax = tax_data and tax_data['tax']

            if tax and tax.l10n_co_edi_type.retention:
                return None

            # For support document, only the taxes IVA (01), ReteICA (05), ReteRenta (06) should be included
            if vals['l10n_co_edi_identifier_type'] == 'cuds' and tax and tax.l10n_co_edi_type.code not in {'01', '05', '06'}:
                return None

            return True

        def tax_grouping_function(base_line, tax_data):
            """ Group the taxes by colombian type using the (tax.amount, tax.amount_type, tax.l10n_co_edi_type) """
            tax = tax_data and tax_data['tax']

            if not tax:
                return None

            # For support document, only the taxes IVA (01), ReteICA (05), ReteRenta (06) should be included
            if vals['l10n_co_edi_identifier_type'] == 'cuds' and tax and tax.l10n_co_edi_type.code not in {'01', '05', '06'}:
                return None

            if tax.l10n_co_edi_type.code == '32':
                # ICL (tax on alcoholic beverages) is a tax based on the alcohol percentage in the bottle.
                # It is always sent in LTRs according to the specifications listed in the DIAN documentation.
                amount = tax.amount / base_line['product_id'].l10n_co_edi_ref_nominal_tax * base_line['quantity']
            elif tax.l10n_co_edi_type.code == '34':
                # IBUA (tax on sugar beverages) is a tax based on the quantity of sugar per 100mL
                # e.g. if the quantity of sugar per 100mL is > 10gr -> tax of 35$ per 100mL
                # In Odoo, we use fixed taxes and a field for the volume of the product: l10n_co_edi_ref_nominal_tax
                # Hence, we can infer the rate per 100mL of the tax
                amount = tax.amount * 100 / base_line['product_id'].l10n_co_edi_ref_nominal_tax
            elif tax.l10n_co_edi_type.code == '05':
                # Taxes with type '05' are retention taxes (15 %) that apply on the *tax amount* of a regular VAT tax
                # Hence, the tax "15% RteVAT 19%" is encoded as a -2.85% tax in Odoo. However, in the UBL, it should appear as 15%.
                # Thus, we find the percentage of the IVA tax on the same line, and divide by it.
                if iva_tax := next(
                    (
                        tax_data['tax']
                        for tax_data in base_line['tax_details']['taxes_data']
                        if tax_data['tax'].l10n_co_edi_type.code == '01'
                    ),
                    None,
                ):
                    amount = tax.amount * 100 / iva_tax.amount
            else:
                amount = tax.amount

            return {
                'l10n_co_edi_type': tax.l10n_co_edi_type,
                'amount_type': tax.amount_type,
                'amount': amount,
                'is_withholding_tax': tax.l10n_co_edi_type.retention,
            }

        vals['total_grouping_function'] = total_grouping_function
        vals['tax_grouping_function'] = tax_grouping_function

    # -------------------------------------------------------------------------
    # EXPORT: Helpers
    # -------------------------------------------------------------------------

    def _add_document_cufe_cude_cuds_vals(self, document_node, vals):
        def format_float(amount, precision_digits=vals['currency_dp']):
            return self.format_float(amount, precision_digits)

        def get_tax_amount(l10n_co_edi_type_code):
            """ Get the tax amount associated with a given colombian tax type code. """
            def grouping_function(base_line, tax_data):
                return tax_data and tax_data['tax'].l10n_co_edi_type.code == l10n_co_edi_type_code

            base_lines_aggregated_tax_details = self.env['account.tax']._aggregate_base_lines_tax_details(
                vals['base_lines'],
                grouping_function
            )
            aggregated_tax_details = self.env['account.tax']._aggregate_base_lines_aggregated_values(
                base_lines_aggregated_tax_details
            )
            if True in aggregated_tax_details:
                return aggregated_tax_details[True]['tax_amount']
            return 0.0

        if vals['l10n_co_edi_identifier_type'] in ('cude', 'cuds'):
            key = vals['l10n_co_edi_operation_mode'].dian_software_security_code
        else:
            key = vals['journal'].l10n_co_edi_technical_key

        monetary_total_tag = 'cac:LegalMonetaryTotal' if vals['document_type'] in {'invoice', 'credit_note'} else 'cac:RequestedMonetaryTotal'

        cufe_cude_cuds_vals = {
            'invoice_id': document_node['cbc:ID']['_text'],
            'issue_date': document_node['cbc:IssueDate']['_text'],
            'issue_time': document_node['cbc:IssueTime']['_text'],  # invoice time (including tz)
            'line_extension_amount': document_node[monetary_total_tag]['cbc:LineExtensionAmount']['_text'],
            'tax_code_01': '01',
            'ValImp1': format_float(get_tax_amount('01')),
            'tax_code_04': '04',
            'ValImp2': format_float(get_tax_amount('04')),
            'tax_code_03': '03',
            'ValImp3': format_float(get_tax_amount('03')),
            'ValTotFac': document_node[monetary_total_tag]['cbc:PayableAmount']['_text'],
            'supplier_company_id': vals['supplier']._get_vat_without_verification_code(),
            'customer_company_id': vals['customer']._get_vat_without_verification_code(),
            'key': key or 'missing_key',
            'profile_execution_id': document_node['cbc:ProfileExecutionID']['_text'],
        }
        if vals['l10n_co_edi_identifier_type'] == 'cuds':
            [cufe_cude_cuds_vals.pop(k) for k in ('tax_code_04', 'ValImp2', 'tax_code_03', 'ValImp3')]

        vals['cufe_cude_cuds'] = "".join(str(res) for res in cufe_cude_cuds_vals.values())
        vals['uuid'] = sha384(vals['cufe_cude_cuds'].encode()).hexdigest()

    @api.model
    def _is_free_invoice_line(self, base_line):
        return any(tax.l10n_co_edi_type.code == 'ZY' for tax in base_line['tax_ids'])

    # -------------------------------------------------------------------------
    # EXPORT: Templates for invoice header nodes
    # -------------------------------------------------------------------------

    def _get_invoice_node(self, vals):
        document_node = super()._get_invoice_node(vals)
        self._add_invoice_payment_exchange_rate_node(document_node, vals)
        self._add_document_cufe_cude_cuds_vals(document_node, vals)
        self._add_document_uuid_node(document_node, vals)
        self._add_document_signature_vals(vals)
        self._add_document_extensions_node(document_node, vals)
        return document_node

    def _add_invoice_header_nodes(self, document_node, vals):
        super()._add_invoice_header_nodes(document_node, vals)
        self._add_document_header_nodes(document_node, vals)

        invoice = vals['invoice']
        if vals['l10n_co_edi_identifier_type'] != 'cuds':
            customization_id = invoice.l10n_co_edi_operation_type
        else:
            customization_id = '10' if vals['supplier'].country_code == 'CO' else '11'

        document_node.update({
            'cbc:CustomizationID': {'_text': customization_id},
            'cbc:ProfileID': {'_text': invoice._l10n_co_edi_get_electronic_invoice_type_info()},
            'cbc:InvoiceTypeCode': {'_text': self._dian_get_document_type_code(invoice)} if vals['document_type'] == 'invoice' else None,
            'cbc:CreditNoteTypeCode': {'_text': self._dian_get_document_type_code(invoice)} if vals['document_type'] == 'credit_note' else None,
            'cbc:IssueDate': {'_text': invoice.l10n_co_edi_post_time.date().isoformat()},
            'cbc:IssueTime': {'_text': invoice.l10n_co_edi_post_time.strftime("%H:%M:%S-05:00")},
            'cac:InvoicePeriod': {
                'cbc:StartDate': {'_text': invoice.invoice_date},
                'cbc:EndDate': {'_text': invoice.invoice_date},
            } if invoice.l10n_co_edi_operation_type in ['22', '32'] else None,
            'cac:DiscrepancyResponse': (
                {
                    'cbc:ReferenceID': {'_text': invoice.reversed_entry_id.name},
                    'cbc:ResponseCode': {'_text': invoice.l10n_co_edi_description_code_credit},
                    'cbc:Description': {'_text': dict(invoice._fields['l10n_co_edi_description_code_credit'].selection).get(invoice.l10n_co_edi_description_code_credit)}
                }
                if invoice.l10n_co_edi_operation_type == '20' or invoice.move_type == 'in_refund'
                else {
                    'cbc:ReferenceID': {'_text': invoice.debit_origin_id.name},
                    'cbc:ResponseCode': {'_text': invoice.l10n_co_edi_description_code_debit},
                    'cbc:Description': {'_text': dict(invoice._fields['l10n_co_edi_description_code_debit'].selection).get(invoice.l10n_co_edi_description_code_debit)}
                }
                if invoice.l10n_co_edi_operation_type == '30'
                else None
            ),
            'cac:AdditionalDocumentReference': {
                'cbc:ID': {'_text': invoice.name},
                'cbc:UUID': {
                    'schemeName': '2' if invoice.company_id.l10n_co_edi_test_environment else '1',
                },
                'cbc:IssueDate': {'_text': invoice.invoice_date},
            } if invoice.l10n_co_edi_is_unsent_contingency_invoice else None,
        })

        document_node['cac:OrderReference']['cbc:SalesOrderID'] = None

        document_node['cac:BillingReference'] = self._get_billing_reference_node(invoice)

        document_node.update({
            'cac:PrepaidPayment': [
                {
                    'cbc:ID': {'_text': p['name']},
                    'cbc:PaidAmount': {
                        '_text': self.format_float(p['amount'], invoice.company_currency_id.decimal_places),
                        'currencyID': invoice.company_currency_id.name
                    },
                    'cbc:ReceivedDate': {'_text': p['date']},
                }
                for p in vals['prepayments']
            ] if vals['document_type'] != 'credit_note' else None,
        })

        document_node['cac:OrderReference']['cbc:SalesOrderID'] = None

        if vals['document_type'] == 'debit_note':
            document_node['cbc:BuyerReference']['_text'] = None

    def _add_document_header_nodes(self, document_node, vals):
        line_count_numeric = len([base_line for base_line in vals['base_lines'] if not base_line['special_mode'] and not base_line.get('is_tip')])

        document_node.update({
            'xsi:schemaLocation': {
                'invoice': "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2     "
                    "http://docs.oasis-open.org/ubl/os-UBL-2.1/xsd/maindoc/UBL-Invoice-2.1.xsd",
                'credit_note': "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2    "
                    "http://docs.oasis-open.org/ubl/os-UBL-2.1/xsd/maindoc/UBL-CreditNote-2.1.xsd",
                'debit_note': "urn:oasis:names:specification:ubl:schema:xsd:DebitNote-2    "
                    "http://docs.oasis-open.org/ubl/os-UBL-2.1/xsd/maindoc/UBL-DebitNote-2.1.xsd"
            }[vals['document_type']],
            'cbc:UBLVersionID': {'_text': 'UBL 2.1'},
            'cbc:ProfileExecutionID': {'_text': '2' if vals['company'].l10n_co_edi_test_environment else '1'},
            'cbc:UUID': {
                'schemeID': '2' if vals['company'].l10n_co_edi_test_environment else '1',
                'schemeName': {
                    'cude': 'CUDE-SHA384',
                    'cuds': 'CUDS-SHA384',
                }.get(vals['l10n_co_edi_identifier_type'], 'CUFE-SHA384'),
            },
            'cbc:DocumentCurrencyCode': {
                '_text': "COP",
                'listAgencyID': "6",
                'listAgencyName': "United Nations Economic Commission for Europe",
                'listID': "ISO 4217 Alpha",
            },
            'cbc:LineCountNumeric': {'_text': line_count_numeric},
        })

    def _add_invoice_accounting_supplier_party_nodes(self, document_node, vals):
        super()._add_invoice_accounting_supplier_party_nodes(document_node, vals)
        document_node['cac:AccountingSupplierParty']['cbc:AdditionalAccountID'] = {
            '_text': vals['supplier']._l10n_co_edi_get_partner_type()
        }

    def _add_invoice_accounting_customer_party_nodes(self, document_node, vals):
        super()._add_invoice_accounting_customer_party_nodes(document_node, vals)
        document_node['cac:AccountingCustomerParty']['cbc:AdditionalAccountID'] = {
            '_text': vals['customer'].commercial_partner_id._l10n_co_edi_get_partner_type()
        }

    def _add_invoice_delivery_nodes(self, document_node, vals):
        pass

    def _add_invoice_payment_means_nodes(self, document_node, vals):
        # OVERRIDE account.edi.xml.ubl_21
        invoice = vals['invoice']
        document_node['cac:PaymentMeans'] = {
            'cbc:ID': {'_text': '1' if invoice.l10n_co_edi_is_direct_payment else '2'},
            'cbc:PaymentMeansCode': {'_text': invoice.l10n_co_edi_payment_option_id.code},
            'cbc:PaymentDueDate': {'_text': invoice.invoice_date_due},
            'cbc:PaymentID': {'_text': invoice.payment_reference or invoice.name},
        }

    def _add_document_uuid_node(self, document_node, vals):
        # Add CUFE/CUDE/CUDS
        document_node['cbc:UUID']['_text'] = vals['uuid']  # as stated in the "Anexo Tecnico" file, SHA384 must be used

        if 'invoice' in vals and vals['invoice'].l10n_co_edi_is_unsent_contingency_invoice:
            document_node['cac:AdditionalDocumentReference']['cbc:UUID']['_text'] = document_node['cbc:UUID']['_text']

    def _add_invoice_payment_exchange_rate_node(self, document_node, vals):
        invoice = vals['invoice']
        if invoice.currency_id.name != "COP":
            document_node['cac:PaymentExchangeRate'] = {
                'cbc:SourceCurrencyCode': {'_text': "COP"},
                'cbc:SourceCurrencyBaseRate': {'_text': (rate := self.format_float(1 / invoice.invoice_currency_rate, 6))},
                'cbc:TargetCurrencyCode': {'_text': invoice.currency_id.name},
                'cbc:TargetCurrencyBaseRate': {'_text': "1.00"},
                'cbc:CalculationRate': {'_text': rate},
                'cbc:Date': {'_text': invoice.invoice_date},
            }

    def _add_document_extensions_node(self, document_node, vals):
        document_node['ext:UBLExtensions'] = self._get_document_extensions_node(vals)

    def _get_address_node(self, vals):
        partner = vals['partner']
        address_vals = {
            'cbc:ID': {'_text': str(partner.city_id.l10n_co_edi_code).zfill(5)},  # Codigo Municipio
            'cbc:CityName': {'_text': partner.city},
            'cbc:PostalZone': {'_text': partner.zip},
            'cbc:CountrySubentity': {'_text': partner.state_id.name},
            'cbc:CountrySubentityCode': {'_text': str(partner.state_id.l10n_co_edi_code).zfill(2)},
            'cac:Country': {
                'cbc:IdentificationCode': {'_text': partner.country_id.code},
                'cbc:Name': {
                    '_text': COUNTRIES_ES.get(partner.country_code) if vals.get('use_es_country_name') else partner.country_id.name,
                    'languageID': 'es' if partner.country_code == 'CO' else 'en',
                },
            },
        }

        if address_line_parts := [partner[x] for x in ('street', 'street2') if partner[x]]:
            address_vals['cac:AddressLine'] = {
                'cbc:Line': {'_text': ' '.join(address_line_parts)}
            }

        return address_vals

    def _get_party_node(self, vals):
        company = vals['company']
        partner = vals['partner']
        role = vals['role']
        commercial_partner = partner.commercial_partner_id
        if partner == company.partner_id.commercial_partner_id:
            partner_display_name = partner_name = commercial_partner_name = company.root_id.partner_id.commercial_partner_id.display_name
        else:
            commercial_partner_name = commercial_partner.display_name
            partner_display_name = partner.display_name
            partner_name = partner.name

        vat_without_verification_code = commercial_partner._get_vat_without_verification_code()
        vat_verification_code = commercial_partner._get_vat_verification_code()

        return {
            'cbc:IndustryClassificationCode': {
                '_text': vals['company'].l10n_co_edi_header_actividad_economica
            } if role == 'supplier' and vals['l10n_co_edi_identifier_type'] != 'cuds' else None,
            'cac:PartyIdentification': {
                'cbc:ID': {
                    '_text': vat_without_verification_code,
                    'schemeName': (partner_code := commercial_partner._l10n_co_edi_get_identification_type_code()),
                    # every Colombian NIT (code='rut') comprises a validation digit, it is mandatory to add it here
                    'schemeID': vat_verification_code if partner_code == CO_NIT_DIAN_CODE else None,
                }
            } if not commercial_partner.is_company else None,
            'cac:PartyName': {
                'cbc:Name': {
                    '_text': partner_display_name,
                }
            },
            'cac:PhysicalLocation': {
                'cac:Address': self._get_address_node({'partner': partner, 'use_es_country_name': True})
            } if partner.l10n_co_dian_id_value != FINAL_CONSUMER_VAT else None,
            'cac:PartyTaxScheme': {
                'cbc:RegistrationName': {
                    '_text': commercial_partner_name,
                },
                'cbc:CompanyID': {
                    '_text': vat_without_verification_code,
                    'schemeName': commercial_partner._l10n_co_edi_get_identification_type_code(),
                    'schemeAgencyName': "CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)",
                    'schemeAgencyID': "195",
                    'schemeID': vat_verification_code
                    if partner._l10n_co_edi_get_identification_type_code() == CO_NIT_DIAN_CODE else None,
                },
                'cbc:TaxLevelCode': {
                    '_text': ';'.join(commercial_partner.l10n_co_edi_obligation_type_ids.mapped('name'))
                },
                # 'Consumidor Final' is used in B2C, hence no address should be filled
                'cac:RegistrationAddress': self._get_address_node({'partner': commercial_partner}) if commercial_partner.l10n_co_dian_id_value != FINAL_CONSUMER_VAT else None,
                'cac:TaxScheme': {
                    'cbc:ID': {
                        '_text': commercial_partner._l10n_co_edi_get_fiscal_regimen_code()
                    },
                    'cbc:Name': {
                        '_text': 'No aplica' if (name := commercial_partner._l10n_co_edi_get_fiscal_regimen_name()) == 'No Aplica' else name
                    }
                },
            },
            'cac:PartyLegalEntity': {
                'cbc:RegistrationName': {
                    '_text': commercial_partner_name,
                },
                'cbc:CompanyID': {
                    '_text': vat_without_verification_code,
                    'schemeName': commercial_partner._l10n_co_edi_get_identification_type_code(),
                    'schemeAgencyName': "CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)",
                    'schemeAgencyID': "195",
                    'schemeID': vat_verification_code,
                },
                'cac:CorporateRegistrationScheme': {
                    'cbc:ID': {
                        '_text': vals['journal'].code
                    },
                    'cbc:Name': {
                        '_text': vals['company'].partner_id._get_vat_without_verification_code()
                    },
                } if role == 'supplier' else None,
            } if partner.l10n_co_dian_id_value != FINAL_CONSUMER_VAT else None,
            'cac:Contact': {
                'cbc:Name': {
                    '_text': partner_name,
                },
                'cbc:Telephone': {
                    '_text': partner.phone
                },
                'cbc:ElectronicMail': {
                    '_text': partner.email
                },
            } if partner.l10n_co_dian_id_value != FINAL_CONSUMER_VAT else None,
        }

    def _get_billing_reference_node(self, invoice):
        """Get the BillingReference node for credit/debit notes."""
        reference_invoice = None
        if invoice.l10n_co_edi_operation_type == '20' or invoice.move_type == 'in_refund':
            reference_invoice = invoice.reversed_entry_id
            scheme_name = "CUDS" if invoice.move_type == 'in_refund' else "CUFE"
        elif invoice.l10n_co_edi_operation_type == '30':
            reference_invoice = invoice.debit_origin_id
            scheme_name = "CUFE"

        if reference_invoice:
            return {
                'cac:InvoiceDocumentReference': {
                    'cbc:ID': {'_text': reference_invoice.name},
                    'cbc:UUID': {
                        '_text': reference_invoice.l10n_co_edi_cufe_cude_ref,
                        'schemeName': f"{scheme_name}-SHA384"
                    },
                    'cbc:IssueDate': {'_text': reference_invoice.invoice_date.isoformat()},
                }
            }
        return None

    def _get_invoice_line_node(self, vals):
        line_node = super()._get_invoice_line_node(vals)
        self._add_invoice_line_period_nodes(line_node, vals)

        return line_node

    # -------------------------------------------------------------------------
    # EXPORT: Templates for invoice amount nodes
    # -------------------------------------------------------------------------

    def _add_document_tax_total_nodes(self, document_node, vals):
        # We need multiple tax total nodes, one per l10n_co_edi_type.

        base_lines_aggregated_tax_details = {}
        aggregated_tax_details = {}
        base_unit_measure_by_grouping_key = defaultdict(float)

        def grouping_function(base_line, tax_data):
            grouping_key = vals['tax_grouping_function'](base_line, tax_data)
            if grouping_key is not None and tax_data['tax'].l10n_co_edi_type.code in ['22', '32', '34']:
                # Handle INC Bolsas/ICL/IBUA taxes
                if tax_data['tax'].l10n_co_edi_type.code == '22':
                    base_unit_measure_by_grouping_key[frozendict(grouping_key)] = tax_data['tax'].amount
                else:
                    base_unit_measure_by_grouping_key[frozendict(grouping_key)] += (
                        base_line['product_id'].l10n_co_edi_ref_nominal_tax *
                        (base_line['quantity'] if tax_data['tax'].l10n_co_edi_type.code == '34' else 1)
                    )
            return grouping_key

        base_lines_aggregated_tax_details = self.env['account.tax']._aggregate_base_lines_tax_details(
            vals['base_lines'],
            grouping_function,
        )
        aggregated_tax_details = self.env['account.tax']._aggregate_base_lines_aggregated_values(
            base_lines_aggregated_tax_details,
        )

        grouped_aggregated_tax_details_by_l10n_co_edi_type = {'tax': defaultdict(dict), 'withholding_tax': defaultdict(dict)}

        for grouping_key, values in aggregated_tax_details.items():
            if grouping_key:
                l10n_co_edi_type = grouping_key['l10n_co_edi_type']
                key = 'withholding_tax' if grouping_key['is_withholding_tax'] else 'tax'
                grouped_aggregated_tax_details_by_l10n_co_edi_type[key][l10n_co_edi_type][grouping_key] = values
                values['base_unit_measure'] = base_unit_measure_by_grouping_key[grouping_key]

        document_node['cac:TaxTotal'] = [
            self._get_tax_total_node({**vals, 'aggregated_tax_details': tax_details, 'role': 'document'})
            for tax_details in grouped_aggregated_tax_details_by_l10n_co_edi_type['tax'].values()
        ]
        if vals['document_type'] == 'invoice':
            document_node['cac:WithholdingTaxTotal'] = [
                self._get_tax_total_node({**vals, 'aggregated_tax_details': tax_details, 'role': 'document', 'sign': -1})
                for tax_details in grouped_aggregated_tax_details_by_l10n_co_edi_type['withholding_tax'].values()
            ]

    def _add_invoice_monetary_total_nodes(self, document_node, vals):
        """ The validator will check that:
        * LineExtensionAmount = sum(InvoiceLine/LineExtensionAmount)
        * TaxExclusiveAmount = sum(InvoiceLine/TaxTotal/TaxSubtotal/TaxableAmount)
        * TaxInclusiveAmount = LineExtensionAmount + sum(Invoice/TaxTotal/TaxAmount)
        * ChargeTotalAmount = sum(Invoice/AllowanceCharge[ChargeIndicator='true'] [1]
        * AllowanceTotalAmount = sum(Invoice/AllowanceCharge[ChargeIndicator='false'] [1]
        * PrepaidAmount = sum(Invoice/PrepaidPayment/PaidAmount)
        * PayableAmount = TaxInclusiveAmount - AllowanceTotalAmount + ChargeTotalAmount [2]

        [1]: Will always be 0
        [2]: PrepaidAmount is not used in the PayableAmount
        [3]: Withholdings have no impact in any of these subtotals, they are optionals
        """
        # The monetary total should not take into account withholding taxes.
        super()._add_invoice_monetary_total_nodes(document_node, vals)

        prepaid_amount = sum(p['amount'] for p in vals['prepayments'])

        monetary_total_tag = self._get_tags_for_document_type(vals)['monetary_total']
        monetary_total_node = document_node[monetary_total_tag]

        if any(self._is_free_invoice_line(base_line) for base_line in vals['base_lines']):
            monetary_total_node['cbc:LineExtensionAmount']['_text'] = self.format_float(0, vals['currency_dp'])
            # for Free Sample invoices the TaxInclusiveAmount == TaxAmount
            tax_amount = monetary_total_node['cbc:TaxInclusiveAmount']['_text'] - monetary_total_node['cbc:TaxExclusiveAmount']['_text']
            monetary_total_node['cbc:TaxInclusiveAmount']['_text'] = self.format_float(tax_amount, vals['currency_dp'])

        monetary_total_node.update({
            'cbc:PayableAmount': {
                '_text': self.format_float(monetary_total_node['cbc:TaxInclusiveAmount']['_text'], vals['currency_dp']),
                'currencyID': vals['currency_name'],
            },
            'cbc:PrepaidAmount': {
                '_text': self.format_float(prepaid_amount, vals['currency_dp']),
                'currencyID': vals['currency_name'],
            } if prepaid_amount else None,
        })

    def _add_document_monetary_total_nodes(self, document_node, vals):
        super()._add_document_monetary_total_nodes(document_node, vals)

        monetary_total_tag = self._get_tags_for_document_type(vals)['monetary_total']
        monetary_total_node = document_node[monetary_total_tag]

        # TaxExclusiveAmount and TaxInclusiveAmount should not include Allowances or Charges
        monetary_total_node.update({
            'cbc:TaxExclusiveAmount': {
                '_text': self.format_float(vals['total_lines'], vals['currency_dp']),
                'currencyID': vals['currency_name'],
            },
            'cbc:TaxInclusiveAmount': {
                '_text': self.format_float(vals['total_lines'] + vals['total_tax_amount'], vals['currency_dp']),
                'currencyID': vals['currency_name'],
            },
        })

    # -------------------------------------------------------------------------
    # EXPORT: Templates for tax-related nodes
    # -------------------------------------------------------------------------

    def _get_tax_subtotal_node(self, vals):
        tax_details = vals['tax_details']
        grouping_key = vals['grouping_key']

        if grouping_key['l10n_co_edi_type'].code not in ['22', '32', '34']:
            tax_subtotal_node = super()._get_tax_subtotal_node(vals)
            tax_subtotal_node['cbc:Percent'] = None
        else:
            # Special subtotals for INC Bolsas/ICL/IBUA taxes
            tax_subtotal_node = {
                'cbc:TaxAmount': {
                    '_text': self.format_float(tax_details['tax_amount'], vals['currency_dp']),
                    'currencyID': vals['currency_name'],
                },
                'cbc:BaseUnitMeasure': {
                    '_text': tax_details['base_unit_measure'],
                    'unitCode': {
                        '22': 'NIU',
                        '32': 'LTR',
                        '34': 'ML'
                    }.get(grouping_key['l10n_co_edi_type'].code),
                },
                'cbc:PerUnitAmount': {
                    '_text': self.format_float(grouping_key['amount'], 2),
                    'currencyID': vals['currency_name']
                },
                'cac:TaxCategory': self._get_tax_category_node(vals),
            }

        return tax_subtotal_node

    def _get_tax_category_node(self, vals):
        grouping_key = vals['grouping_key']
        return {
            # DIAN accepts up to 3 decimals for this node. But it also checks that the type of tax is consistent with the tax amount reported.
            # For instance: '19.00' for an 'IVA' tax is allowed, but '19.000' is not
            # (it raises: "FAS01b, Rechazo: Tributo IVA (01), INC (04) informado no coincide, revisar Porcentaje, Nombre y ID.").
            # The majority of taxes have only 2 decimals, but some have 3 (and they should be reported with all their decimals).
            'cbc:Percent': {
                '_text': FloatFmt(abs(grouping_key['amount']), 2, 3)  # withholding taxes are reported as positives
            } if grouping_key['l10n_co_edi_type'].code not in {'22', '32', '34'}
            else None,  # Don't include Percent for INC Bolsas/ICL/IBUA taxes
            'cac:TaxScheme': {
                'cbc:ID': {
                    '_text': grouping_key['l10n_co_edi_type'].code,
                },
                'cbc:Name': {
                    '_text': 'No aplica' if grouping_key['l10n_co_edi_type'].name == 'No Aplica' else grouping_key['l10n_co_edi_type'].name
                },
            }
        }

    # -------------------------------------------------------------------------
    # EXPORT: Templates for invoice line nodes
    # -------------------------------------------------------------------------

    def _add_invoice_line_id_nodes(self, line_node, vals):
        super()._add_invoice_line_id_nodes(line_node, vals)
        base_line = vals['base_line']
        invoice = vals['invoice']
        if invoice.l10n_co_edi_operation_type == '11':
            line_node['cbc:ID']['schemeID'] = '1' if base_line['product_id'].l10n_co_edi_mandate_contract else '0'

    def _add_invoice_line_item_nodes(self, line_node, vals):
        super()._add_invoice_line_item_nodes(line_node, vals)
        record = vals['base_line']['record']
        if record.product_id.l10n_co_edi_mandate_contract:
            mandate_principal = record.partner_id
            scheme_name_mp = mandate_principal._l10n_co_edi_get_identification_type_code()
            line_node['cac:Item']['cac:InformationContentProviderParty'] = {
                'cac:PowerOfAttorney': {
                    'cac:AgentParty': {
                        'cac:PartyIdentification': {
                            'cbc:ID': {
                                '_text': mandate_principal._get_vat_without_verification_code(),
                                'schemeAgencyID': '195',
                                'schemeAgencyName': "CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)",
                                'schemeID': mandate_principal._get_vat_verification_code() if scheme_name_mp == CO_NIT_DIAN_CODE else False,
                                'schemeName': scheme_name_mp,
                            }
                        }
                    }
                }
            }

    def _invoice_line_item_node_require_description(self, vals):
        # For support documents description is mandatory
        if vals['l10n_co_edi_is_support_document']:
            return True
        return super()._invoice_line_item_node_require_description(vals)

    def _add_document_line_amount_nodes(self, line_node, vals):
        super()._add_document_line_amount_nodes(line_node, vals)
        base_line = vals['base_line']

        # Colombia follows a standard that very much resembles the UNSPSC
        uom = base_line['product_uom_id'].l10n_co_edi_ubl or '94'
        quantity_tag = self._get_tags_for_document_type(vals)['line_quantity']
        line_node[quantity_tag]['unitCode'] = uom

        if self._is_free_invoice_line(base_line):
            line_node['cbc:LineExtensionAmount']['_text'] = self.format_float(0, vals['currency_dp'])

    def _add_invoice_line_note_nodes(self, line_node, vals):
        invoice = vals['invoice']
        base_line = vals['base_line']
        if invoice.l10n_co_edi_operation_type == '09' and base_line['product_id']:
            line_node['cbc:Note'] = {'_text': f"Contrato de servicios AIU por Concepto de: {base_line['product_id'].name}"}

    def _add_invoice_line_period_nodes(self, line_node, vals):
        line = vals['base_line']['record']
        # Support documents have a special InvoicePeriod node
        if line.move_id.l10n_co_edi_is_support_document:
            line_node['cac:InvoicePeriod'] = {
                'cbc:StartDate': {'_text': line.move_id.invoice_date},
                'cbc:DescriptionCode': {'_text': 1},
                'cbc:Description': {'_text': 'Por operación'},
            }

    def _add_document_line_tax_total_nodes(self, line_node, vals):
        # Colombian particularity: there should be one `TaxTotal` per colombian tax type, comprising 1 or more
        # `TaxSubtotal` (1 per tax amount). The same applies for `WithholdingTaxTotal`.
        base_unit_measure_by_grouping_key = defaultdict(float)

        def grouping_function(base_line, tax_data):
            grouping_key = vals['tax_grouping_function'](base_line, tax_data)
            if grouping_key is not None and tax_data['tax'].l10n_co_edi_type.code in ['22', '32', '34']:
                # - INC Bolsas (tax on plastic bags) is a tax based on the number of plastic bags used in the sale.
                #   It is always sent in NIUs (Number of Items) according to the specifications listed in the DIAN documentation.
                # - ICL (tax on alcoholic beverages) is a tax based on the alcohol percentage in the bottle.
                #   It is always sent in LTRs according to the specifications listed in the DIAN documentation.
                # - IBUA (tax on sugar beverages) is a tax based on the quantity of sugar per 100mL
                #   e.g. if the quantity of sugar per 100mL is > 10gr -> tax of 35$ per 100mL
                # In Odoo, we have a field for the volume of the product : l10n_co_edi_ref_nominal_tax
                if tax_data['tax'].l10n_co_edi_type.code == '22':
                    base_unit_measure_by_grouping_key[frozendict(grouping_key)] = tax_data['tax'].amount
                else:
                    base_unit_measure_by_grouping_key[frozendict(grouping_key)] += (
                        base_line['product_id'].l10n_co_edi_ref_nominal_tax *
                        (base_line['quantity'] if tax_data['tax'].l10n_co_edi_type.code == '34' else 1)
                    )
            return grouping_key

        aggregated_tax_details = self.env['account.tax']._aggregate_base_line_tax_details(
            vals['base_line'],
            grouping_function,
        )

        grouped_aggregated_tax_details_by_l10n_co_edi_type = {'tax': defaultdict(dict), 'withholding_tax': defaultdict(dict)}

        for grouping_key, values in aggregated_tax_details.items():
            if grouping_key:
                l10n_co_edi_type = grouping_key['l10n_co_edi_type']
                key = 'withholding_tax' if grouping_key['is_withholding_tax'] else 'tax'
                grouped_aggregated_tax_details_by_l10n_co_edi_type[key][l10n_co_edi_type][grouping_key] = values
                values['base_unit_measure'] = base_unit_measure_by_grouping_key[grouping_key]

        line_node['cac:TaxTotal'] = [
            self._get_tax_total_node({**vals, 'aggregated_tax_details': tax_details, 'role': 'line'})
            for tax_details in grouped_aggregated_tax_details_by_l10n_co_edi_type['tax'].values()
        ]
        if vals['document_type'] == 'invoice':
            line_node['cac:WithholdingTaxTotal'] = [
                self._get_tax_total_node({**vals, 'aggregated_tax_details': tax_details, 'role': 'line', 'sign': -1})
                for tax_details in grouped_aggregated_tax_details_by_l10n_co_edi_type['withholding_tax'].values()
            ]

    def _add_document_line_item_nodes(self, line_node, vals):
        super()._add_document_line_item_nodes(line_node, vals)

        base_line = vals['base_line']
        product = base_line['product_id']
        if vals['l10n_co_edi_type'] == L10N_CO_EDI_TYPE['Export Invoice']:
            line_node['cac:Item']['cbc:BrandName'] = {'_text': product.l10n_co_edi_brand}
            line_node['cac:Item']['cbc:ModelName'] = {'_text': product.l10n_co_edi_customs_code}

        l10n_co_product_code, product_code_scheme_id, product_code_scheme_name = self._l10n_co_edi_get_product_code(
            product,
            vals['l10n_co_edi_type'],
            vals['document_type'],
            vals['l10n_co_edi_is_support_document'],
        )
        line_node['cac:Item']['cac:SellersItemIdentification'] = {
            'cbc:ID': {'_text': product.code if vals['l10n_co_edi_identifier_type'] != 'cuds' else l10n_co_product_code},
            'cbc:ExtendedID': {'_text': l10n_co_product_code} if vals['l10n_co_edi_identifier_type'] == 'cuds' else None,
        }
        line_node['cac:Item']['cac:StandardItemIdentification'] = {
            'cbc:ID': {
                '_text': l10n_co_product_code,
                'schemeID': product_code_scheme_id,
                'schemeName': product_code_scheme_name,
            }
        }

    def _l10n_co_edi_get_product_code(self, product, l10n_co_edi_type, document_type, is_support_document):
        if product:
            if l10n_co_edi_type == L10N_CO_EDI_TYPE['Export Invoice']:
                if not product.l10n_co_edi_customs_code:
                    raise UserError(self.env._('Exportation invoices require custom code in all the products, please fill in this information before validating the invoice'))
                return product.l10n_co_edi_customs_code, '020', 'Partida Alanceraria'

            if (
                    document_type == "credit_note" and
                    is_support_document and
                    (code := product.default_code or product.barcode or product.unspsc_code_id.code)
            ):
                return code, '999', 'Estándar de adopción del contribuyente'
            elif product.barcode:
                return product.barcode, '010', 'GTIN'
            elif product.unspsc_code_id:
                return product.unspsc_code_id.code, '001', 'UNSPSC'
            elif product.default_code:
                return product.default_code, '999', 'Estándar de adopción del contribuyente'

        return '1010101', '001', ''

    def _add_document_line_tax_category_nodes(self, line_node, vals):
        # No InvoiceLine/Item/ClassifiedTaxCategory in Colombia
        pass

    def _add_document_line_gross_subtotal_and_discount_vals(self, vals):
        """
        Override to extract the gross_subtotal and discount_amount so that
        the global discount will appear as an AllowanceCharge node for the line.
        """
        super()._add_document_line_gross_subtotal_and_discount_vals(vals)
        tax_details = vals['base_line']['tax_details']
        if 'raw_discount_amount_currency' not in tax_details:
            return
        for suffix in ('_currency', ''):
            vals[f'discount_amount{suffix}'] = tax_details[f'raw_discount_amount{suffix}']
            vals[f'gross_subtotal{suffix}'] = tax_details[f'raw_gross_total_excluded{suffix}']
            vals[f'gross_price_unit{suffix}'] = tax_details[f'raw_gross_price_unit{suffix}']

    def _get_line_fixed_tax_allowance_charge_nodes(self, vals):
        # Fixed taxes (e.g. the IBUA sugar tax) should not be reported as AllowanceCharges.
        return []

    def _get_line_discount_allowance_charge_node(self, vals):
        discount_node = super()._get_line_discount_allowance_charge_node(vals)
        if discount_node:
            discount_node['cbc:AllowanceChargeReasonCode'] = {'_text': '00'}  # unconditional discount
            if 'raw_discount_amount_currency' in vals['base_line']['tax_details']:
                # Invoice flow: the discount may originate from a redistributed global discount.
                discount_node['cbc:MultiplierFactorNumeric'] = {'_text': round(100 * vals['discount_amount'] / vals['gross_subtotal'], 4)}
                discount_node['cbc:Amount'] = {
                    '_text': self.format_float(vals['discount_amount'], vals['currency_dp']),
                    'currencyID': vals['currency_name'],
                }
            else:
                discount_node['cbc:MultiplierFactorNumeric'] = {'_text': vals['base_line']['discount']}
            discount_node['cbc:BaseAmount'] = {
                '_text': self.format_float(vals['gross_subtotal'], vals['currency_dp']),
                'currencyID': vals['currency_name'],
            }
        return discount_node

    def _add_invoice_line_price_nodes(self, line_node, vals):
        # EXTEND account.edi.xml.ubl_20
        super()._add_invoice_line_price_nodes(line_node, vals)

        if self._is_free_invoice_line(vals['base_line']):
            line_node['cac:Price']['cbc:PriceAmount']['_text'] = '0.0'

    def _add_document_line_price_nodes(self, line_node, vals):
        super()._add_document_line_price_nodes(line_node, vals)
        base_line = vals['base_line']
        # Colombia follows a standard that very much resembles the UNSPSC
        uom = base_line['product_uom_id'].l10n_co_edi_ubl or '94'
        line_node['cac:Price']['cbc:BaseQuantity'] = {
            '_text': base_line['quantity'],
            'unitCode': uom,
        }

    def _add_invoice_line_pricing_reference_nodes(self, line_node, vals):
        # EXTEND account.edi.xml.ubl_20
        super()._add_invoice_line_pricing_reference_nodes(line_node, vals)

        if self._is_free_invoice_line(vals['base_line']):
            line_node.setdefault('cac:PricingReference', {}).update({
                'cac:AlternativeConditionPrice': {
                    'cbc:PriceAmount': {
                        '_text': vals['gross_price_unit'],
                        'currencyID': vals['company_currency_id'].name,
                    },
                    'cbc:PriceTypeCode': {'_text': '01'},
                    'cbc:PriceType': {'_text': 'Valor comercial'}
                }
            })

    def _add_invoice_line_free_of_charge_indicator_nodes(self, line_node, vals):
        # OVERRIDE account.edi.xml.ubl_20
        if self._is_free_invoice_line(vals['base_line']):
            line_node['cbc:FreeOfChargeIndicator'] = {'_text': 'true'}

    # -------------------------------------------------------------------------
    # EXPORT: Constraints
    # -------------------------------------------------------------------------

    def _export_invoice_constraints(self, move, vals):
        # EXTENDS account.edi.xml.ubl_21
        constraints = super()._export_invoice_constraints(move, vals)

        constraints['_config'] = constraints.get('_config', dict()) | {
            'indent_suffix': "- ",
            'indent_suffix_on_root_titles': False,
        }

        # Move constraints
        constraints['dian_model_account.move'] = {'_title': self.env._("On the %(model_name)s (%(model)s):\n", model_name="account.move", model=self.env._("Move"))}

        now = fields.Datetime.context_timestamp(self.with_context(tz='America/Bogota'), fields.Datetime.now()).date()
        oldest_date = now - timedelta(days=6)
        newest_date = now + timedelta(days=6)
        if move.invoice_date and not (oldest_date <= move.invoice_date <= newest_date):
            constraints['dian_model_account.move']['date'] = self.env._("The issue date can not be older than 6 days or more than 6 days in the future.")
        if not move.l10n_co_edi_post_time:
            constraints['dian_model_account.move']['post_time'] = self.env._("A posted time is required to compute the CUFE/CUDE/CUDS.")
        if not move.l10n_co_edi_type:
            constraints['dian_model_account.move']['l10n_co_edi_type'] = self.env._("An Electronic Invoice Type must be selected before sending the invoice.")

        if move.l10n_co_edi_operation_type == '20':
            # Credit note with a referenced invoice
            if not move.l10n_co_edi_description_code_credit:
                constraints['dian_model_account.move']['credit_note_missing_reason'] = self.env._("Please set a credit note reason as it is required for this type of transaction.")
            if not move.reversed_entry_id:
                constraints['dian_model_account.move']['credit_note'] = self.env._("There is no invoice linked to this credit note but the operation type is '20'.")
            elif not move.reversed_entry_id.l10n_co_edi_cufe_cude_ref:
                constraints['dian_model_account.move']['credit_note_cufe'] = self.env._("The invoice linked to this credit note has no CUFE.")

        if move.move_type == 'in_refund':
            # Support Document Credit Note
            if not move.reversed_entry_id:
                constraints['dian_model_account.move']['credit_note'] = self.env._("There is no support document linked to this credit note.")
            if not move.reversed_entry_id.l10n_co_edi_cufe_cude_ref:
                constraints['dian_model_account.move']['credit_note_cufe'] = self.env._("The support document linked to this credit note has no CUDS.")

        if move.l10n_co_edi_operation_type == '30':
            # Debit note with a referenced invoice
            if not move.debit_origin_id:
                constraints['dian_model_account.move']['debit_note'] = self.env._("There is no original debited invoice but the operation type is '30'.")
            elif not move.debit_origin_id.l10n_co_edi_cufe_cude_ref:
                constraints['dian_model_account.move']['debit_note_cufe'] = self.env._("The original debited invoice has no CUFE.")

        if move.l10n_co_edi_operation_type in ('20', '22'):
            constraints['dian_model_account.move']['concepto_credit_note'] = self._check_required_fields(move, 'l10n_co_edi_description_code_credit')
        if move.l10n_co_edi_debit_note:
            constraints['dian_model_account.move']['concepto_debit_note'] = self._check_required_fields(move, 'l10n_co_edi_description_code_debit')

        # Company constraints
        constraints['dian_model_res.company'] = {'_title': self.env._("On the %(model_name)s (%(model)s):\n", model_name="res.company", model=self.env._("Company"))}

        if operation_mode := self._dian_get_operation_mode(move):
            mandatory_fields = ['dian_software_id', 'dian_software_operation_mode', 'dian_software_security_code']
            if move.company_id.l10n_co_edi_test_environment:
                mandatory_fields.append('dian_testing_id')

            for field in mandatory_fields:
                constraints['dian_model_res.company'][field] = self._check_required_fields(operation_mode, field)

            if move.l10n_co_edi_identifier_type in ('cude', 'cuds') and not operation_mode.dian_software_security_code:
                constraints['dian_model_res.company']['l10n_co_edi_identifier_type'] = self.env._("The software PIN is required to compute the CUDE/CUDS.")
        else:
            constraints['dian_model_res.company']['operation_modes'] = self.env._("No DIAN Operation Mode Matches")

        # Journal constraints
        constraints['dian_model_account.journal'] = {'_title': self.env._("On the %(model_name)s (%(model)s):\n", model_name="account.journal", model=self.env._("Journal"))}
        if move.move_type == 'out_invoice' and not move.journal_id.l10n_co_edi_technical_key and not move.company_id.l10n_co_edi_demo_mode:
            constraints['dian_model_account.journal']['l10n_co_edi_technical_key'] = self.env._("A technical key on the journal is required to compute the CUFE.")

        required_journal_fields = [
            'l10n_co_edi_dian_authorization_number',
            'l10n_co_edi_dian_authorization_date',
            'l10n_co_edi_dian_authorization_end_date',
            'l10n_co_edi_min_range_number',
            'l10n_co_edi_max_range_number',
        ]
        if not move.company_id.l10n_co_edi_demo_mode:
            required_journal_fields.append('l10n_co_edi_technical_key')

        for field in required_journal_fields:
            constraints['dian_model_account.journal'][f"dian_{field}"] = self._check_required_fields(move.journal_id, field)

        # Partner constraints
        for role in ('customer', 'supplier'):
            constraint_title = ""
            match role:
                case 'customer':
                    constraint_title = self.env._("Customer Partner")
                case 'supplier':
                    constraint_title = self.env._("Supplier Partner")

            constraints[f'{role}_dian_model_res.partner'] = {'_title': self.env._("On the %(model_name)s (%(model)s):\n", model_name="res.partner", model=constraint_title)}
            commercial_partner = vals[role].commercial_partner_id

            constraints[f'{role}_dian_model_res.partner'].update({
                f"dian_vat_{role}": self._check_required_fields(commercial_partner, 'l10n_co_dian_id_value'),
                f"dian_identification_type_{role}": self._check_required_fields(commercial_partner, 'l10n_co_dian_id_code'),
                f"dian_obligation_type_{role}": self._check_required_fields(commercial_partner, 'l10n_co_edi_obligation_type_ids'),
            })

            if commercial_partner.l10n_co_dian_id_code != CO_NIT_DIAN_CODE and '-' in (commercial_partner.l10n_co_dian_id_value or ''):
                constraints[f'{role}_dian_model_res.partner']["NIT"] = self.env._("The identification number of %s contains '-' but is not a NIT.", commercial_partner.name)
            if vals[role].country_code == 'CO' and commercial_partner.l10n_co_dian_id_value != FINAL_CONSUMER_VAT:
                constraints[f'{role}_dian_model_res.partner']['country_subentity'] = self._check_required_fields(vals[role], 'state_id')
                constraints[f'{role}_dian_model_res.partner']["city"] = self._check_required_fields(vals[role], 'city_id')

        # Move line constraints
        constraints['dian_model_account.move.line'] = {'_title': self.env._("On the %(model_name)s (%(model)s):\n", model_name="account.move.line", model=self.env._("Move line"))}
        is_free_sample_invoice = any(self._is_free_invoice_line(base_line) for base_line in vals['base_lines'])

        if is_free_sample_invoice and not all(self._is_free_invoice_line(base_line) for base_line in vals['base_lines']):
            # Every line on a free sample invoice needs to have a tax with type == Free sample
            constraints['dian_model_account.move.line']['free_sample'] = self.env._("For Free Sample Invoices, all invoice lines should be configured with a Free Sample tax.")

        for line in move.invoice_line_ids.filtered(lambda l: l.display_type not in ('line_section', 'line_note')):
            product = line.product_id
            # Check the validation for non-global discount lines via coupons & programs
            if line.price_subtotal >= 0:
                constraints['dian_model_account.move.line'][f"product_{product.id}"] = self._check_required_fields(
                    product,
                    ['default_code', 'barcode', 'unspsc_code_id']
                )

            if move.l10n_co_edi_type == L10N_CO_EDI_TYPE['Export Invoice'] and product:
                if not product.l10n_co_edi_customs_code:
                    constraints['dian_model_account.move.line']['export_product_code'] = self.env._("Every exportation product must have a customs code.")
                if not product.l10n_co_edi_brand:
                    constraints['dian_model_account.move.line']['export_product_brand'] = self.env._("Every exportation product must have a brand.")
            if "IBUA" in line.tax_ids.l10n_co_edi_type.mapped('name') and product.l10n_co_edi_ref_nominal_tax == 0:
                constraints['dian_model_account.move.line']['sugar'] = self.env._(
                    "Volume in milliliters should be set on the %(field_description)s field for product: %(product_name)s when using IBUA taxes.",
                    field_description=product._fields['l10n_co_edi_ref_nominal_tax']._description_string(self.env),
                    product_name=product.name)

            if "ICL" in line.tax_ids.l10n_co_edi_type.mapped('name') and product.l10n_co_edi_ref_nominal_tax == 0:
                constraints['dian_model_account.move.line']['alcohol'] = self.env._(
                    "Alcohol percentage should be set on the %(field_description)s field for product: %(product_name)s when using ICL taxes.",
                    field_description=product._fields['l10n_co_edi_ref_nominal_tax']._description_string(self.env),
                    product_name=product.name)

            if not self._dian_uom_code(line):
                constraints['dian_model_account.move.line']['uom'] = self.env._("There is no Colombian code on the unit of measure: %s", line.product_uom_id.name)

            if move.l10n_co_edi_is_support_document and move.currency_id.is_zero(line.price_unit):
                constraints['dian_model_account.move.line']['zero_lines'] = self.env._("Every line should have non zero price units.")

        if move.l10n_co_edi_operation_type == '09':
            if set(move.line_ids.mapped('product_id.type')) != {'service'}:
                constraints['dian_model_account.move.line']['aiu_products'] = self.env._("All products in an AIU invoice should be a service.")

        should_be_mandate = (
            move.move_type in ('in_invoice', 'out_invoice')
            and not move.journal_id.l10n_co_edi_debit_note
            and move.line_ids.product_id.filtered('l10n_co_edi_mandate_contract')
        )

        if move.l10n_co_edi_operation_type != '11' and should_be_mandate:
            constraints['dian_model_account.move']['mandate_products'] = self.env._(
                "One or more products in the invoice are marked as Mandate Contracts. "
                "Please select 'Mandatos' as the Operation Type (CO), or remove those products from the invoice."
            )

        if move.l10n_co_edi_operation_type == '11' and not should_be_mandate:
            constraints['dian_model_account.move']['mandate_products'] = self.env._(
                "The 'Mandatos' option was selected as the Operation Type (CO), but the invoice does not contain "
                "any products marked as Mandate Contracts. Adjust the invoice type or check the listed products."
            )
        return constraints

    # -------------------------------------------------------------------------
    # EXPORT: Commercial Events
    # -------------------------------------------------------------------------

    def _export_co_send_event_update_status_invoice(self, invoice, next_commercial_state):
        vals = {'invoice': invoice, 'l10n_co_dian_commercial_state_next': next_commercial_state}
        document_node = self._get_co_invoice_event_update_status_node(vals)
        document_nsmap = self._get_co_invoice_event_update_status_nsmap(vals)

        xml_content = dict_to_xml(document_node, nsmap=document_nsmap)
        self._dian_fill_signed_info_and_signature(xml_content, vals['x509_certificate'])

        return etree.tostring(xml_content, encoding='UTF-8'), []

    def _get_co_invoice_event_update_status_node(self, vals):
        self._add_co_invoice_event_update_status_config_vals(vals)

        document_node = {'_tag': 'ApplicationResponse'}

        self._add_document_config_vals(vals)

        self._add_document_signature_vals(vals)
        self._add_document_extensions_node(document_node, vals)

        self._add_co_invoice_event_update_status_header_nodes(document_node, vals)
        self._add_co_invoice_event_update_status_note_nodes(document_node, vals)
        self._add_co_invoice_event_update_status_sender_party_nodes(document_node, vals)
        self._add_co_invoice_event_update_status_receiver_party_nodes(document_node, vals)
        self._add_co_invoice_event_update_status_document_response_nodes(document_node, vals)

        document_node['cbc:UUID']['_text'] = self._dian_calculate_cude_sha384(document_node, vals)

        return document_node

    def _add_co_invoice_event_update_status_config_vals(self, vals):
        invoice = vals['invoice']
        commercial_state_values = invoice._fields['l10n_co_edi_commercial_state'].get_values(self.env)
        id_prefix = invoice.ref if invoice.is_purchase_document() else invoice.name
        vals.update({
            'now': datetime.now(tz=ZoneInfo('America/Bogota')),
            'company': invoice.company_id,
            'journal': invoice.journal_id,
            'l10n_co_edi_identifier_type': invoice.l10n_co_edi_identifier_type,
            'uuid': invoice.l10n_co_edi_cufe_cude_ref,
            'sender_partner': invoice.company_id.partner_id,
            'receiver_partner': invoice.partner_id,
            'is_test_env': invoice.company_id.l10n_co_edi_test_environment,
            'tax_types': invoice.line_ids.tax_ids.flatten_taxes_hierarchy().mapped('l10n_co_edi_type'),
            'name': f'{id_prefix}{commercial_state_values.index(vals["l10n_co_dian_commercial_state_next"])}',
        })

    def _add_co_invoice_event_update_status_header_nodes(self, node, vals):
        node.update({
            'cbc:UBLVersionID': {'_text': 'UBL 2.1'},
            'cbc:CustomizationID': {'_text': '1'},
            'cbc:ProfileID': {'_text': 'DIAN 2.1: ApplicationResponse de la Factura Electrónica de Venta'},
            'cbc:ProfileExecutionID': {'_text': '2' if vals['is_test_env'] else '1'},
            'cbc:ID': {'_text': vals['name']},
            'cbc:UUID': {
                'schemeID': '2' if vals['is_test_env'] else '1',
                'schemeName': 'CUDE-SHA384',
            },
            'cbc:IssueDate': {'_text': vals['now'].date().isoformat()},
            'cbc:IssueTime': {'_text': vals['now'].strftime("%H:%M:%S-05:00")},
        })

    def _add_co_invoice_event_update_status_note_nodes(self, node, vals):
        invoice = vals['invoice']
        if invoice.move_type in ('out_invoice', 'out_refund') and vals['l10n_co_dian_commercial_state_next'] == 'accepted_by_issuer':
            last_event_xml = etree.fromstring(invoice.l10n_co_edi_document_ids.sorted()[0].attachment_id.raw.content)
            last_event_cufe = last_event_xml.findtext('./{*}UUID')
            node.update({
                'cbc:Note': {
                    '_text': f"""Manifiesto bajo la gravedad de juramento que transcurridos 3 días hábiles contados desde la creación del Recibo de bienes
y servicios {invoice.name} con CUDE {last_event_cufe}, el adquirente {invoice.partner_id.name} identificado con NIT {invoice.partner_id.vat} no manifestó expresamente
la aceptación o rechazo de la referida factura, ni reclamó en contra de su contenido.""",
                }
            })

    def _add_co_invoice_event_update_status_sender_party_nodes(self, node, vals):
        node['cac:SenderParty'] = {
            'cac:PartyTaxScheme': self._get_co_invoice_event_update_status_party_tax_scheme_node({**vals, 'partner': vals['sender_partner'], 'role': 'sender'}),
        }

    def _add_co_invoice_event_update_status_receiver_party_nodes(self, node, vals):
        receiver_partner = vals['receiver_partner']
        node['cac:ReceiverParty'] = {
            'cac:PartyTaxScheme': self._get_co_invoice_event_update_status_party_tax_scheme_node({**vals, 'partner': receiver_partner, 'role': 'receiver'}),
        }

        if vals['l10n_co_dian_commercial_state_next'] != 'accepted_by_issuer':
            node['cac:ReceiverParty']['cac:Contact'] = {
                'cbc:ElectronicMail': {'_text': receiver_partner.email},
            }

    def _get_co_invoice_event_update_status_party_tax_scheme_node(self, vals):
        partner = vals['partner']

        if vals['role'] == 'sender':
            registration_name = partner.display_name
        elif vals['l10n_co_dian_commercial_state_next'] != 'accepted_by_issuer':
            registration_name = partner.name
        else:
            registration_name = "Unidad Administrativa Especial Dirección de Impuestos y Aduanas Nacionales"

        tax_type = vals['tax_types'][0] if vals['tax_types'] else None

        if vals['role'] == 'sender' and vals['l10n_co_dian_commercial_state_next'] == 'accepted_by_issuer':
            partner_vat = '800197268'  # VAT number of DIAN
        else:
            partner_vat = partner._get_vat_without_verification_code()

        return {
            'cbc:RegistrationName': {'_text': registration_name},
            'cbc:CompanyID': {
                '_text': partner_vat,
                'schemeName': partner._l10n_co_edi_get_identification_type_code(),
                'schemeAgencyName': "CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)",
                'schemeAgencyID': "195",
                'schemeID': partner._get_vat_verification_code(),
                'schemeVersionID': "1",
            },
            'cac:TaxScheme': {
                'cbc:ID': {'_text': tax_type.code if tax_type else None},
                'cbc:Name': {'_text': tax_type.name if tax_type else None},
            },
        }

    def _add_co_invoice_event_update_status_document_response_nodes(self, node, vals):
        node['cac:DocumentResponse'] = {
            'cac:Response': self._get_co_invoice_event_update_status_response_node(vals),
            'cac:DocumentReference': self._get_co_invoice_event_update_status_document_reference_node(vals),
        }

        if vals['l10n_co_dian_commercial_state_next'] in ('received', 'goods_received'):
            node['cac:DocumentResponse']['cac:IssuerParty'] = self._get_co_invoice_event_update_status_issuer_party_node(vals)

    def _get_co_invoice_event_update_status_response_node(self, vals):
        invoice = vals['invoice']

        match vals['l10n_co_dian_commercial_state_next']:
            case 'received':
                description = "Acuse de recibo de Factura Electrónica de Venta"
            case 'goods_received':
                description = "Recibo del bien y/o prestación del servicio"
            case 'claimed':
                description = "Reclamo de la Factura Electrónica de Venta"
            case 'accepted':
                description = "Aceptación expresa"
            case 'accepted_by_issuer':
                description = "Aceptación Tácita"
            case unknown_state:
                _logger.warning(self.env._("Unknown commercial state %(state)s", state=unknown_state))
                description = None

        commercial_states = dict(invoice._fields['l10n_co_edi_commercial_state']._description_selection(self.env))

        node = {
            'cbc:ResponseCode': {
                '_text': commercial_states[vals['l10n_co_dian_commercial_state_next']].split(' - ', 1)[0],
            },
            'cbc:Description': {'_text': description},
        }

        if vals['l10n_co_dian_commercial_state_next'] == 'claimed':
            # DIAN expects the claim reason names in Spanish
            claim_reasons = invoice._fields['l10n_co_edi_claim_reason']._description_selection(self.with_context(lang='es_419').env)
            node['cbc:ResponseCode'].update({
                'listID': invoice.l10n_co_edi_claim_reason,
                'name': next(v for k, v in claim_reasons if k == invoice.l10n_co_edi_claim_reason),
            })

        return node

    def _get_co_invoice_event_update_status_document_reference_node(self, vals):
        invoice = vals['invoice']
        return {
            'cbc:ID': {'_text': invoice.name if invoice.move_type == 'out_invoice' else invoice.ref},
            'cbc:UUID': {
                '_text': invoice.l10n_co_edi_cufe_cude_ref,
                'schemeName': 'CUFE-SHA384',
            },
            'cbc:DocumentTypeCode': {'_text': invoice.l10n_co_edi_type.zfill(2)}
        }

    def _get_co_invoice_event_update_status_issuer_party_node(self, vals):
        partner = vals['invoice'].partner_id
        node = {
            'cac:Person': {
                'cbc:ID': {
                    '_text': compact(partner.vat),
                    'schemeName': partner._l10n_co_edi_get_identification_type_code(),
                    'schemeID': partner.vat,
                },
                'cbc:FirstName': {'_text': partner.name},
                'cbc:FamilyName': {'_text': partner.name},
            }
        }

        if partner.function:
            node['cac:Person'].update({
                'cbc:JobTitle': {'_text': partner.function},
                'cbc:OrganizationDepartment': {'_text': partner.function},
            })

        return node

    def _get_co_invoice_event_update_status_nsmap(self, vals):
        return {
            None: 'urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse-2',
            'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
            'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
            'ds': 'http://www.w3.org/2000/09/xmldsig#',
            'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
            'sts': 'dian:gov:co:facturaelectronica:Structures-2-1',
            'xades': 'http://uri.etsi.org/01903/v1.3.2#',
            'xades141': 'http://uri.etsi.org/01903/v1.4.1#',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
        }

    # -------------------------------------------------------------------------
    # Utils
    # -------------------------------------------------------------------------

    def _dian_uom_code(self, line):
        _logger.debug('method is deprecated, use _dian_get_co_ubl_code instead')
        return self._dian_get_co_ubl_code(line.product_uom_id)

    @api.model
    def _dian_get_co_ubl_code(self, uom):
        """ Colombia follows a standard that very much resembles the UNSPSC """
        return uom.l10n_co_edi_ubl or '94'

    def _dian_tax_amount_repr(self, tax_amount):
        """ Returns a string representation of a float amount to fill the 'TaxSubtotal/TaxCategory/Percent' node.

        DIAN accepts up to 3 decimals for this node. But it also checks that the type of tax is consistent with the
        tax amount reported.
        For instance: '19.00' for an 'IVA' tax is allowed, but '19.000' is not (it raises: "FAS01b, Rechazo: Tributo
        IVA (01), INC (04) informado no coincide, revisar Porcentaje, Nombre y ID.").
        The majority of taxes have only 2 decimals, but some have 3 (and they should be reported with all their
        decimals), hence this weird function.
        """
        str_tax_amount = self.format_float(abs(tax_amount), 3)  # withholding taxes are reported as positives
        return str_tax_amount[:-1] if str_tax_amount.endswith('0') else str_tax_amount

    def _dian_tax_totals(self, move, taxes_vals, withholding):
        """
        Colombian particularity: there should be one `TaxTotal` per colombian tax type, comprising 1 or more
        `TaxSubtotal` (1 per tax amount). The same applies for `WithholdingTaxTotal`.

        :returns: [
            {
                'tax_amount': float,
                'currency': res.currency,
                'currency_dp': int,
                'tax_subtotal_vals': [{
                    'tax_amount': float,
                    'taxable_amount': float,
                    'currency': res.currency,
                    'currency_dp': int,
                    'tax_category_vals': {},
                }]
            },
        ]
        """
        def filter_tax_details(key):
            if move.l10n_co_edi_is_support_document:
                # For support document, only the taxes IVA (01), ReteICA (05), ReteRenta (06) should be included
                return key['tax_co_ret'] == withholding and key['tax_co_type'] in ('01', '05', '06')
            return key['tax_co_ret'] == withholding

        currency = move.company_id.currency_id
        tax_total_dict = defaultdict(lambda: {
            'currency': currency,
            'currency_dp': self._get_currency_decimal_places(currency),
            'tax_amount': 0,
            'per_unit_amount': 0,
            'tax_subtotal_vals': [],
        })
        filtered_tax_details = {k: v for k, v in taxes_vals['tax_details'].items() if filter_tax_details(k)}
        for grouping_key, vals in filtered_tax_details.items():
            tax_co_type = grouping_key['tax_co_type']
            tax_total_dict[tax_co_type]['tax_co_type'] = tax_co_type  # not used in the xml, used to build the CUFE
            tax_subtotal = {
                'currency': currency,
                'currency_dp': self._get_currency_decimal_places(currency),
                'taxable_amount': vals['base_amount'],
                'tax_amount': abs(vals['tax_amount']),   # abs for withholding taxes
                'tax_category_vals': {
                    'percent': self._dian_tax_amount_repr(float(vals['_tax_category_vals_']['percent'])),
                    'tax_scheme_vals': vals['_tax_category_vals_']['tax_scheme_vals'],
                },
            }
            if tax_co_type == '22':
                # INC Bolsas (tax on plastic bags) is a tax based on the number of plastic bags used in the sale.
                # It is always sent in NIUs (Number of Items) according to the specifications listed in the DIAN documentation.
                tax_subtotal.pop('taxable_amount')
                tax_subtotal['base_unit_measure_attrs'] = {'unitCode': "NIU"}
                if 'percent' in tax_subtotal['tax_category_vals']:
                    tax_subtotal['tax_category_vals'].pop('percent')
                # Fixed rate per bag
                tax_subtotal['base_unit_measure'] = float(vals['_tax_category_vals_']['percent'])
                tax_subtotal['per_unit_amount'] = self.format_float(tax_subtotal['base_unit_measure'], 2)
            if tax_co_type == '32':
                # ICL (tax on alcoholic beverages) is a tax based on the alcohol percentage in the bottle.
                # It is always sent in LTRs according to the specifications listed in the DIAN documentation.
                tax_subtotal.pop('taxable_amount')
                tax_subtotal['base_unit_measure_attrs'] = {'unitCode': 'LTR'}
                if 'percent' in tax_subtotal['tax_category_vals']:
                    tax_subtotal['tax_category_vals'].pop('percent')
                if 'tax_details_per_record' in taxes_vals:
                    tax_subtotal['base_unit_measure'] = sum(
                        base_line['product_id'].l10n_co_edi_ref_nominal_tax
                        for base_line, _taxes_data in vals['base_line_x_taxes_data']
                    )
                else:
                    base_line = taxes_vals['base_line']
                    tax_subtotal['base_unit_measure'] = base_line['product_id'].l10n_co_edi_ref_nominal_tax
                # Field validation happens after the exporting of values so we default to a sensible rate of 0 if no
                # alcohol percent is set.
                rate = 0
                if tax_subtotal['base_unit_measure']:
                    rate = vals['tax_amount'] / tax_subtotal['base_unit_measure']
                tax_subtotal['per_unit_amount'] = self.format_float(rate, 2)
            if tax_co_type == '34':
                # IBUA (tax on sugar beverages) is a tax based on the quantity of sugar per 100mL
                # e.g. if the quantity of sugar per 100mL is > 10gr -> tax of 35$ per 100mL
                # In Odoo, we use fixed taxes and a field for the volume of the product: l10n_co_edi_ref_nominal_tax
                # Hence, we can infer the rate per 100mL of the tax
                tax_subtotal.pop('taxable_amount')
                tax_subtotal['base_unit_measure_attrs'] = {'unitCode': "ML"}
                if 'percent' in tax_subtotal['tax_category_vals']:
                    tax_subtotal['tax_category_vals'].pop('percent')
                # Total Volume in mL
                if 'tax_details_per_record' in taxes_vals:
                    tax_subtotal['base_unit_measure'] = sum(
                        base_line['product_id'].l10n_co_edi_ref_nominal_tax * base_line['quantity']
                        for base_line, _taxes_data in vals['base_line_x_taxes_data']
                    )
                else:
                    base_line = taxes_vals['base_line']
                    tax_subtotal['base_unit_measure'] = base_line['product_id'].l10n_co_edi_ref_nominal_tax * base_line['quantity']
                # Infer the rate per 100mL
                # Field validation happens after the exporting of values so we default to a sensible rate of 0 if
                # no sugar contents are set.
                rate = 0
                if tax_subtotal['base_unit_measure']:
                    rate = vals['tax_amount'] * 100 / tax_subtotal['base_unit_measure']
                tax_subtotal['per_unit_amount'] = self.format_float(rate, 2)
            tax_total_dict[tax_co_type]['tax_amount'] += tax_subtotal['tax_amount']  # abs for withholding taxes
            tax_total_dict[tax_co_type]['tax_subtotal_vals'].append(tax_subtotal)

        if '05' in tax_total_dict and move.l10n_co_edi_is_support_document and withholding:
            # Taxes with type '05' are retention taxes (15 %) that apply on the *tax amount* of a regular VAT tax
            # Hence, the tax "15% RteVAT 19%" is encoded as a -2.85% tax in Odoo
            if 'tax_details_per_record' in taxes_vals:
                # On document level, backtrack the taxable amount based on the tax amount
                for subtotal in tax_total_dict['05']['tax_subtotal_vals']:
                    subtotal['tax_category_vals']['percent'] = '15.00'
                    subtotal['taxable_amount'] = subtotal['tax_amount'] / 0.15
            else:
                # On invoice line, look at the sibling tax total node '01' and extract its exact tax amount
                # DSAY05: the Taxable Amount for the taxes with type '05' should be equal to the Tax Amount
                # on which the taxes with type '01' were applied
                sibling_tax_totals = self._dian_tax_totals(move, taxes_vals, withholding=False)
                tax_amount_01 = next((tot for tot in sibling_tax_totals if tot['tax_co_type'] == '01'), {'tax_amount': 0})['tax_amount']
                for subtotal in tax_total_dict['05']['tax_subtotal_vals']:
                    subtotal['tax_category_vals']['percent'] = '15.00'
                    subtotal['taxable_amount'] = tax_amount_01
        return [v for k, v in tax_total_dict.items()]

    def _dian_get_identifier_vals(self, invoice, invoice_vals):
        """ Returns the values used to compute the CUFE/CUDE/CUDS """
        operation_mode = self._dian_get_operation_mode(invoice)

        def format_float(amount, precision_digits=invoice_vals['vals']['currency_dp']):
            return invoice_vals['format_float'](amount, precision_digits)

        def get_filtered_tax_amount(co_tax_code):
            """ Get the tax amount associated to a given colombian tax type code. """
            return sum(ttvals['tax_amount'] for ttvals in invoice_vals['vals']['tax_total_vals'] if ttvals['tax_co_type'] == co_tax_code)

        if invoice.l10n_co_edi_identifier_type in ('cude', 'cuds'):
            key = operation_mode.dian_software_security_code
        else:
            key = invoice.journal_id.l10n_co_edi_technical_key

        vals = {
            'invoice_id': invoice_vals['vals']['id'],
            'issue_date': invoice_vals['vals']['issue_date'],
            'issue_time': invoice_vals['vals']['issue_time'],  # invoice time (including tz)
            'line_extension_amount': format_float(invoice_vals['vals']['monetary_total_vals']['line_extension_amount']),
            'tax_code_01': '01',
            'ValImp1': format_float(get_filtered_tax_amount('01')),
            'tax_code_04': '04',
            'ValImp2': format_float(get_filtered_tax_amount('04')),
            'tax_code_03': '03',
            'ValImp3': format_float(get_filtered_tax_amount('03')),
            'ValTotFac': format_float(invoice_vals['vals']['monetary_total_vals']['payable_amount']),
            'supplier_company_id': invoice_vals['vals']['accounting_supplier_party_vals']['party_vals']['party_tax_scheme_vals'][0]['company_id'],
            'customer_company_id': invoice_vals['vals']['accounting_customer_party_vals']['party_vals']['party_tax_scheme_vals'][0]['company_id'],
            'key': key or 'missing_key',
            'profile_execution_id': invoice_vals['vals']['profile_execution_id'],
        }
        if invoice.l10n_co_edi_is_support_document:
            [vals.pop(k) for k in ('tax_code_04', 'ValImp2', 'tax_code_03', 'ValImp3')]
        return vals

    def _dian_insert_corporate_registration_scheme_node(self, invoice, xml):
        # TODO: Remove in master - this method is not called anywhere
        # Create a CorporateRegistrationScheme node
        root = etree.fromstring(xml)
        nsmap = root.nsmap
        corporate_node = etree.Element("{%s}CorporateRegistrationScheme" % nsmap.get('cac'), nsmap=nsmap)
        id_node = etree.SubElement(corporate_node, "{%s}ID" % nsmap.get('cbc'), nsmap=nsmap)
        id_node.text = invoice.journal_id.code
        name_node = etree.SubElement(corporate_node, "{%s}Name" % nsmap.get('cbc'), nsmap=nsmap)
        name_node.text = invoice.company_id.partner_id._get_vat_without_verification_code()
        # Insert
        legal_entity_node = root.find('.//{*}AccountingSupplierParty//{*}PartyLegalEntity')
        if legal_entity_node is not None:
            legal_entity_node.insert(2, corporate_node)
        return etree.tostring(cleanup_xml_node(root))

    def _dian_get_qr_code_url(self, invoice, identifier):
        """ Returns the value used to fill the sts:DianExtensions/sts:QRCode node """
        # TODO: Remove in master - this method is not called anywhere
        if invoice.company_id.l10n_co_edi_test_environment:
            url = 'https://catalogo-vpfe-hab.dian.gov.co/document/searchqr?documentkey='
        else:
            url = 'https://catalogo-vpfe.dian.gov.co/document/searchqr?documentkey='
        return url + identifier

    def _dian_get_security_code(self, operation_mode, document_number):
        """ Returns the value for the 'SoftwareSecurityCode' node """
        return sha384((
            operation_mode.dian_software_id
            + operation_mode.dian_software_security_code
            + document_number
        ).encode()).hexdigest()

    def _dian_get_document_type_code(self, invoice):
        """ Returns the document type, used for the 'InvoiceTypeCode'/'CreditNoteTypeCode' node """
        if not invoice.l10n_co_edi_is_support_document and invoice.l10n_co_edi_type:
            return invoice.l10n_co_edi_type
        elif invoice.move_type == 'in_refund':
            return '95'  # Nota de ajuste al documento soporte
        else:
            return '05'  # Documento soporte

    def _dian_get_customization_id(self, invoice):
        """ Returns the value used for the 'CustomizationID' node """
        # TODO: Remove in master - this method is not called anywhere
        if not invoice.l10n_co_edi_is_support_document:
            return invoice.l10n_co_edi_operation_type
        return '10' if invoice.partner_id.country_code == 'CO' else '11'

    def _dian_get_operation_mode(self, invoice):
        """Looks for the desired operation mode record based on the mode type"""
        # use 'invoice' for invoices and vendor bills that are not support documents
        mode = 'bill' if invoice.journal_id.l10n_co_edi_is_support_document else 'invoice'
        return invoice.company_id.l10n_co_edi_operation_mode_ids.filtered(
            lambda operation_mode: operation_mode.dian_software_operation_mode == mode
        )

    def _get_sts_namespace(self, vals):
        if vals['document_type'] == 'debit_note':
            return "http://www.dian.gov.co/contratos/facturaelectronica/v1/Structures"
        else:
            return "dian:gov:co:facturaelectronica:Structures-2-1"

    @api.model
    def _dian_calculate_cude_sha384(self, node, vals):
        """Compute the CUDE for a move
        type: 'application_response'
        see: Section 11.5 of Anexo-Tecnico-Factura-Electronica-de-Venta-vr-1-9
        """
        cude_vals = {
            'Num_DE': node['cbc:ID']['_text'],
            'Fec_Emi': node['cbc:IssueDate']['_text'],
            'Hor_Emi': node['cbc:IssueTime']['_text'],
            'NitFe': node['cac:SenderParty']['cac:PartyTaxScheme']['cbc:CompanyID']['_text'],
            'DocAdq': node['cac:ReceiverParty']['cac:PartyTaxScheme']['cbc:CompanyID']['_text'],
            'ResponseCode': node['cac:DocumentResponse']['cac:Response']['cbc:ResponseCode']['_text'],
            'ID': node['cac:DocumentResponse']['cac:DocumentReference']['cbc:ID']['_text'],
            'DocumentTypeCode': node['cac:DocumentResponse']['cac:DocumentReference']['cbc:DocumentTypeCode']['_text'],
            'Software-PIN': self._dian_get_operation_mode(vals['invoice']).dian_software_security_code,
        }

        cude = ''.join(str(value) for value in cude_vals.values())
        return sha384(cude.encode()).hexdigest()

    def _dian_sign_xml(self, xml, invoice):
        # TODO: Remove in master - this method is not called anywhere
        vals = {'invoice': invoice}

        operation_mode = self._dian_get_operation_mode(invoice)
        if not operation_mode:
            return xml, [self.env._("No DIAN Operation Mode Matches")]

        root = etree.fromstring(xml)
        vals['uuid'] = root.findtext('./cbc:UUID', namespaces=root.nsmap)

        self._add_invoice_config_vals(vals)
        self._add_document_signature_vals(vals)

        extensions_node = self._get_document_extensions_node(vals)
        nsmap = self._get_document_extensions_nsmap(vals)

        extensions = dict_to_xml(extensions_node, nsmap=nsmap, render_empty_nodes=True)
        root.insert(0, extensions)

        xml_utils._remove_tail_and_text_in_hierarchy(root)
        self._dian_fill_signed_info_and_signature(root, vals['x509_certificate'])
        return etree.tostring(root, encoding='UTF-8'), []

    def _dian_fill_signed_info_and_signature(self, root, certificate):
        # Hash and sign
        xml_utils._reference_digests(root.find(".//ds:SignedInfo", {'ds': 'http://www.w3.org/2000/09/xmldsig#'}))
        xml_utils._fill_signature(root.find(".//ds:Signature", {'ds': 'http://www.w3.org/2000/09/xmldsig#'}), certificate)

    def _add_document_signature_vals(self, vals):
        certificates_sudo = vals['company'].sudo().l10n_co_edi_certificate_ids
        if not certificates_sudo:
            raise UserError(self.env._("No DIAN certificate is configured on the company."))

        if not vals['l10n_co_edi_operation_mode']:
            raise UserError(self.env._("No matching operation mode found on the company for this journal entry type"))

        if vals['company'].l10n_co_edi_test_environment:
            qr_code_val = f'https://catalogo-vpfe-hab.dian.gov.co/document/searchqr?documentkey={vals["uuid"]}'
        else:
            qr_code_val = f'https://catalogo-vpfe.dian.gov.co/document/searchqr?documentkey={vals["uuid"]}'

        vals['software_security_code'] = sha384((
            vals['l10n_co_edi_operation_mode'].dian_software_id
                + vals['l10n_co_edi_operation_mode'].dian_software_security_code
                + vals['name']
        ).encode()).hexdigest()

        vals.update({
            'qr_code_val': qr_code_val,
            'document_id': "xmldsig-" + str(xml_utils._uuid1()),
            'key_info_id': "xmldsig-" + str(xml_utils._uuid1()) + "-keyinfo",
            'x509_certificate': certificates_sudo[-1],
            'x509_certificates': certificates_sudo,
            'signature_value': 'to be filled later',
            # Colombia time (UTC-5): p.556 "Anexo-Tecnico-Resolucion[...].pdf"
            'signing_time': datetime.now(tz=ZoneInfo('America/Bogota')).isoformat(timespec='milliseconds'),
            'claimed_role': "supplier",
        })

    def _get_document_extensions_nsmap(self, vals):
        return {
            'cbc': "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
            'ds': "http://www.w3.org/2000/09/xmldsig#",
            'ext': "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
            'sts': self._get_sts_namespace(vals),
            'xades': "http://uri.etsi.org/01903/v1.3.2#",
        }

    def _get_document_extensions_node(self, vals):
        return {
            '_tag': 'ext:UBLExtensions',
            'ext:UBLExtension': [
                # First UBLExtension for DIAN details
                {
                    'ext:ExtensionContent': {
                        'sts:DianExtensions': {
                            'sts:InvoiceControl': {
                                'sts:InvoiceAuthorization': {
                                    '_text': vals['journal'].l10n_co_edi_dian_authorization_number
                                },
                                'sts:AuthorizationPeriod': {
                                    'cbc:StartDate': {'_text': vals['journal'].l10n_co_edi_dian_authorization_date},
                                    'cbc:EndDate': {'_text': vals['journal'].l10n_co_edi_dian_authorization_end_date},
                                },
                                'sts:AuthorizedInvoices': {
                                    'sts:Prefix': {'_text': vals['journal'].code},
                                    'sts:From': {'_text': vals['journal'].l10n_co_edi_min_range_number},
                                    'sts:To': {'_text': vals['journal'].l10n_co_edi_max_range_number},
                                },
                            },
                            'sts:InvoiceSource': {
                                'cbc:IdentificationCode': {
                                    '_text': 'CO',
                                    'listAgencyID': '6',
                                    'listAgencyName': 'United Nations Economic Commission for Europe',
                                    'listSchemeURI': 'urn:oasis:names:specification:ubl:codelist:gc:CountryIdentificationCode-2.1',
                                }
                            },
                            'sts:SoftwareProvider': {
                                'sts:ProviderID': {
                                    '_text': vals['company'].partner_id._get_vat_without_verification_code(),
                                    'schemeAgencyID': '195',
                                    'schemeAgencyName': 'CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)',
                                    'schemeID': vals['company'].partner_id._get_vat_verification_code(),
                                    'schemeName': CO_NIT_DIAN_CODE,
                                },
                                'sts:SoftwareID': {
                                    '_text': vals['l10n_co_edi_operation_mode'].dian_software_id,
                                    'schemeAgencyID': '195',
                                    'schemeAgencyName': 'CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)',
                                },
                            },
                            'sts:SoftwareSecurityCode': {
                                '_text': vals['software_security_code'],
                                'schemeAgencyID': '195',
                                'schemeAgencyName': 'CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)',
                            },
                            'sts:AuthorizationProvider': {
                                'sts:AuthorizationProviderID': {
                                    '_text': '800197268',
                                    'schemeAgencyID': '195',
                                    'schemeAgencyName': 'CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)',
                                    'schemeID': '4',
                                    'schemeName': CO_NIT_DIAN_CODE,
                                }
                            },
                            'sts:QRCode': {'_text': vals['qr_code_val']},
                        }
                    }
                },
                # Second UBLExtension for Signature
                {
                    'ext:ExtensionContent': {
                        'ds:Signature': {
                            'Id': vals['document_id'],
                            'ds:SignedInfo': {
                                'ds:CanonicalizationMethod': {'Algorithm': 'http://www.w3.org/TR/2001/REC-xml-c14n-20010315'},
                                'ds:SignatureMethod': {'Algorithm': 'http://www.w3.org/2001/04/xmldsig-more#rsa-sha256'},
                                'ds:Reference': [
                                    {
                                        'Id': f'{vals["document_id"]}-ref0',
                                        'URI': '',
                                        'ds:Transforms': {
                                            'ds:Transform': {'Algorithm': 'http://www.w3.org/2000/09/xmldsig#enveloped-signature'}
                                        },
                                        'ds:DigestMethod': {'Algorithm': 'http://www.w3.org/2001/04/xmlenc#sha256'},
                                        'ds:DigestValue': {'_text': 'dummy'},  # This should be filled in later
                                    },
                                    {
                                        'URI': f'#{vals["key_info_id"]}',
                                        'ds:DigestMethod': {'Algorithm': 'http://www.w3.org/2001/04/xmlenc#sha256'},
                                        'ds:DigestValue': {'_text': 'dummy'},  # This should be filled in later
                                    },
                                    {
                                        'Type': 'http://uri.etsi.org/01903#SignedProperties',
                                        'URI': f'#{vals["document_id"]}-signedprops',
                                        'ds:DigestMethod': {'Algorithm': 'http://www.w3.org/2001/04/xmlenc#sha256'},
                                        'ds:DigestValue': {'_text': 'dummy'},  # This should be filled in later
                                    }
                                ]
                            },
                            'ds:SignatureValue': {
                                '_text': vals['signature_value'],
                                'Id': f'{vals["document_id"]}-sigvalue',
                            },
                            'ds:KeyInfo': {
                                'Id': vals['key_info_id'],
                                'ds:X509Data': {
                                    'ds:X509Certificate': {'_text': vals['x509_certificate']._get_der_certificate_bytes().decode()}
                                }
                            },
                            'ds:Object': {
                                'xades:QualifyingProperties': {
                                    'Target': f'#{vals["document_id"]}',
                                    'xades:SignedProperties': {
                                        'Id': f'{vals["document_id"]}-signedprops',
                                        'xades:SignedSignatureProperties': {
                                            'xades:SigningTime': {'_text': vals['signing_time']},
                                            'xades:SigningCertificate': {
                                                'xades:Cert': [
                                                    {
                                                        'xades:CertDigest': {
                                                            'ds:DigestMethod': {'Algorithm': 'http://www.w3.org/2001/04/xmlenc#sha256'},
                                                            'ds:DigestValue': {'_text': vals['x509_certificate']._get_fingerprint_bytes(formatting='base64').decode()},
                                                        },
                                                        'xades:IssuerSerial': {
                                                            'ds:X509IssuerName': {'_text': cert._get_issuer_string()},
                                                            'ds:X509SerialNumber': {'_text': int(cert.serial_number)},
                                                        }
                                                    } for cert in vals['x509_certificates']
                                                ]
                                            },
                                            'xades:SignaturePolicyIdentifier': {
                                                'xades:SignaturePolicyId': {
                                                    'xades:SigPolicyId': {
                                                        'xades:Identifier': {'_text': 'https:/facturaelectronica.dian.gov.co/politicadefirma/v2/politicadefirmav2.pdf'},
                                                        'xades:Description': {'_text': 'Política de firma para facturas electrónicas de la República de Colombia.'}
                                                    },
                                                    'xades:SigPolicyHash': {
                                                        'ds:DigestMethod': {'Algorithm': 'http://www.w3.org/2001/04/xmlenc#sha256'},
                                                        'ds:DigestValue': {'_text': 'dMoMvtcG5aIzgYo0tIsSQeVJBDnUnfSOfBpxXrmor0Y='},
                                                    }
                                                }
                                            },
                                            'xades:SignerRole': {
                                                'xades:ClaimedRoles': {
                                                    'xades:ClaimedRole': {'_text': vals['claimed_role']}
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            ]
        }

    # -------------------------------------------------------------------------
    # IMPORT
    # -------------------------------------------------------------------------

    def _import_fill_invoice(self, invoice, tree, qty_factor):
        # OVERRIDE account.edi.xml.ubl_20
        logs = super()._import_fill_invoice(invoice, tree, qty_factor)
        cufe = self._find_value("./cbc:UUID[@schemeName='CUFE-SHA384']", tree)
        l10n_co_edi_type = self._find_value("./cbc:InvoiceTypeCode", tree)
        if cufe:
            invoice.l10n_co_edi_cufe_cude_ref = cufe
        if l10n_co_edi_type and l10n_co_edi_type in L10N_CO_EDI_TYPE.values():
            invoice.l10n_co_edi_type = l10n_co_edi_type
        if invoice.is_purchase_document():
            self.env['l10n_co_edi.document']._create_document(
                etree.tostring(tree, encoding='UTF-8'),
                invoice,
                'invoice_accepted',
                attachment_name=f'dian_{invoice.move_type}_{invoice.ref}.xml',
                commercial_state='pending',
                message_json={'status': ''},
            )
        return logs

    def _get_tax_nodes(self, tree):
        tax_nodes = super()._get_tax_nodes(tree)
        # Deepcopy WithholdingTaxTotal elements so it doesn't modify the tree itself
        # the tree eventually gets passed into `_import_attachments'
        for elem in copy.deepcopy(tree.findall('.//{*}WithholdingTaxTotal')):
            percentage_nodes = elem.findall('.//{*}TaxSubtotal/{*}TaxCategory/{*}Percent')
            if not percentage_nodes:
                percentage_nodes = elem.findall('.//{*}TaxSubtotal/{*}Percent')
            # Negate the percentage amount to find the withholding tax in `_retrieve_taxes`
            for node in percentage_nodes:
                negate_percentage = -float(node.text)
                node.text = str(negate_percentage)
            tax_nodes += percentage_nodes
        return tax_nodes

    def _get_basis_qty(self, tree, xpath_dict):
        """ OVERRIDE account.edi.common
        In Colombia, the DIAN treats PriceAmount as the exact unit price,
        so it must not be divided by BaseQuantity."""
        return 1.0
