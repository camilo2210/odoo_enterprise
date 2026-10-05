# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from collections import defaultdict
from datetime import datetime
from json import dumps
from pprint import pformat

from odoo import models, fields, _, api
from odoo.addons.iap.tools.iap_tools import iap_jsonrpc
from odoo.addons.l10n_br_avatax.models.product_template import USE_TYPE_SELECTION
from odoo.exceptions import ValidationError
from odoo.tools import partition, frozendict
from odoo.tools.float_utils import float_round, json_float_round

logger = logging.getLogger(__name__)

IAP_SERVICE_NAME = 'l10n_br_avatax_proxy'
DEFAULT_IAP_ENDPOINT = 'https://l10n-br-avatax.api.odoo.com'
DEFAULT_IAP_TEST_ENDPOINT = 'https://l10n-br-avatax.test.odoo.com'
ICP_LOG_NAME = 'l10n_br_avatax.log.end.date'
AVATAX_PRECISION_DIGITS = 2  # defined by API

COUNTRY_TO_AVATAX_CODE = {
    "MM": "930", "BA": "981", "KP": "1872", "KR": "1902", "HR": "1953", "US": "2496",
    "FK": "2550", "GD": "2976", "IM": "3595", "NL": "5738", "PF": "5991", "SS": "7600",
    "AF": "132", "AL": "175", "DE": "230", "BF": "310", "AD": "370", "AO": "400", "AQ": "420",
    "AG": "434", "SA": "531", "DZ": "590", "AR": "639", "AM": "647", "AW": "655", "AU": "698",
    "AT": "728", "BS": "779", "BH": "809", "BD": "817", "BB": "833", "BY": "850", "BE": "876",
    "BZ": "884", "BM": "906", "BO": "973", "BQ": "3599", "BW": "1015", "BV": "1023", "BR": "1058",
    "BN": "1082", "BG": "1112", "BI": "1155", "CV": "1279", "KY": "1376", "KH": "1414", "CM": "1457",
    "CA": "1490", "GG": "3212", "JE": "3930", "KZ": "1538", "QA": "1546", "CL": "1589", "CN": "1600",
    "CY": "1635", "CO": "1694", "KM": "1732", "CG": "8885", "CK": "1830", "CR": "1961", "KW": "1988",
    "CU": "1996", "BJ": "2291", "DK": "2321", "DM": "2356", "EC": "2399", "EG": "2402", "ER": "2437",
    "AE": "2445", "ES": "2453", "SI": "2461", "SK": "2470", "EE": "2518", "ET": "2534", "PH": "2674",
    "FI": "2712", "FR": "2755", "GA": "2810", "GM": "2852", "GH": "2895", "GE": "2917", "GI": "2933",
    "GR": "3018", "GL": "3050", "GP": "3093", "GU": "3131", "GT": "3174", "GF": "3255", "GN": "3298",
    "GQ": "3310", "GY": "3379", "HT": "3417", "HM": "3433", "HN": "3450", "HK": "3514", "HU": "3557",
    "YE": "3573", "IN": "3611", "ID": "3654", "IQ": "3697", "IE": "3751", "IS": "3794", "IL": "3832",
    "IT": "3867", "JM": "3913", "JP": "3999", "JO": "4030", "KI": "4111", "LA": "4200", "LS": "4260",
    "LV": "4278", "LB": "4316", "LR": "4340", "LY": "4383", "LI": "4405", "LT": "4421", "LU": "4456",
    "MK": "4499", "MG": "4502", "MY": "4553", "MW": "4588", "MV": "4618", "ML": "4642", "MT": "4677",
    "MA": "4740", "MH": "4766", "MQ": "4774", "MU": "4855", "MR": "4880", "MX": "4936", "MD": "4944",
    "MC": "4952", "MN": "4979", "ME": "4985", "FM": "4995", "MS": "5010", "MZ": "5053", "NA": "5070",
    "NR": "5088", "CX": "5118", "NP": "5177", "NI": "5215", "NE": "5258", "NG": "5282", "NU": "5312",
    "NF": "5355", "NO": "5380", "NC": "5428", "PG": "5452", "NZ": "5487", "VU": "5517", "OM": "5568",
    "PW": "5754", "PK": "5762", "PS": "5780", "PA": "5800", "PY": "5860", "PE": "5894", "PN": "5932",
    "PL": "6033", "PT": "6076", "PR": "6114", "KE": "6238", "KG": "6254", "UA": "8311", "CF": "6408",
    "DO": "6475", "ZW": "6653", "RO": "6700", "RW": "6750", "RU": "6769", "EH": "6858", "SV": "6874",
    "WS": "6904", "AS": "6912", "SM": "6971", "VC": "7056", "SH": "7102", "LC": "7153", "SN": "7285",
    "SC": "7315", "SL": "7358", "RS": "7370", "SG": "7412", "SY": "7447", "SO": "7480", "LK": "7501",
    "SZ": "7544", "ZA": "7560", "SD": "7595", "SE": "7641", "CH": "7676", "SR": "7706", "TH": "7765",
    "TZ": "7803", "TD": "7889", "CZ": "7919", "TG": "8001", "TO": "8109", "TT": "8150", "TN": "8206",
    "TC": "8230", "TM": "8249", "TR": "8273", "TV": "8281", "UG": "8338", "UY": "8451", "UZ": "8478",
    "VA": "8486", "VE": "8508", "VN": "8583", "VG": "8630", "VI": "8664", "FJ": "8702", "WF": "8753",
    "ZM": "8907",
}

