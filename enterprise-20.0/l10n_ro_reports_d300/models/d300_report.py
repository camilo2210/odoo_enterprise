import re

from lxml import etree
from stdnum.ro.cui import compact

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools import file_open


RETURN_PERIOD_PAYMENT_PREFIX = {"L": "301", "T": "302", "S": "303", "A": "304"}

RON_LIMIT = 5000

R_FIELD_RE = re.compile(r"^R\d")

# Mapping from l10n_ro tax_report line.code to D300 v12 XSD attribute.
# Lines NOT mapped here are computed by _compute_d300_settlement (R33_2, R34_2,
# R37_2, R40_2, R41_2, R42_2).
LINE_CODE_TO_ANAF = {
    "tax_ro_baza_rd1": "R1_1",
    "tax_ro_baza_rd2": "R2_1",
    "tax_ro_baza_rd3": "R3_1",
    "tax_ro_baza_rd31": "R3_1_1",
    "tax_ro_baza_rd4": "R4_1",
    "tax_ro_baza_rd5": "R5_1",
    "tax_ro_baza_rd51": "R5_1_1",
    "tax_ro_baza_rd6": "R6_1",
    "tax_ro_baza_rd7": "R7_1",
    "tax_ro_baza_rd71": "R7_1_1",
    "tax_ro_baza_rd8": "R8_1",
    "tax_ro_baza_rd9": "R9_1",
    "tax_ro_baza_rd10": "R10_1",
    "tax_ro_baza_rd11": "R11_1",
    "tax_ro_baza_rd12": "R12_1",
    "tax_ro_baza_rd121": "R12_1_1",
    "tax_ro_baza_rd122": "R12_2_1",
    "tax_ro_baza_rd13": "R13_1",
    "tax_ro_baza_rd14": "R14_1",
    "tax_ro_baza_rd15": "R15_1",
    "tax_ro_baza_rd16": "R16_1",
    "tax_ro_baza_rd17": "R64_1",
    "tax_ro_baza_rd18": "R65_1",
    "tax_ro_tva_rd5": "R5_2",
    "tax_ro_tva_rd51": "R5_1_2",
    "tax_ro_tva_rd6": "R6_2",
    "tax_ro_tva_rd7": "R7_2",
    "tax_ro_tva_rd71": "R7_1_2",
    "tax_ro_tva_rd8": "R8_2",
    "tax_ro_tva_rd9": "R9_2",
    "tax_ro_tva_rd10": "R10_2",
    "tax_ro_tva_rd11": "R11_2",
    "tax_ro_tva_rd12": "R12_2",
    "tax_ro_tva_rd121": "R12_1_2",
    "tax_ro_tva_rd122": "R12_2_2",
    "tax_ro_tva_rd16": "R16_2",
    "tax_ro_tva_rd17": "R64_2",
    "tax_ro_tva_rd18": "R65_2",
    "total_tax_ro_baza_col": "R17_1",
    "total_tax_ro_tva_col": "R17_2",
    "tax_ro_baza_rd20": "R18_1",
    "tax_ro_baza_rd201": "R18_1_1",
    "tax_ro_baza_rd21": "R19_1",
    "tax_ro_baza_rd22": "R20_1",
    "tax_ro_baza_rd221": "R20_1_1",
    "tax_ro_baza_rd23": "R21_1",
    "tax_ro_tva_rd20": "R18_2",
    "tax_ro_tva_rd201": "R18_1_2",
    "tax_ro_tva_rd21": "R19_2",
    "tax_ro_tva_rd22": "R20_2",
    "tax_ro_tva_rd221": "R20_1_2",
    "tax_ro_tva_rd23": "R21_2",
    "tax_ro_baza_rd24": "R22_1",
    "tax_ro_baza_rd25": "R23_1",
    "tax_ro_baza_rd27": "R25_1",
    "tax_ro_baza_rd271": "R25_1_1",
    "tax_ro_baza_rd272": "R25_2_1",
    "tax_ro_baza_rd30": "R26_1",
    "tax_ro_baza_rd301": "R26_1_1",
    "tax_ro_tva_rd24": "R22_2",
    "tax_ro_tva_rd25": "R23_2",
    "tax_ro_tva_rd27": "R25_2",
    "tax_ro_tva_rd271": "R25_1_2",
    "tax_ro_tva_rd272": "R25_2_2",
    "tax_ro_tva_rd28": "R43_2",
    "tax_ro_tva_rd29": "R44_2",
    "tax_ro_baza_total_rd31": "R27_1",
    "tax_ro_tva_total_rd31": "R27_2",
    "tax_ro_tva_rd32": "R28_2",
    "tax_ro_tva_rd33": "R29_2",
    "tax_ro_baza_rd34": "R30_1",
    "tax_ro_tva_rd34": "R30_2",
    "tax_ro_tva_rd35": "R31_2",
    "tax_ro_tva_rd36": "R32_2",
    "tax_ro_tva_rd40": "R36_2",
    "tax_ro_tva_rd43": "R39_2",
}


