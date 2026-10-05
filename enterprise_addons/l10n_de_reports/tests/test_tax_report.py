import base64

from unittest.mock import patch, Mock
from freezegun import freeze_time

from odoo import Command
from odoo.tests import tagged
from odoo.addons.account_reports.tests.account_sales_report_common import AccountSalesReportCommon


REQUESTS_POST = 'odoo.addons.l10n_de_reports.models.account_return.requests.post'


def _mock_post_success(*args, **kwargs):
    resp = Mock()
    resp.status_code = 200
    resp.json.return_value = {
        'transfer_ticket': 'ET-2019-11-00001234',
        'hints': [{'field': 'Kz81', 'message': 'Value accepted'}],
        'pdf_confirmation': base64.b64encode(b'%PDF-1.4 fake pdf content').decode(),
    }
    return resp


@tagged('post_install_l10n', 'post_install', '-at_install')
class GermanTaxReportTest(AccountSalesReportCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountSalesReportCommon.setup_chart_template('de_skr04')
    def setUpClass(cls):
        super().setUpClass()
        cls.company.write({
            'country_id': cls.env.ref('base.de').id,
            'vat': 'DE123456788',
            'state_id': cls.env.ref('base.state_de_th').id,
            'l10n_de_stnr': '151/815/08156',
            'street': 'Musterstraße 1',
            'zip': '99099',
            'city': 'Erfurt',
            'phone': '+49 361 1234567',
            'email': 'buchhaltung@test.de',
        })

        tax_19_sale = cls.env['account.chart.template'].ref('tax_ust_19_skr04')
        tax_7_sale = cls.env['account.chart.template'].ref('tax_ust_7_skr04')
        tax_eu_sale = cls.env['account.chart.template'].ref('tax_free_skr04_mit_vst')
        tax_export = cls.env['account.chart.template'].ref('tax_export_skr04')
        tax_19_eu_purchase = cls.env['account.chart.template'].ref('tax_eu_19_purchase_skr04')
        tax_7_eu_purchase = cls.env['account.chart.template'].ref('tax_eu_7_purchase_skr04')
        tax_19_purchase = cls.env['account.chart.template'].ref('tax_vst_19_skr04')
        tax_7_purchase = cls.env['account.chart.template'].ref('tax_vst_7_skr04')
        foreign_goods = cls.env['account.chart.template'].ref('tax_ust_19_13b_ausland_ohne_vst_skr04')

        moves = cls.env['account.move'].create(
            [
                {
                    'move_type': 'out_invoice',
                    'partner_id': cls.partner_a.id,
                    'invoice_date': '2019-11-01',
                    'invoice_line_ids': [
                        Command.create({
                            'price_unit': 150,
                            'tax_ids': tax_19_sale.ids,
                        })
                    ],
                },
                {
                    'move_type': 'out_invoice',
                    'partner_id': cls.partner_a.id,
                    'invoice_date': '2019-11-01',
                    'invoice_line_ids': [
                        Command.create({
                            'price_unit': 200,
                            'tax_ids': tax_7_sale.ids,
                        })
                    ],
                },
                {
                    'move_type': 'out_invoice',
                    'partner_id': cls.partner_a.id,
                    'invoice_date': '2019-11-01',
                    'invoice_line_ids': [
                        Command.create({
                            'price_unit': 500,
                            'tax_ids': tax_eu_sale.ids,
                        })
                    ],
                },
                {
                    'move_type': 'out_invoice',
                    'partner_id': cls.partner_a.id,
                    'invoice_date': '2019-11-01',
                    'invoice_line_ids': [
                        Command.create({
                            'price_unit': 300,
                            'tax_ids': tax_export.ids,
                        })
                    ],
                },
                {
                    'move_type': 'in_invoice',
                    'partner_id': cls.partner_a.id,
                    'invoice_date': '2019-11-01',
                    'invoice_line_ids': [
                        Command.create({
                            'price_unit': 75,
                            'tax_ids': tax_19_eu_purchase.ids,
                        })
                    ],
                },
                {
                    'move_type': 'in_invoice',
                    'partner_id': cls.partner_a.id,
                    'invoice_date': '2019-11-01',
                    'invoice_line_ids': [
                        Command.create({
                            'price_unit': 120,
                            'tax_ids': tax_7_eu_purchase.ids,
                        })
                    ],
                },
                {
                    'move_type': 'in_invoice',
                    'partner_id': cls.partner_a.id,
                    'invoice_date': '2019-11-01',
                    'invoice_line_ids': [
                        Command.create({
                            'price_unit': 400,
                            'tax_ids': tax_19_purchase.ids,
                        })
                    ],
                },
                {
                    'move_type': 'in_invoice',
                    'partner_id': cls.partner_a.id,
                    'invoice_date': '2019-11-01',
                    'invoice_line_ids': [
                        Command.create({
                            'price_unit': 100,
                            'tax_ids': tax_7_purchase.ids,
                        })
                    ],
                },
                {
                    'move_type': 'in_invoice',
                    'partner_id': cls.partner_a.id,
                    'invoice_date': '2019-11-01',
                    'invoice_line_ids': [
                        Command.create(
                            {
                                'price_unit': 50,
                                'tax_ids': foreign_goods.ids,
                            }
                        )
                    ],
                },
            ]
        )
        moves.action_post()

        cls.de_return_type = cls.env.ref('l10n_de_reports.de_tax_return_type')
        cls.tax_return = cls.env['account.return'].create({
            'name': 'UStVA November 2019',
            'date_from': '2019-11-01',
            'date_to': '2019-11-30',
            'type_id': cls.de_return_type.id,
            'company_id': cls.company.id,
        })

    @freeze_time('2019-12-31')
    def test_generate_xml(self):
        report = self.env.ref('l10n_de.tax_report')
        options = report.get_options({})

        vat_return_element = f"""
        <Umsatzsteuervoranmeldung>
            <Jahr>2019</Jahr>
            <Zeitraum>11</Zeitraum>
            <Steuernummer>{self.company.get_l10n_de_stnr_national()}</Steuernummer>
            <Kz43>800</Kz43>
            <Kz61>22.65</Kz61>
            <Kz66>83.00</Kz66>
            <Kz67>9.50</Kz67>
            <Kz81>150</Kz81>
            <Kz83>-40.50</Kz83>
            <Kz84>50</Kz84>
            <Kz85>9.50</Kz85>
            <Kz86>200</Kz86>
            <Kz89>75</Kz89>
            <Kz93>120</Kz93>
        </Umsatzsteuervoranmeldung>
        """

        data_provider_element = f"""
        <DatenLieferant>
            <Name>{self.company.name}</Name>
            <Strasse>{self.company.street or ''}</Strasse>
            <PLZ>{self.company.zip or ''}</PLZ>
            <Ort>{self.company.city or ''}</Ort>
            <Telefon>{self.company.phone or ''}</Telefon>
            <Email>{self.company.email or ''}</Email>
        </DatenLieferant>
        """

        submitter_data_element = f"""
        <Unternehmer>
            <Bezeichnung>{self.company.name}</Bezeichnung>
            <Str>{self.company.street or ''}</Str>
            <Ort>{self.company.city or ''}</Ort>
            <PLZ>{self.company.zip or ''}</PLZ>
            <Telefon>{self.company.phone or ''}</Telefon>
            <Email>{self.company.email or ''}</Email>
        </Unternehmer>
        """

        expected_xml = f"""
        <Anmeldungssteuern xmlns="http://finkonsens.de/elster/elsteranmeldung/ustva/v2019" version="2019">
            <Erstellungsdatum>20191231</Erstellungsdatum>
            {data_provider_element}
            <Steuerfall>
                {submitter_data_element}
                {vat_return_element}
            </Steuerfall>
        </Anmeldungssteuern>
        """
        self.assertXmlTreeEqual(
            self.get_xml_tree_from_string(self.env[report.custom_handler_model_name].export_tax_report_to_xml(options)['file_content']),
            self.get_xml_tree_from_string(expected_xml),
        )

    @freeze_time('2026-10-01')
    def test_zeitraum_is_set_for_quarterly_tax_report(self):
        self.env.ref('l10n_de_reports.de_tax_return_type').deadline_periodicity = 'trimester'

        report = self.env.ref('l10n_de.tax_report')
        options = report.get_options({})

        xml_export = self.env[report.custom_handler_model_name].export_tax_report_to_xml(options)
        tree = self.get_xml_tree_from_string(xml_export['file_content'])
        zeitraum = tree.xpath('//*[local-name()="Zeitraum"]')[0].text
        self.assertEqual(zeitraum, '43')

    @freeze_time('2019-12-15')
    def test_successful_submission(self):
        with self.allow_pdf_render(), patch(REQUESTS_POST, side_effect=_mock_post_success):
            self.tax_return.action_submit()

        attachment_names = self.tax_return.attachment_ids.mapped('name')
        self.assertTrue(any('Uebertragungsprotokoll' in n for n in attachment_names))
        msg = self.tax_return.message_ids.filtered(lambda m: 'Successfully submitted' in m.body)[0]
        hints = self.tax_return.message_ids.filtered(lambda m: 'Hints' in m.body)[0]
        self.assertIn('ET-2019-11-00001234', msg.body)
        self.assertTrue('Kz81' in hints.body)