COUNTRY_TO_ALPHA_3_CODE = {
    "BD": "BGD", "BE": "BEL", "BF": "BFA", "BG": "BGR", "BA": "BIH", "BB": "BRB", "WF": "WLF", "BL": "BLM", "BM": "BMU",
    "BN": "BRN", "BO": "BOL", "BH": "BHR", "BI": "BDI", "BJ": "BEN", "BT": "BTN", "JM": "JAM", "BV": "BVT", "BW": "BWA",
    "WS": "WSM", "BQ": "BES", "BR": "BRA", "BS": "BHS", "JE": "JEY", "BY": "BLR", "BZ": "BLZ", "RU": "RUS", "RW": "RWA",
    "RS": "SRB", "TL": "TLS", "RE": "REU", "TM": "TKM", "TJ": "TJK", "RO": "ROU", "TK": "TKL", "GW": "GNB", "GU": "GUM",
    "GT": "GTM", "GS": "SGS", "GR": "GRC", "GQ": "GNQ", "GP": "GLP", "JP": "JPN", "GY": "GUY", "GG": "GGY", "GF": "GUF",
    "GE": "GEO", "GD": "GRD", "GB": "GBR", "GA": "GAB", "SV": "SLV", "GN": "GIN", "GM": "GMB", "GL": "GRL", "GI": "GIB",
    "GH": "GHA", "OM": "OMN", "TN": "TUN", "JO": "JOR", "HR": "HRV", "HT": "HTI", "HU": "HUN", "HK": "HKG", "HN": "HND",
    "HM": "HMD", "VE": "VEN", "PR": "PRI", "PS": "PSE", "PW": "PLW", "PT": "PRT", "SJ": "SJM", "PY": "PRY", "IQ": "IRQ",
    "PA": "PAN", "PF": "PYF", "PG": "PNG", "PE": "PER", "PK": "PAK", "PH": "PHL", "PN": "PCN", "PL": "POL", "PM": "SPM",
    "ZM": "ZMB", "EH": "ESH", "EE": "EST", "EG": "EGY", "ZA": "ZAF", "EC": "ECU", "IT": "ITA", "VN": "VNM", "SB": "SLB",
    "ET": "ETH", "SO": "SOM", "ZW": "ZWE", "SA": "SAU", "ES": "ESP", "ER": "ERI", "ME": "MNE", "MD": "MDA", "MG": "MDG",
    "MF": "MAF", "MA": "MAR", "MC": "MCO", "UZ": "UZB", "MM": "MMR", "ML": "MLI", "MO": "MAC", "MN": "MNG", "MH": "MHL",
    "MK": "MKD", "MU": "MUS", "MT": "MLT", "MW": "MWI", "MV": "MDV", "MQ": "MTQ", "MP": "MNP", "MS": "MSR", "MR": "MRT",
    "IM": "IMN", "UG": "UGA", "TZ": "TZA", "MY": "MYS", "MX": "MEX", "IL": "ISR", "FR": "FRA", "IO": "IOT", "SH": "SHN",
    "FI": "FIN", "FJ": "FJI", "FK": "FLK", "FM": "FSM", "FO": "FRO", "NI": "NIC", "NL": "NLD", "NO": "NOR", "NA": "NAM",
    "VU": "VUT", "NC": "NCL", "NE": "NER", "NF": "NFK", "NG": "NGA", "NZ": "NZL", "NP": "NPL", "NR": "NRU", "NU": "NIU",
    "CK": "COK", "XK": "XKX", "CI": "CIV", "CH": "CHE", "CO": "COL", "CN": "CHN", "CM": "CMR", "CL": "CHL", "CC": "CCK",
    "CA": "CAN", "CG": "COG", "CF": "CAF", "CD": "COD", "CZ": "CZE", "CY": "CYP", "CX": "CXR", "CR": "CRI", "CW": "CUW",
    "CV": "CPV", "CU": "CUB", "SZ": "SWZ", "SY": "SYR", "SX": "SXM", "KG": "KGZ", "KE": "KEN", "SS": "SSD", "SR": "SUR",
    "KI": "KIR", "KH": "KHM", "KN": "KNA", "KM": "COM", "ST": "STP", "SK": "SVK", "KR": "KOR", "SI": "SVN", "KP": "PRK",
    "KW": "KWT", "SN": "SEN", "SM": "SMR", "SL": "SLE", "SC": "SYC", "KZ": "KAZ", "KY": "CYM", "SG": "SGP", "SE": "SWE",
    "SD": "SDN", "DO": "DOM", "DM": "DMA", "DJ": "DJI", "DK": "DNK", "VG": "VGB", "DE": "DEU", "YE": "YEM", "DZ": "DZA",
    "US": "USA", "UY": "URY", "YT": "MYT", "UM": "UMI", "LB": "LBN", "LC": "LCA", "LA": "LAO", "TV": "TUV", "TW": "TWN",
    "TT": "TTO", "TR": "TUR", "LK": "LKA", "LI": "LIE", "LV": "LVA", "TO": "TON", "LT": "LTU", "LU": "LUX", "LR": "LBR",
    "LS": "LSO", "TH": "THA", "TF": "ATF", "TG": "TGO", "TD": "TCD", "TC": "TCA", "LY": "LBY", "VA": "VAT", "VC": "VCT",
    "AE": "ARE", "AD": "AND", "AG": "ATG", "AF": "AFG", "AI": "AIA", "VI": "VIR", "IS": "ISL", "IR": "IRN", "AM": "ARM",
    "AL": "ALB", "AO": "AGO", "AQ": "ATA", "AS": "ASM", "AR": "ARG", "AU": "AUS", "AT": "AUT", "AW": "ABW", "IN": "IND",
    "AX": "ALA", "AZ": "AZE", "IE": "IRL", "ID": "IDN", "UA": "UKR", "QA": "QAT", "MZ": "MOZ"
}