class L10nRoD300ReportHandler(models.AbstractModel):
    _name = "l10n_ro.d300.report.handler"
    _inherit = "account.tax.report.handler"
    _description = "Romanian D300 Report Custom Handler"

    def export_tax_report_to_xml(self, options):
        report = self.env["account.report"].browse(options["report_id"])
        sender_company = report._get_sender_company_for_export(options)
        if not sender_company.email:
            raise UserError(_("No email address associated with company %s.", sender_company.name))
        tax_return = options["return_id"]

        date_from = options["date"].get("date_from")
        date_to = options["date"].get("date_to")
        dt_to = fields.Date.from_string(date_to)

        options_for_export = report.get_options(
            {
                "no_format": True,
                "date": {"date_from": date_from, "date_to": date_to},
                "filter_unfold_all": True,
                "export_mode": "file",
            }
        )
        lines = report._get_lines(options_for_export)

        colname_to_idx = {col["expression_label"]: idx for idx, col in enumerate(options_for_export.get("columns", []))}
        balance_idx = colname_to_idx["balance"]

        d300_values = {}
        currency = sender_company.currency_id

        for line in lines:
            code = line.code or ""
            amount = line.columns[balance_idx].no_format or 0.0
            if code in LINE_CODE_TO_ANAF and not currency.is_zero(amount):
                d300_values[LINE_CODE_TO_ANAF[code]] = round(amount)

        self._compute_d300_settlement(d300_values)

        if d300_values.get("R35_2", 0) != 0 and d300_values.get("R38_2", 0) != 0:
            raise UserError(_("D300: R35_2 and R38_2 cannot both be non-zero."))

        if tax_return.l10n_ro_request_refund and d300_values.get("R42_2", 0) < RON_LIMIT:
            raise UserError(_("D300: Cannot request reimbursement if the balance is < 5000."))

        return_period = tax_return.l10n_ro_return_period or "L"
        vat = report.get_vat_for_export(options)

        address_str = tax_return.l10n_ro_fiscal_address or sender_company.partner_id.contact_address_inline

        total = sum(v for k, v in d300_values.items() if R_FIELD_RE.match(k))

        header = {
            "luna": str(dt_to.month),
            "an": str(dt_to.year),
            "cui": compact(vat),
            "den": (sender_company.name or ""),
            "adresa": address_str,
            "mail": sender_company.email,
            "banca": tax_return.l10n_ro_bank_name,
            "cont": tax_return.l10n_ro_bank_account,
            "temei": "2" if tax_return.l10n_ro_post_audit_filing else "0",
            "totalPlata_A": str(total),
            "nume_declar": tax_return.l10n_ro_declarant_name,
            "prenume_declar": tax_return.l10n_ro_declarant_surname,
            "functie_declar": tax_return.l10n_ro_declarant_role,
            "caen": tax_return.l10n_ro_caen_code,
            "tip_decont": return_period,
            "pro_rata": f"{tax_return.l10n_ro_pro_rata:.2f}",
            "depusReprezentant": "1" if tax_return.l10n_ro_filed_by_representative else "0",
            "bifa_interne": "1" if tax_return.l10n_ro_simplified_internal else "0",
            "bifa_cereale": "D" if tax_return.l10n_ro_sale_cereals else "N",
            "bifa_mob": "D" if tax_return.l10n_ro_sale_mobile_phones else "N",
            "bifa_disp": "D" if tax_return.l10n_ro_sale_integrated_circuits else "N",
            "bifa_cons": "D" if tax_return.l10n_ro_sale_consoles_tablets_laptops else "N",
            "solicit_ramb": "D" if tax_return.l10n_ro_request_refund else "N",
            "nr_evid": self._compute_payment_record_number(dt_to, return_period),
        }

        xml_bytes = self._build_d300_xml({**header, **{k: str(v) for k, v in d300_values.items()}})

        vat_label = (vat or sender_company.name).replace(" ", "_")
        return {
            "file_name": f"D300_{vat_label}_{dt_to.year}_{dt_to.month:02d}.xml",
            "file_content": xml_bytes,
            "file_type": "xml",
        }

    def _build_d300_xml(self, xml_attrs):
        with file_open("l10n_ro_reports_d300/data/validation/d300_v12.xsd", "rb") as f:
            schema = etree.XMLSchema(etree.parse(f))

        ns = "mfp:anaf:dgti:d300:declaratie:v12"
        xsi = "http://www.w3.org/2001/XMLSchema-instance"
        root = etree.Element(
            f"{{{ns}}}declaratie300",
            nsmap={None: ns, "xsi": xsi},
            attrib={f"{{{xsi}}}schemaLocation": f"{ns} D300.xsd", **xml_attrs},
        )

        try:
            schema.assertValid(root)
        except etree.DocumentInvalid as xml_errors:
            self.env["bus.bus"]._sendone(
                self.env.user.partner_id,
                "simple_notification",
                {
                    "type": "warning",
                    "title": _("XML Validation Error"),
                    "message": _(
                        "Some values will not pass the authority's validation, please check them before submitting your file: %s",
                        [error.message.split(" {'")[0] for error in xml_errors.error_log],
                    ),
                    "sticky": True,
                },
            )

        return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="utf-8")

    def _compute_d300_settlement(self, d300):
        collected = d300.get("R17_2", 0)
        deducted = d300.get("R32_2", 0)

        d300["R33_2"] = max(deducted - collected, 0)
        d300["R34_2"] = max(collected - deducted, 0)

        d300.setdefault("R35_2", 0)
        d300["R37_2"] = d300["R34_2"] + d300["R35_2"] + d300.get("R36_2", 0)

        d300.setdefault("R38_2", 0)
        d300["R40_2"] = d300["R33_2"] + d300["R38_2"] + d300.get("R39_2", 0)

        d300["R41_2"] = max(d300["R37_2"] - d300["R40_2"], 0)
        d300["R42_2"] = max(d300["R40_2"] - d300["R37_2"], 0)

    def _compute_payment_record_number(self, dt_to, return_period="L"):
        period_prefix = RETURN_PERIOD_PAYMENT_PREFIX.get(return_period, "301")
        base = (
            f"10{period_prefix}01{str(dt_to.month).zfill(2)}{str(dt_to.year)[-2:]}"
            f"25{str(dt_to.month % 12 + 1).zfill(2)}"
            f"{str(dt_to.year + (1 if dt_to.month == 12 else 0))[-2:]}0000"
        )
        padded = base[:21].ljust(21, "0")
        checksum = str(sum(int(c) for c in padded) % 100).zfill(2)
        return padded + checksum
