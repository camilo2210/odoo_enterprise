from freezegun import freeze_time
from lxml import etree

from odoo import Command
from odoo.tests import tagged
from odoo.tools import file_open

from odoo.addons.l10n_ro_reports_d300.tests.test_d300_report import TestL10nRoD300Report


@tagged("post_install_l10n", "post_install", "-at_install")
class TestL10nRoD300XmlExport(TestL10nRoD300Report):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.tax_sale_21 = cls.env.ref(f"account.{cls.company.id}_tvac_21", raise_if_not_found=False)
        cls.tax_purchase_21 = cls.env.ref(f"account.{cls.company.id}_tvad_21", raise_if_not_found=False)
        cls.tax_sale_11 = cls.env.ref(f"account.{cls.company.id}_tvac_11", raise_if_not_found=False)
        cls.tax_purchase_11 = cls.env.ref(f"account.{cls.company.id}_tvad_11", raise_if_not_found=False)

        cls.partner_ro = cls.env["res.partner"].create({
            "name": "Test RO Partner",
            "vat": "8001011234567",
            "country_id": cls.env.ref("base.ro").id,
        })

    def _generate_d300_xml(self, date_from, date_to):
        tax_return = self.env["account.return"].create({
            "name": "Test D300 Return",
            "date_from": date_from,
            "date_to": date_to,
            "type_id": self.env.ref("l10n_ro_reports.ro_tax_return_type").id,
            "company_id": self.company.id,
        })
        with self.allow_pdf_render():
            action = tax_return.action_submit()

        wizard = self.env["l10n_ro.d300.submission.wizard"].browse(action["res_id"])
        wizard.write({
            "l10n_ro_declarant_name": "Popescu",
            "l10n_ro_declarant_surname": "Ion",
            "l10n_ro_declarant_role": "Administrator",
            "l10n_ro_bank_name": "Banca Test",
            "l10n_ro_bank_account": "RO00BANK0000000000000001",
            "l10n_ro_caen_code": "6201",
            "l10n_ro_return_period": "L",
            "l10n_ro_pro_rata": 100.0,
        })
        with self.allow_pdf_render():
            wizard.action_proceed_with_submission()

        return tax_return.attachment_ids.filtered(lambda a: a.mimetype == "application/xml")

    @freeze_time("2025-08-15")
    def test_xml_export_full(self):
        """End-to-end: invoices -> return -> wizard -> XML attachment with expected attributes."""
        self.env["account.move"].create([{
            "move_type": move_type,
            "partner_id": self.partner_ro.id,
            "invoice_date": "2025-08-05",
            "invoice_line_ids": [Command.create({
                "name": "Test Product",
                "price_unit": price_unit,
                "tax_ids": [Command.set(tax.ids)],
            })],
        } for move_type, price_unit, tax in [
            ("out_invoice", 1000.0, self.tax_sale_21),
            ("out_invoice", 2000.0, self.tax_sale_11),
            ("in_invoice", 500.0, self.tax_purchase_21),
            ("in_invoice", 800.0, self.tax_purchase_11),
        ]]).action_post()

        xml = self._generate_d300_xml("2025-08-01", "2025-08-31")
        self.assertTrue(xml, "D300 XML attachment was not generated.")

        attribs = dict(etree.fromstring(xml.raw.content).attrib)
        self.assertEqual(attribs["tip_decont"], "L")
        self.assertEqual(attribs["pro_rata"], "100.00")
        # Per-line attributes:
        # sale 21% x 1000 -> R9_1=1000, R9_2=210
        # sale 11% x 2000 -> R10_1=2000, R10_2=220
        # purchase 21% x 500 -> R22_1=500, R22_2=105
        # purchase 11% x 800 -> R23_1=800, R23_2=88
        self.assertEqual(attribs.get("R9_1", "0"), "1000")
        self.assertEqual(attribs.get("R9_2", "0"), "210")
        self.assertEqual(attribs.get("R10_1", "0"), "2000")
        self.assertEqual(attribs.get("R10_2", "0"), "220")
        self.assertEqual(attribs.get("R22_1", "0"), "500")
        self.assertEqual(attribs.get("R22_2", "0"), "105")
        self.assertEqual(attribs.get("R23_1", "0"), "800")
        self.assertEqual(attribs.get("R23_2", "0"), "88")
        # Aggregations: R17 = sum collected, R27 = sum deductible.
        self.assertEqual(attribs.get("R17_1", "0"), "3000")
        self.assertEqual(attribs.get("R17_2", "0"), "430")
        self.assertEqual(attribs.get("R27_1", "0"), "1300")
        self.assertEqual(attribs.get("R27_2", "0"), "193")
        # Settlement (computed): collected (R17_2)=430, deducted (R32_2)=193 -> 237 to pay.
        self.assertEqual(attribs["R33_2"], "0")
        self.assertEqual(attribs["R34_2"], "237")
        self.assertEqual(attribs["R35_2"], "0")
        self.assertEqual(attribs["R37_2"], "237")
        self.assertEqual(attribs["R38_2"], "0")
        self.assertEqual(attribs["R40_2"], "0")
        self.assertEqual(attribs["R41_2"], "237")
        self.assertEqual(attribs["R42_2"], "0")

    @freeze_time("2025-08-15")
    def test_xml_export_validates_against_xsd(self):
        """Generated XML must validate against d300_v12.xsd."""
        self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner_ro.id,
            "invoice_date": "2025-08-05",
            "invoice_line_ids": [Command.create({
                "name": "Test Product",
                "price_unit": 1000.0,
                "tax_ids": [Command.set(self.tax_sale_21.ids)],
            })],
        }).action_post()

        xml = self._generate_d300_xml("2025-08-01", "2025-08-31")
        self.assertTrue(xml)

        with file_open("l10n_ro_reports_d300/data/validation/d300_v12.xsd", "rb") as f:
            schema = etree.XMLSchema(etree.parse(f))
        schema.assertValid(etree.fromstring(xml.raw.content))