class AccountExternalTaxMixin(models.AbstractModel):
    """ Brazilian Avatax adaptations. This class requires the following fields on the inherited model:
    - company_id (res.company): the company the record belongs to,
    - country_code (Char): the country code of the company this record belongs to,
    - fiscal_position_id (account.fiscal.position): fiscal position used for this record,
    - currency_id (res.currency): currency used on the record,
    - partner_shipping_id (res.partner): delivery address, where services are rendered or goods are delivered,
    - partner_id (res.partner): the end customer of the transaction,
    """
    _inherit = 'account.external.tax.mixin'

    l10n_br_is_service_transaction = fields.Boolean(
        "Is Service Transaction",
        compute="_compute_l10n_br_is_service_transaction",
        help="Technical field used to determine if this transaction should be sent to the service or goods API.",
    )
    l10n_br_cnae_code_id = fields.Many2one(
        "l10n_br.cnae.code",
        string="CNAE Code",
        compute="_compute_l10n_br_cnae_code_id",
        store=True,
        readonly=False,
        help="Brazil: the company's CNAE code for tax calculation and EDI."
    )
    l10n_br_goods_operation_type_id = fields.Many2one(
        "l10n_br.operation.type",
        compute="_compute_l10n_br_goods_operation_type_id",
        store=True,
        readonly=False,
        copy=False,
        string="Goods Operation Type",
        help="Brazil: this is the operation type related to the goods transaction. This will be used as a default on transaction lines."
    )
    l10n_br_use_type = fields.Selection(
        USE_TYPE_SELECTION,
        string="Purpose of Use",
        help="Brazil: this will override the purpose of use for all products sold here."
    )
    l10n_br_is_avatax = fields.Boolean(
        compute="_compute_l10n_br_is_avatax",
        string="Is Brazilian Avatax",
        help="Technical field used to check if this record requires tax calculation or EDI via Avatax."
    )
    # Technical field that holds errors meant for the actionable_errors widget.
    l10n_br_avatax_warnings = fields.Json(compute="_compute_l10n_br_avatax_warnings")
    l10n_br_edi_avatax_data = fields.Json(
        help="Brazil: technical field that remembers the last tax summary returned by Avatax.", copy=False
    )

    def _compute_l10n_br_is_service_transaction(self):
        """Should be overridden. Used to determine if we should treat this record as a service (NFS-e) record."""
        self.l10n_br_is_service_transaction = False

    @api.depends('company_id')
    def _compute_l10n_br_cnae_code_id(self):
        for record in self:
            record.l10n_br_cnae_code_id = self.company_id.l10n_br_cnae_code_id

    @api.depends('country_code', 'fiscal_position_id')
    def _compute_l10n_br_goods_operation_type_id(self):
        """Set the default operation type which is standardSales. Should be overridden to determine
        the document type for the model."""
        for record in self:
            record.l10n_br_goods_operation_type_id = self.env.ref("l10n_br_avatax.operation_type_1") if record._l10n_br_is_avatax() else False

    def _compute_l10n_br_is_avatax_depends(self):
        return ['country_code', 'fiscal_position_id']

    @api.depends(lambda self: self._compute_l10n_br_is_avatax_depends())
    def _compute_l10n_br_is_avatax(self):
        for record in self:
            record.l10n_br_is_avatax = record._l10n_br_is_avatax()

    def _compute_is_tax_computed_externally(self):
        super()._compute_is_tax_computed_externally()
        self.filtered(lambda record: record.l10n_br_is_avatax).is_tax_computed_externally = True

    def _l10n_br_is_avatax(self):
        return self.country_code == 'BR' and self.fiscal_position_id.l10n_br_is_avatax

    def _depends_l10n_br_avatax_warnings(self):
        """Provides dependencies that trigger recomputation of l10n_br_avatax. Model-specific fields should be added
        with an override."""
        return ["l10n_br_is_avatax", "l10n_br_is_service_transaction", "currency_id", "company_id"]

    def _l10n_br_avatax_check_company(self):
        company_sudo = self.company_id.sudo()
        api_id, api_key = company_sudo.l10n_br_avatax_api_identifier, company_sudo.l10n_br_avatax_api_key
        if not api_id or not api_key:
            return {
                "missing_avatax_account": {
                    "message": _("Please create an Avatax account"),
                    "action_text": _("Go to the configuration panel"),
                    "action": self.env.ref('account.action_account_config').with_company(company_sudo)._get_action_dict(),
                    "level": "danger",
                }
            }

        return {}

    def _l10n_br_avatax_check_currency(self):
        if self.currency_id.name != 'BRL':
            return {
                "bad_currency": {
                    "message": _("Brazilian Real is required to calculate taxes with Avatax."),
                    "level": "danger",
                }
            }

        return {}

    @api.model
    def _l10n_br_avatax_check_lines(self, lines, is_service):
        errors = {}

        for line in lines:
            product = line['tempProduct']
            cean = line['itemDescriptor']['cean']
            if not product:
                errors["required_product"] = {
                    "message": _("A product is required on each line when using Avatax."),
                    "level": "danger",
                }
            elif cean and (not cean.isdigit() or not (len(cean) == 8 or 12 <= len(cean) <= 14)):
                errors["bad_cean"] = {
                    "message": _("The barcode of %s must have either 8, or 12 to 14 digits when using Avatax.", product.display_name),
                    "level": "danger",
                }

            if line['lineAmount'] < line['lineTaxedDiscount']:
                errors["negative_line"] = {
                    "message": _("The document amount must be positive."),
                    "level": "danger",
                }

        if not self._l10n_br_get_non_transport_lines(lines):
            errors["non_transport_line"] = {
                "message": _("Avatax requires at least one non-transport line."),
                "level": "danger",
            }

        service_lines, consumable_lines = partition(
            lambda line: line["tempProduct"].product_tmpl_id._l10n_br_is_only_allowed_on_service_invoice(), lines
        )

        if not is_service:
            if service_lines:
                service_products = self.env["product.product"].union(line["tempProduct"] for line in service_lines)
                errors["disallowed_service_products"] = {
                    "message": _(
                        "%(transaction)s is a goods transaction but has service products:\n%(products)s.",
                        transaction=self.display_name,
                        products=service_products.mapped('display_name'),
                    ),
                    "action_text": _("View products"),
                    "action": service_products._get_records_action(name=_("View Product(s)")),
                    "level": "danger",
                }
        else:
            if consumable_lines:
                consumable_products = self.env["product.product"].union(line["tempProduct"] for line in consumable_lines)
                errors["disallowed_goods_products"] = {
                    "message": _(
                        "%(transaction)s is a service transaction but has non-service products:\n%(products)s",
                        transaction=self.display_name,
                        products=consumable_products.mapped('display_name'),
                    ),
                    "action_text": _("View products"),
                    "action": consumable_products._get_records_action(name=_("View Product(s)")),
                    "level": "danger",
                }

        return errors

    @api.model
    def _l10n_br_avatax_check_missing_fields_product(self, lines):
        res = {}
        incomplete_products = self.env['product.product']

        for line in lines:
            product = line['tempProduct']
            if product and not product.l10n_br_ncm_code_id:
                incomplete_products |= product

        if incomplete_products:
            res["products_missing_fields_danger"] = {
                    "message": _(
                        "For Brazilian tax calculation you must set a Mercosul NCM Code on the following:\n%(products)s",
                        products=incomplete_products.mapped("display_name")
                    ),
                    "action_text": _("View products"),
                    "action": incomplete_products._l10n_br_avatax_action_missing_fields(self.l10n_br_is_service_transaction),
                    "level": "danger",
                }

        return res

    def _l10n_br_avatax_check_partner(self):
        res = {}
        if self.l10n_br_is_service_transaction and self.partner_shipping_id.country_id.code == 'BR':
            partner = self.partner_shipping_id
            city = partner.city_id
            if not city or city.country_id.code != "BR":
                res["missing_city"] = {
                    "message": _("%s must have a city selected in the list of Brazil's cities.", partner.display_name),
                    "action_text": _("View customer"),
                    "action": partner._get_records_action(),
                    "level": "danger",
                }

        return res

    @api.depends(lambda self: self._depends_l10n_br_avatax_warnings())
    def _compute_l10n_br_avatax_warnings(self):
        for record in self:
            if not record.l10n_br_is_avatax:
                record.l10n_br_avatax_warnings = False
                continue

            params = record._get_l10n_br_avatax_service_params()
            lines = self._prepare_l10n_br_avatax_document_lines_service_call(
                params['line_data'],
                params['use_type'],
                params['cnae'],
                params['is_service'],
                params['partner_shipping'],
                params['company'],
            )
            record.l10n_br_avatax_warnings = {
                **record._l10n_br_avatax_check_company(),
                **record._l10n_br_avatax_check_currency(),
                **record._l10n_br_avatax_check_lines(lines, params['is_service']),
                **record._l10n_br_avatax_check_missing_fields_product(lines),
                **record._l10n_br_avatax_check_partner(),
            }

    def _l10n_br_avatax_blocking_errors(self):
        """Only consider 'danger' level errors to be blocking. Other ones are considered warnings."""
        return [error for error in (self.l10n_br_avatax_warnings or {}).values() if error.get('level') == 'danger']

    def _l10n_br_avatax_log(self):
        self.env['account.external.tax.mixin']._enable_external_tax_logging(ICP_LOG_NAME)
        return True

    def _l10n_br_avatax_handle_response(self, service_params, response, title):
        if response.get('error'):
            inner_errors = []
            for error in response['error'].get('innerError', []):
                # Useful inner errors are line-specific. Ones that aren't are typically not useful for the user.
                if 'lineCode' not in error:
                    continue

                product_name = self.env[service_params['line_model_name']].browse(error['lineCode']).product_id.display_name

                inner_errors.append(_('What:'))
                inner_errors.append('- %s: %s' % (product_name, error['message']))

                where = error.get('where', {})
                if where:
                    inner_errors.append(_('Where:'))
                for where_key, where_value in sorted(where.items()):
                    if where_key == 'date':
                        continue
                    inner_errors.append('- %s: %s' % (where_key, where_value))

            return '%s\n%s\n%s' % (title, response['error']['message'], '\n'.join(inner_errors))

        return None

    @api.model
    def _l10n_br_get_non_transport_lines(self, lines):
        return [line for line in lines if not line['tempTransportCostType']]

    @api.model
    def _l10n_br_remove_temp_values_lines(self, lines):
        for line in lines:
            del line['tempTransportCostType']
            del line['tempProduct']

    @api.model
    def _l10n_br_repr_amounts(self, lines):
        """ Ensures all amount fields have the right amount of decimals before sending it to the API. """
        for line in lines:
            for amount_field in ('lineAmount', 'freightAmount', 'insuranceAmount', 'otherCostAmount'):
                line[amount_field] = json_float_round(line[amount_field], AVATAX_PRECISION_DIGITS)

    @api.model
    def _l10n_br_get_partner_type(self, partner):
        if partner.country_code not in ('BR', False):
            return 'foreign'
        elif partner.is_company:
            return 'business'
        else:
            return 'individual'

    @api.model
    def _l10n_br_get_taxes_settings(self, is_service, partner):
        if is_service:
            settings = {
                'cofinsSubjectTo': partner.l10n_br_subject_cofins,
                'pisSubjectTo': partner.l10n_br_subject_pis,
                'csllSubjectTo': 'T' if partner.l10n_br_is_subject_csll else 'E',
            }
            regime = partner.l10n_br_tax_regime
            if regime and regime.startswith('simplified'):
                settings['issRfRateForSimplesTaxRegime'] = partner.l10n_br_iss_simples_rate

            return settings
        else:
            return {'icmsTaxPayer': partner.l10n_br_taxpayer == 'icms'}

    @api.model
    def _l10n_br_deep_update_dict(self, d, u):
        """Like {}.update but handles nested dicts recursively. Based on https://stackoverflow.com/a/3233356."""
        for k, v in u.items():
            if isinstance(v, dict):
                d[k] = self._l10n_br_deep_update_dict(d.get(k, {}), v)
            else:
                d[k] = v
        return d

    @api.model
    def _l10n_br_deep_clean_dict(self, d):
        """Recursively removes keys with a falsy value in dicts. Based on https://stackoverflow.com/a/48152075."""
        cleaned_dict = {}
        for k, v in d.items():
            # Avalara will assign the wrong CFOP if some falsy fields are missing.
            if isinstance(v, dict) and k != 'taxesSettings':
                v = self._l10n_br_deep_clean_dict(v)
            if v:
                cleaned_dict[k] = v
        return cleaned_dict or None

    @api.model
    def _l10n_br_get_location_dict(self, partner, is_export=False):
        # 'partner' may be empty, e.g. when the invoice has no transporter.
        federal_tax_id = partner._get_preferred_legal_entity_identifier_vals().get('value', '') if partner else ''
        return {
            "name": partner.name or partner.display_name,
            "businessName": partner.name or partner.display_name,
            "type": self._l10n_br_get_partner_type(partner),
            "federalTaxId": "9999999999" if is_export else federal_tax_id,
            "cityTaxId": partner.l10n_br_im_code,
            "stateTaxId": partner.l10n_br_ie_code,
            "suframa": partner.l10n_br_isuf_code,
            "address": {
                "neighborhood": "EXTERIOR" if is_export else partner.street2,
                "street": partner.street_name,
                "zipcode": "99999999" if is_export else partner.zip,
                "cityName": "EXTERIOR" if is_export else partner.city,
                'cityCode': '9999999' if is_export else '',
                "state": "EX" if is_export else partner.state_id.code,
                'country': COUNTRY_TO_ALPHA_3_CODE.get(partner.country_code, 'BRA'),
                "countryCode": COUNTRY_TO_AVATAX_CODE.get(partner.country_code),
                "number": partner.street_number,
                "complement": partner.street_number2,
                "phone": partner.phone,
                "email": partner.email,
            },
            "activitySector": {
              "code": partner.l10n_br_activity_sector,
            },
            "taxRegime": partner.l10n_br_tax_regime,
        }

    @api.model
    def _l10n_br_get_locations(self, params):
        customer = params['partner']
        company_partner = params['company_partner']
        partner_shipping = params['partner_shipping']

        is_service = params['is_service']
        is_export = params['is_export_goods']

        # For customer
        entity_location = self._l10n_br_get_location_dict(customer, is_export)
        entity_location['taxesSettings'] = self._l10n_br_get_taxes_settings(is_service, customer)

        # For company
        establishment_location = self._l10n_br_get_location_dict(company_partner)
        establishment_location['taxesSettings'] = self._l10n_br_get_taxes_settings(is_service, company_partner)
        if company_partner.l10n_br_tax_regime == 'simplified':
            establishment_location['taxesSettings']['pCredSN'] = params['company'].l10n_br_icms_rate
        if cnae := params['cnae']:
            establishment_location['activitySector']['ActivitySector_CNAE'] = {'code': cnae.sanitized_code}

        # For when services was provided at a different delivery address
        partner_shipping_location = {}
        if partner_shipping != customer:
            partner_shipping_content = self._l10n_br_get_location_dict(partner_shipping)

            key = 'rendered' if is_service else 'delivery'
            partner_shipping_location[key] = partner_shipping_content

        return {
            "entity": entity_location,
            "establishment": establishment_location,
            **partner_shipping_location,
        }

    def _get_l10n_br_avatax_service_params(self):
        params = self._get_external_tax_service_params()

        params.update({
            'operation_type': self.l10n_br_goods_operation_type_id,
            'invoice_refs': {},
            'installments': {},
            'id': self.id,
            'model_name': self._name,
            'line_model_name': self._name + '.line',
            'partner': self.partner_id,
            'company': self.company_id,
            'use_type': self.l10n_br_use_type,
            'cnae': self.l10n_br_cnae_code_id,
            'is_service': self.l10n_br_is_service_transaction,
            'is_return': self.l10n_br_goods_operation_type_id.technical_name == 'salesReturn',

            # To be filled by models
            'partner_shipping': None,
            'origin_record': None,

            # For NF-e export
            'is_export_goods': None,
            'shipping_state_id': None,
            'incoterm_location': None,
        })
        return params

    @api.model
    def _prepare_l10n_br_avatax_document_line_service_call(self, line_data, record_use_type, cnae, is_service, partner_shipping, company):
        """ Prepares the line data for the /calculations API call. temp* values are here to help with post-processing
        and will be removed before sending by _remove_temp_values_lines.
        """
        # Transform the descriptions of the lines to something Avatax will trim correctly.
        description = line_data['description'] and line_data['description'].replace("\n", " | ")

        base_line = line_data['base_line']
        product = base_line['product_id']
        op_type = line_data['operation_type']
        dispatched_discount_amount = abs(sum(
            disc_line['tax_details']['raw_total_excluded_currency']
            for disc_line in base_line.get('discount_base_lines', [])
        ))
        line = {
            'lineCode': base_line['id'],
            'useType': op_type.l10n_br_use_type or record_use_type or product.l10n_br_use_type,
            'operationType': op_type.technical_name,
            'otherCostAmount': 0,
            'freightAmount': 0,
            'insuranceAmount': 0,
            'lineTaxedDiscount': base_line['quantity'] * base_line['price_unit'] * (base_line['discount'] / 100.0) + dispatched_discount_amount,
            'lineAmount': base_line['quantity'] * base_line['price_unit'],
            'lineUnitPrice': base_line['price_unit'],
            'numberOfItems': base_line['quantity'],
            'itemDescriptor': {
                'description': description or product.display_name or '',
                'cean': product.barcode or '',
            },
            'tempTransportCostType': product.l10n_br_transport_cost_type,
            'tempProduct': product,
        }

        descriptor = line['itemDescriptor']

        # Sending false or empty string returns errors
        if cnae:
            descriptor['cnae'] = cnae.sanitized_code

        if is_service:
            line['benefitsAbroad'] = partner_shipping.country_id.code != 'BR'
            descriptor['serviceCodeOrigin'] = product.l10n_br_property_service_code_origin_id.code
            descriptor['withLaborAssignment'] = product.l10n_br_labor
            descriptor['hsCode'] = product.l10n_br_ncm_code_id.code or ''

            # Explicitly filter on company, this can be called via controllers which run as superuser and bypass record rules.
            service_codes = product.product_tmpl_id.l10n_br_service_code_ids.filtered(lambda code: code.company_id == company)
            descriptor['serviceCode'] = (
                service_codes.filtered(lambda code: code.city_id == partner_shipping.city_id).code
                or product.l10n_br_property_service_code_origin_id.code
            )
            # Override the CNAE code if the product has a specific one.
            if product.l10n_br_ncm_code_id.l10n_br_cnae_code_id:
                descriptor['cnae'] = product.l10n_br_ncm_code_id.l10n_br_cnae_code_id.sanitized_code
        else:
            descriptor['cest'] = product.l10n_br_cest_code or ''
            descriptor['source'] = op_type.l10n_br_source_origin or product.l10n_br_source_origin or ''
            descriptor['productType'] = op_type.l10n_br_sped_type or product.l10n_br_sped_type or ''
            descriptor['hsCode'] = (product.l10n_br_ncm_code_id.code or '').replace('.', '')
            if product.l10n_br_ncm_code_id.ex:
                descriptor['ex'] = product.l10n_br_ncm_code_id.ex

            uom = base_line['product_uom_id']
            descriptor['unitTaxable'] = uom.name[:6] if uom else ''  # the maximum length allowed by the API is 6
            descriptor['unit'] = uom.name[:6] if uom else ''
            descriptor.update({
                'manufacturerEquivalent': op_type.l10n_br_issuer_manufacturer_industry_equivalent,
                'appropriateIPIcreditWhenInGoing': op_type.l10n_br_issuer_appropriate_ipi_credit,
                'notSubjectToIcmsSt': op_type.l10n_br_issuer_not_subject_to_icmsst,
                'isIcmsStSubstitute': op_type.l10n_br_issuer_is_icmsst_substitute,
                'appropriateICMScreditWhenInGoing': op_type.l10n_br_issuer_appropriate_icms_credit,
                'appropriatePISCOFINScreditWhenInGoing': op_type.l10n_br_issuer_appropriate_piscofins_credit,
            })
            line['goods'] = {'entityOwnProduction': op_type.l10n_br_recipient_manufacturer_industry_equivalent}
            if is_substitute := op_type.l10n_br_recipient_is_icmsst_substitute:
                line['goods']['entityIcmsStSubstitute'] = is_substitute

            if order_number := line_data.get('order_number'):
                line['orderNumber'] = order_number
            if order_item_number := line_data.get('order_item_number'):
                line['orderItemNumber'] = order_item_number

        return line

    @api.model
    def _l10n_br_distribute_transport_cost_over_lines(self, lines, transport_cost_type):
        """ Avatax requires transport costs to be specified per line. This distributes transport costs (indicated by
        their product's l10n_br_transport_cost_type) over the lines in proportion to their subtotals. """
        type_to_api_field = {
            'freight': 'freightAmount',
            'insurance': 'insuranceAmount',
            'other': 'otherCostAmount',
        }
        api_field = type_to_api_field[transport_cost_type]

        transport_lines = [line for line in lines if line['tempTransportCostType'] == transport_cost_type]
        regular_lines = self._l10n_br_get_non_transport_lines(lines)
        total = sum(line['lineAmount'] for line in regular_lines)

        if not regular_lines:
            # _compute_l10n_br_avatax_warnings() will inform the user about this
            return []

        for transport_line in transport_lines:
            transport_net = transport_line['lineAmount'] - transport_line['lineTaxedDiscount']
            remaining = transport_net
            for line in regular_lines[:-1]:
                current_cost = float_round(
                    transport_net * (line['lineAmount'] / total),
                    precision_digits=AVATAX_PRECISION_DIGITS
                )
                remaining -= current_cost
                line[api_field] += current_cost

            # put remainder on last line to avoid rounding issues
            regular_lines[-1][api_field] += remaining

        return [line for line in lines if line['tempTransportCostType'] != transport_cost_type]

    @api.model
    def _prepare_l10n_br_avatax_document_lines_service_call(self, line_datas, use_type, cnae, is_service, partner_shipping, company):
        lines = [self._prepare_l10n_br_avatax_document_line_service_call(line_data, use_type, cnae, is_service, partner_shipping, company) for line_data in line_datas]
        lines = self._l10n_br_distribute_transport_cost_over_lines(lines, 'freight')
        lines = self._l10n_br_distribute_transport_cost_over_lines(lines, 'insurance')
        lines = self._l10n_br_distribute_transport_cost_over_lines(lines, 'other')
        return lines

    @api.model
    def _prepare_l10n_br_avatax_document_service_call(self, params):
        """ Returns the full payload containing one record to be used in a /transactions API call. """

        is_service = params['is_service']
        lines = self._prepare_l10n_br_avatax_document_lines_service_call(
            params['line_data'],
            params['use_type'],
            params['cnae'],
            is_service,
            params['partner_shipping'],
            params['company']
        )
        self._l10n_br_remove_temp_values_lines(lines)
        self._l10n_br_repr_amounts(lines)

        payments = {}
        if installments := params['installments']:
            payments = {'payment': installments}

        goods = {}
        if params['is_export_goods']:
            goods = {
                'idDest': 3,
            }
            if params['shipping_state_id'] and params['incoterm_location']:
                goods['exportInfo'] = {
                    'shippingState': params['shipping_state_id'].code,
                    'place': params['incoterm_location'][:60],
                }

        return self._l10n_br_deep_clean_dict({
            'header': {
                'transactionDate': (params['document_date'] or fields.Date.today()).isoformat(),
                'amountCalcType': 'gross',
                'documentCode': '%s_%s' % (params['model_name'], params['id']),
                'messageType': 'services' if is_service else 'goods',
                'companyLocation': params['company_partner'].vat,
                'operationType': params['operation_type'].technical_name,
                **params['invoice_refs'],
                'locations': self._l10n_br_get_locations(params),
                'goods': goods,
                **payments,
            },
            'lines': lines,
        })

    @api.model
    def _extract_tax_values_from_l10n_br_avatax_detail(self, service_params, line_detail, tax_detail):
        tax_amount = tax_detail['tax']

        if tax_detail['taxImpact']['impactOnNetAmount'] == 'Subtracted':
            tax_amount *= -1

        base_amount_currency = line_detail['lineNetFigure']
        # The service API already accounts for the discount in the net figure.
        if not service_params['is_service']:
            base_amount_currency -= line_detail['lineTaxedDiscount']

        if tax_detail['taxImpact']['impactOnNetAmount'] == 'Informative' or tax_detail["taxImpact"]["accounting"] == "none":
            return None

        return (
            {'name': 'Avalara Brazil', 'company_id': service_params['company'].id},
            {
                'name': tax_detail['taxType'],
                'l10n_br_avatax_code': tax_detail['taxType'],
                'company_id': service_params['company'].id,
                'amount': 1,
                'amount_type': 'percent',
                'price_include_override': 'tax_included' if tax_detail['taxImpact']['impactOnNetAmount'] == 'Included' else 'tax_excluded',
                **({'type_tax_use': self.invoice_filter_type_domain} if 'invoice_filter_type_domain' in self._fields else {})
            },
            {'tax_amount_currency': tax_amount, 'base_amount_currency': base_amount_currency},
        )

    def _l10n_br_call_avatax_taxes(self, company, document_data):
        # To allow saving this response in l10n_br_edi.
        api_response = self.env['account.external.tax.mixin']._l10n_br_iap_calculate_tax(document_data, company)

        # Store the retrieved Avatax data
        self.l10n_br_edi_avatax_data = {
            "header": api_response.get("header"),
            "lines": api_response.get("lines"),
            "summary": api_response.get("summary"),
        }

        return api_response

    def _get_external_tax_service_params(self):
        """Override to filter out negative lines. Negative lines will be dispatched
        into valid positive ones.
        """
        params = super()._get_external_tax_service_params()
        if not self.l10n_br_is_avatax:
            return params

        AccountTax = self.env['account.tax']
        # Extract base_lines from line_data
        line_data = params['line_data']
        base_lines = []
        for index, data in enumerate(line_data):
            base_line = data['base_line']
            base_line['_index'] = index
            if base_line['tax_details']['raw_total_excluded_currency'] < 0 and not base_line['special_type']:
                # Set key to identify discount lines later at '_dispatch_global_discount_lines'
                base_line['special_type'] = 'global_discount'

            clean_base_line = AccountTax._prepare_base_line_for_taxes_computation(
                base_line,
                tax_ids=[],
                special_type=base_line['special_type'],
                _original_record=base_line['record'],
                _original_data=data,
                _original_base_line=base_line,
                _index=index,
            )
            clean_base_line['record'] = clean_base_line['_original_record']
            base_lines.append(clean_base_line)

        AccountTax._add_tax_details_in_base_lines(base_lines, self.company_id)
        AccountTax._round_base_lines_tax_details(base_lines, self.company_id)
        aggregated_base_lines = self.env['account.tax']._dispatch_global_discount_lines(base_lines, self.company_id)

        return {
            **params,
            'line_data': [
                {
                    **base_line['_original_data'],
                    'base_line': base_line,
                }
                for base_line in aggregated_base_lines
            ],
        }

    def _get_external_taxes(self):
        # EXTENDS 'account.external.tax.mixin'
        res = super()._get_external_taxes()

        br_records = self.filtered(lambda record: record.l10n_br_is_avatax)

        errors = []
        for record in br_records:
            if blocking := record._l10n_br_avatax_blocking_errors():
                errors.append(_(
                    "Taxes cannot be calculated for %(record)s:\n%(errors)s",
                    record=record.display_name, errors="\n".join(f"- {msg['message']}" for msg in blocking)
                ))

        if errors:
            raise ValidationError('\n\n'.join(errors))

        for company, records in br_records.grouped("company_id").items():
            base_line_with_tax_values = []
            for record in records:
                service_params = record._get_l10n_br_avatax_service_params()
                document_data = record._prepare_l10n_br_avatax_document_service_call(service_params)
                base_lines = [data['base_line'] for data in service_params['line_data']]

                api_response = self._l10n_br_call_avatax_taxes(company, document_data)
                error = self._l10n_br_avatax_handle_response(service_params, api_response, _(
                    'Odoo could not fetch the taxes related to %(document)s.',
                    document=record.display_name,
                ))
                if error:
                    errors.append(error)
                    continue

                for base_line, line_results in zip(base_lines, api_response['lines']):
                    # Reset manual field since it is possible that some discount lines were removed or added
                    tax_values_list = []
                    for tax_detail in line_results['taxDetails']:
                        if extracted_tax_info := record._extract_tax_values_from_l10n_br_avatax_detail(service_params, line_results, tax_detail):
                            tax_values_list.append(extracted_tax_info)
                    base_line_with_tax_values.append((base_line, tax_values_list))

            if errors:
                raise ValidationError('\n\n'.join(errors))

            res.update(self._process_external_taxes(company, base_line_with_tax_values, 'l10n_br_avatax_code', search_archived_taxes=True))

        return res

    def _process_external_taxes(self, company, base_line_with_tax_values, tax_key_field, search_archived_taxes=False):
        """EXTENDS account_external_tax. Extract original 'discount_base_lines' from each base line and obtain the theorical.
        tax and base amount obtained from rpc call for each discount line.
        """
        if tax_key_field != 'l10n_br_avatax_code':
            return super()._process_external_taxes(company, base_line_with_tax_values, tax_key_field, search_archived_taxes)

        AccountTax = self.env['account.tax']
        to_group_together = defaultdict(lambda: {'to_aggregate': []})
        new_base_line_with_tax_values = []
        for base_line, tax_values_list in base_line_with_tax_values:
            # No discount line to distribute.
            discount_base_lines = base_line.get('discount_base_lines')
            if not discount_base_lines:
                new_base_line_with_tax_values.append((base_line, tax_values_list))
                continue

            # Split the amounts to distinguish what is from the clean base_line and what has to be allocated to each discount_base_line.
            # We can't use original_base_line as this might have the info of a previous calculation.
            target_factors_discount_base_lines = [
                {
                    'factor': discount_base_line['tax_details']['raw_total_excluded_currency'],
                    'base_line_index': discount_base_line['_index'],
                    'discount_base_line': discount_base_line,
                    'tax_values_list': [
                        (
                            tax_group_values,
                            tax_values,
                            {key: 0.0 for key, _amount in amount_values.items()},
                        )
                        for tax_group_values, tax_values, amount_values in tax_values_list
                    ],
                }
                for discount_base_line in discount_base_lines
            ]
            target_factor_base_line = {
                'factor': base_line['tax_details']['raw_total_excluded_currency'],
                'base_line_index': base_line['_index'],
                'tax_values_list': [
                    (
                        tax_group_values,
                        tax_values,
                        {key: 0.0 for key, _amount in amount_values.items()},
                    )
                    for tax_group_values, tax_values, amount_values in tax_values_list
                ],
            }
            target_factors = [target_factor_base_line] + target_factors_discount_base_lines
            for tax_values_index, (_tax_group_values, _tax_values, amount_values) in enumerate(tax_values_list):
                for key, amount in amount_values.items():
                    # First we get the amounts to distribute for the positive part and the total negative
                    amounts_to_distribute = AccountTax._distribute_delta_amount_smoothly(
                        precision_digits=AVATAX_PRECISION_DIGITS,
                        delta_amount=amount,
                        target_factors=target_factors,
                        allow_negative_factors=True,
                    )

                    for _line_index, (target_factor, amount_to_distribute) in enumerate(zip(target_factors, amounts_to_distribute)):
                        target_factor['tax_values_list'][tax_values_index][2][key] += amount_to_distribute

            # Add the fully recovered original_base_line.
            new_base_line_with_tax_values.append((base_line, target_factor_base_line['tax_values_list']))
            for target_factor in target_factors_discount_base_lines:
                to_group_together[target_factor['base_line_index']]['base_line'] = target_factor['discount_base_line']['record']
                to_group_together[target_factor['base_line_index']]['to_aggregate'].append(target_factor['tax_values_list'])

        # Recover the original discount lines.
        for data in to_group_together.values():
            # Each line can have different taxes, meaning each discount can have amounts from an specific tax in some lines
            # but not in others.
            tax_values_amount_map = defaultdict(lambda: {'base_amount_currency': 0.0, 'tax_amount_currency': 0.0})
            original_base_line = data['base_line']
            to_aggregate_tax_values_list = data['to_aggregate']

            # Aggregate amounts for each tax combination
            for to_aggregate_tax_values in to_aggregate_tax_values_list:
                for tax_group_values, tax_values, amount_vals in to_aggregate_tax_values:
                    tax_group_key, tax_values_key = frozendict(tax_group_values), frozendict(tax_values)
                    tax_amounts = tax_values_amount_map[tax_group_key, tax_values_key]
                    tax_amounts['tax_amount_currency'] += amount_vals['tax_amount_currency']
                    tax_amounts['base_amount_currency'] += amount_vals['base_amount_currency']

            # Build tax values
            new_tax_values_list = [
                (dict(tax_key[0]), dict(tax_key[1]), aggregated_amounts)
                for tax_key, aggregated_amounts in tax_values_amount_map.items()
            ]

            new_base_line_with_tax_values.append((original_base_line, new_tax_values_list))

        # Sort
        base_line_with_tax_values = sorted(new_base_line_with_tax_values, key=lambda x: x[0]['_index'])

        return super()._process_external_taxes(company, base_line_with_tax_values, tax_key_field, search_archived_taxes)

    @api.model
    def _l10n_br_get_line_tax_details_str(self, groupby_dict):
        """ Returns a dict of formatted string of tax details of all taxes per line
            :param groupby_dict:    a dict that has a record as the key and lines as the value
                                    (ex. {account.move: account.move.line} or {sale.order: sale.order.line})
        """

        line_tax_details_str_dict = {}

        for record, lines in groupby_dict.items():
            tax_calculation_response = record.l10n_br_edi_avatax_data or {}
            if not tax_calculation_response:
                continue
            line_id_to_line_data = {line["lineCode"]: line for line in tax_calculation_response.get("lines", [])}
            service_param = record._get_l10n_br_avatax_service_params()

            for line in lines:
                avalara_line = line_id_to_line_data.get(line.id, {})
                tax_detail_to_str = ''
                # Build the formatted string since each line can have multiple taxes
                for detail in avalara_line.get('taxDetails', {}):
                    if avatax_detail := record._extract_tax_values_from_l10n_br_avatax_detail(service_param, avalara_line, detail):
                        # Find the specific tax referenced in the taxDetail to access its name
                        extracted_tax_info = avatax_detail[1]
                        existing_tax = record._search_existing_external_tax(
                            record.company_id,
                            'l10n_br_avatax_code',
                            extracted_tax_info["l10n_br_avatax_code"],
                            extracted_tax_info["price_include_override"]
                        )
                        cst_str = ""
                        if cst := detail.get("cst"):
                            cst_str = f"CST {cst} - "

                        # Tax detail format: '<tax name> - <tax percentage>% - R$ <tax amount> - CST <code> - BC R$ <base amount>'
                        tax_detail_to_str += f"{existing_tax.display_name} - {detail["rate"]}% - R$ {detail["tax"]} - {cst_str}BC R$ {detail["subtotalTaxable"]} \n"
                line_tax_details_str_dict[line.id] = tax_detail_to_str

        return line_tax_details_str_dict

    # IAP related methods
    def _l10n_br_iap_request(self, route, company, json=None):
        avatax_api_id, avatax_api_key = company.sudo().l10n_br_avatax_api_identifier, company.sudo().l10n_br_avatax_api_key

        default_endpoint = DEFAULT_IAP_ENDPOINT if company.l10n_br_avalara_environment == 'production' else DEFAULT_IAP_TEST_ENDPOINT
        iap_endpoint = self.env['ir.config_parameter'].sudo().get_str('l10n_br_avatax_iap.endpoint') or default_endpoint
        environment = company.l10n_br_avalara_environment
        url = f'{iap_endpoint}/api/l10n_br_avatax/1/{route}'

        params = {
            'db_uuid': self.env['ir.config_parameter'].sudo().get_str('database.uuid'),
            'account_token': self.env['iap.account'].get(IAP_SERVICE_NAME).sudo().account_token,
            'avatax': {
                'is_production': environment and environment == 'production',
                'json': json or {},
            }
        }

        if avatax_api_id:
            params['api_id'] = avatax_api_id
            params['api_secret'] = avatax_api_key

        start = str(datetime.utcnow())
        response = iap_jsonrpc(url, params=params, timeout=60, raise_user_error=True)  # longer timeout because create_account can take some time
        end = str(datetime.utcnow())

        # Avatax support requested that requests and responses be provided in JSON, so they can easily load them in their
        # internal tools for troubleshooting.
        self._log_external_tax_request(
            'Avatax Brazil',
            ICP_LOG_NAME,
            f"start={start}\n"
            f"end={end}\n"
            f"args={pformat(url)}\n"
            f"request={dumps(json, indent=2)}\n"
            f"response={dumps(response, indent=2)}"
        )

        return response

    def _l10n_br_iap_ping(self, company):
        # This takes company because this function is called directly from res.config.settings instead of a sale.order or account.move
        return self._l10n_br_iap_request('ping', company)

    def _l10n_br_iap_create_account(self, account_data, company):
        # This takes company because this function is called directly from res.config.settings instead of a sale.order or account.move
        return self._l10n_br_iap_request('create_account', company, account_data)

    @api.model
    def _l10n_br_iap_calculate_tax(self, transaction, company):
        return self._l10n_br_iap_request('calculate_tax', company, transaction)
