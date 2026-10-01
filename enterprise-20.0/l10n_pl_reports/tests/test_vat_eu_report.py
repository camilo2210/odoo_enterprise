from lxml import etree

from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nPlVatEuReport(TestAccountReportsCommon):
    namespace = {'vateu': 'http://crd.gov.pl/wzor/2021/01/12/10293/'}

    @classmethod
    @TestAccountReportsCommon.setup_country('pl')
    def setUpClass(cls):
        super().setUpClass()
        cls.company.write({
            'name': 'Polish Company',
            'vat': 'PL1234567883',
            'l10n_pl_reports_tax_office_id': cls.env.ref('l10n_pl.pl_tax_office_0206'),
        })
        cls.partner_a.write({
            'name': 'Belgian Partner',
            'country_id': cls.env.ref('base.be').id,
            'vat': 'BE0477472701',
        })
        cls.report = cls.env.ref('l10n_pl_reports.vat_eu_report')
        cls.previous_options = {
            'selected_variant_id': cls.report.id,
            'date': {
                'date_from': '2026-01-01',
                'date_to': '2026-01-31',
                'mode': 'range',
                'filter': 'custom',
            },
        }

    def _create_vat_eu_invoice(self, move_type, tax_xmlid, amount, *, partner=None, currency=None):
        return self._create_invoice_one_line(
            move_type=move_type,
            partner_id=partner or self.partner_a,
            invoice_date='2026-01-15',
            name=tax_xmlid,
            price_unit=amount,
            account_id=(
                self.company_data['default_account_revenue']
                if move_type in ('out_invoice', 'out_refund')
                else self.company_data['default_account_expense']
            ),
            tax_ids=self.env.ref(f'account.{self.company.id}_{tax_xmlid}'),
            currency_id=currency,
            post=True,
        )

    def _export(self, options):
        self.env.flush_all()
        report = self.env['account.report'].browse(options['report_id'])
        return self.env[report.custom_handler_model_name].l10n_pl_export_vat_eu_to_xml(options)

    def test_report_and_xml_export(self):
        self._create_vat_eu_invoice('out_invoice', 'vs_unia', 1000)
        self._create_vat_eu_invoice('out_invoice', 'vs_unia_triangular', 2000)
        self._create_vat_eu_invoice('out_invoice', 'vs_dostu', 3000)
        self._create_vat_eu_invoice('in_invoice', 'vz_unia', 4000)
        self._create_vat_eu_invoice('in_invoice', 'vz_unia_triangular', 5000)

        options = self.report.get_options(self.previous_options)
        lines = self.report._get_lines(options)
        self.assertLinesValues(
            lines,
            [0, 1, 2, 3, 4, 5, 6, 7],
            [
                ['EC Sales and Purchase List',   '',             '', 1000.0, 2000.0, 3000.0, 4000.0, 5000.0],
                ['Belgian Partner',            'BE',   '0477472701', 1000.0, 2000.0, 3000.0, 4000.0, 5000.0],
            ],
            options,
        )

        result = self._export(options)
        self.assertTrue(result['file_name'].endswith('_2026_01.xml'))
        self.assertXmlTreeEqual(
            self.get_xml_tree_from_string(result['file_content']),
            self.get_xml_tree_from_string('''
                <Deklaracja xmlns="http://crd.gov.pl/wzor/2021/01/12/10293/"
                            xmlns:etd="http://crd.gov.pl/xml/schematy/dziedzinowe/mf/2020/03/11/eD/DefinicjeTypy/">
                    <Naglowek>
                        <KodFormularza kodSystemowy="VAT-UE (5)" wersjaSchemy="2-0E">VAT-UE</KodFormularza>
                        <WariantFormularza>5</WariantFormularza>
                        <Rok>2026</Rok>
                        <Miesiac>1</Miesiac>
                        <CelZlozenia>1</CelZlozenia>
                        <KodUrzedu>0206</KodUrzedu>
                    </Naglowek>
                    <Podmiot1 rola="Podatnik">
                        <etd:OsobaNiefizyczna>
                            <etd:NIP>1234567883</etd:NIP>
                            <etd:PelnaNazwa>Polish Company</etd:PelnaNazwa>
                        </etd:OsobaNiefizyczna>
                    </Podmiot1>
                    <PozycjeSzczegolowe>
                        <Grupa1><P_Da>BE</P_Da><P_Db>0477472701</P_Db><P_Dc>1000</P_Dc><P_Dd>1</P_Dd></Grupa1>
                        <Grupa1><P_Da>BE</P_Da><P_Db>0477472701</P_Db><P_Dc>2000</P_Dc><P_Dd>2</P_Dd></Grupa1>
                        <Grupa2><P_Na>BE</P_Na><P_Nb>0477472701</P_Nb><P_Nc>4000</P_Nc><P_Nd>1</P_Nd></Grupa2>
                        <Grupa2><P_Na>BE</P_Na><P_Nb>0477472701</P_Nb><P_Nc>5000</P_Nc><P_Nd>2</P_Nd></Grupa2>
                        <Grupa3><P_Ua>BE</P_Ua><P_Ub>0477472701</P_Ub><P_Uc>3000</P_Uc></Grupa3>
                    </PozycjeSzczegolowe>
                    <Pouczenie>1</Pouczenie>
                </Deklaracja>
            '''),
        )

    def test_export_requires_full_month(self):
        partial_options = self.report.get_options({
            **self.previous_options,
            'date': {
                **self.previous_options['date'],
                'date_from': '2026-01-02',
            },
        })
        with self.assertRaisesRegex(UserError, 'single calendar month'):
            self._export(partial_options)

        spanning_options = self.report.get_options({
            **self.previous_options,
            'date': {
                **self.previous_options['date'],
                'date_to': '2026-02-01',
            },
        })
        with self.assertRaisesRegex(UserError, 'single calendar month'):
            self._export(spanning_options)

    def test_export_aggregates_duplicate_partner_vat(self):
        duplicate_partner = self.env['res.partner'].create({
            'name': 'Other Belgian Partner Record',
            'country_id': self.env.ref('base.be').id,
            'vat': self.partner_a.vat,
        })
        self._create_vat_eu_invoice('out_invoice', 'vs_unia', 1000)
        self._create_vat_eu_invoice('out_invoice', 'vs_unia', 500, partner=duplicate_partner)

        root = etree.fromstring(self._export(self.report.get_options(self.previous_options))['file_content'])
        groups = root.xpath('vateu:PozycjeSzczegolowe/vateu:Grupa1', namespaces=self.namespace)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].xpath('string(vateu:P_Dc)', namespaces=self.namespace), '1500')

    def test_export_refunds_and_foreign_currency(self):
        self._create_vat_eu_invoice('out_invoice', 'vs_unia', 1000)
        self._create_vat_eu_invoice('out_refund', 'vs_unia', 250)

        eur = self.setup_other_currency('EUR', rates=[('2026-01-01', 0.25)])
        self._create_vat_eu_invoice('out_invoice', 'vs_unia', 100, currency=eur)

        root = etree.fromstring(self._export(self.report.get_options(self.previous_options))['file_content'])
        self.assertEqual(
            root.xpath('string(vateu:PozycjeSzczegolowe/vateu:Grupa1/vateu:P_Dc)', namespaces=self.namespace),
            '1150',
        )

    def test_empty_export(self):
        root = etree.fromstring(self._export(self.report.get_options(self.previous_options))['file_content'])
        self.assertTrue(root.xpath('vateu:PozycjeSzczegolowe', namespaces=self.namespace))

    def test_export_rejects_missing_partner_vat(self):
        self.partner_a.vat = False
        self._create_vat_eu_invoice('out_invoice', 'vs_unia', 1000)
        with self.assertRaisesRegex(UserError, 'valid EU VAT number'):
            self._export(self.report.get_options(self.previous_options))
