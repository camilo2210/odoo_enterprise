from odoo.addons.l10n_mx_edi.tests.common import TestMxEdiCommon
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon

from odoo import Command, fields
from odoo.tests.common import test_xsd
from odoo.tests import HttpCase, tagged
from odoo.exceptions import RedirectWarning

from freezegun import freeze_time


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nMXTrialBalanceReportCommon(TestMxEdiCommon, TestAccountReportsCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Enforce old default expence account
        cls.company = cls.company_data['company']
        cls.company_data['default_account_expense'] = cls.env.ref(f'account.{cls.company.id}_cuenta601_84')

        cls.account_tag_debit = cls.env.ref('l10n_mx.tag_debit_balance_account')
        cls.account_tag_credit = cls.env.ref('l10n_mx.tag_credit_balance_account')

        # Entries in 2020 to test initial balance
        cls.move_2020_01 = cls._create_invoice(
            move_type='entry',
            journal_id=cls.company_data['default_journal_misc'],
            date='2020-01-01',
            line_ids=[
                cls._prepare_entry_line(
                    account_id=cls.company_data['default_account_payable'],
                    debit=1000.0,
                    credit=0.0,
                ),
                cls._prepare_entry_line(
                    account_id=cls.company_data['default_account_revenue'],
                    debit=0.0,
                    credit=1000.0,
                ),
            ],
        )

        cls.move_2020_02 = cls._create_invoice(
            move_type='entry',
            journal_id=cls.company_data['default_journal_misc'],
            date='2020-02-01',
            line_ids=[
                cls._prepare_entry_line(
                    account_id=cls.company_data['default_account_expense'],
                    debit=500.0,
                    credit=0.0,
                ),
                cls._prepare_entry_line(
                    account_id=cls.company_data['default_account_revenue'],
                    debit=0.0,
                    credit=500.0,
                ),
            ],
        )
        (cls.move_2020_01 + cls.move_2020_02).action_post()

        # Entries in 2021 to test report for a specific financial year
        cls.move_2021_01 = cls._create_invoice(
            move_type='entry',
            journal_id=cls.company_data['default_journal_misc'],
            date='2021-06-01',
            line_ids=[
                cls._prepare_entry_line(
                    account_id=cls.company_data['default_account_expense'],
                    debit=250.0,
                    credit=0.0,
                ),
                cls._prepare_entry_line(
                    account_id=cls.company_data['default_account_revenue'],
                    debit=0.0,
                    credit=250.0,
                ),
            ],
        )

        cls.move_2021_02 = cls._create_invoice(
            move_type='entry',
            journal_id=cls.company_data['default_journal_misc'],
            date='2021-08-01',
            line_ids=[
                cls._prepare_entry_line(
                    account_id=cls.company_data['default_account_payable'],
                    debit=75.0,
                    credit=0.0,
                ),
                cls._prepare_entry_line(
                    account_id=cls.company_data['default_account_revenue'],
                    debit=0.0,
                    credit=75.0,
                ),
            ],
        )
        (cls.move_2021_01 + cls.move_2021_02).action_post()

        # Special cases: codes with extra levels from the default COA and dotted account names
        cls.extra_deep_code = cls.env["account.account"].create(
            {
                "name": "Extra deep code",
                "account_type": "liability_current",
                "code": "205.06.01.001",
                "parent_id": cls.env["account.chart.template"].ref("account_subgroup_otros_acreedores_diversos_a_corto_plazo").id,
            }
        )

        cls.dotted_name = cls.env["account.account"].create(
            {
                "name": "Dotted name C.V.",
                "account_type": "liability_current",
                "code": "205.06.03",
                "parent_id": cls.env["account.chart.template"].ref("account_subgroup_otros_acreedores_diversos_a_corto_plazo").id,
            }
        )

        cls.extra_deep_code_move = cls.env["account.move"].create(
            {
                "move_type": "entry",
                "date": fields.Date.to_date("2021-06-01"),
                "journal_id": cls.company_data["default_journal_misc"].id,
                "line_ids": [
                    Command.create(
                        {
                            "debit": 400.0,
                            "credit": 0.0,
                            "account_id": cls.dotted_name.id,
                        }
                    ),
                    Command.create(
                        {
                            "debit": 0.0,
                            "credit": 400.0,
                            "account_id": cls.extra_deep_code.id,
                        }
                    ),
                ],
            }
        )

        cls.dotted_name_move = cls.env["account.move"].create(
            {
                "move_type": "entry",
                "date": fields.Date.to_date("2021-06-01"),
                "journal_id": cls.company_data["default_journal_misc"].id,
                "line_ids": [
                    Command.create(
                        {
                            "debit": 50.0,
                            "credit": 0.0,
                            "account_id": cls.extra_deep_code.id,
                        }
                    ),
                    Command.create(
                        {
                            "debit": 0.0,
                            "credit": 50.0,
                            "account_id": cls.dotted_name.id,
                        }
                    ),
                ],
            }
        )
        (cls.extra_deep_code_move + cls.dotted_name_move).action_post()

        cls.report = cls.env.ref('account_reports.trial_balance_report')
        cls.company_data['company'].totals_below_sections = True


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nMXTrialBalanceReport(TestL10nMXTrialBalanceReportCommon):
    _test_user_groups = None  # FIXME list needed groups

    def test_generate_coa_xml(self):
        """ This test will generate a COA report and verify that every
            account with an entry in the selected period has been there.

            CodAgrup corresponds to Account Group code
            NumCta corresponds to Account code
            Desc corresponds to Account Name
            SubCtaDe corresponds to account parent code
            Nivel corresponds to Hierarchy Level
            Natur corresponds to type of account (Debit or Credit)

            Available values for "Natur":
            D = Debit Account
            A = Credit Account

            Unaffected Earnings account is not include in this report because
            it's custom Odoo account.
        """

        expected_coa_xml = b"""<?xml version='1.0' encoding='utf-8'?>
        <catalogocuentas:Catalogo xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:catalogocuentas="http://www.sat.gob.mx/esquemas/ContabilidadE/1_3/CatalogoCuentas" xsi:schemaLocation="http://www.sat.gob.mx/esquemas/ContabilidadE/1_3/CatalogoCuentas http://www.sat.gob.mx/esquemas/ContabilidadE/1_3/CatalogoCuentas/CatalogoCuentas_1_3.xsd" Version="1.3" RFC="EKU9003173C9" Mes="01" Anio="2021" Sello="___ignore___" Certificado="___ignore___" noCertificado="___ignore___">
            <catalogocuentas:Ctas CodAgrup="201" NumCta="201" Desc="Suppliers" Nivel="1" Natur="A"/>
            <catalogocuentas:Ctas CodAgrup="201.01" NumCta="201.01" Desc="National suppliers" SubCtaDe="201" Nivel="2" Natur="A"/>
            <catalogocuentas:Ctas CodAgrup="201.01" NumCta="201.01.01" Desc="National suppliers" SubCtaDe="201.01" Nivel="3" Natur="A"/>
            <catalogocuentas:Ctas CodAgrup="205" NumCta="205" Desc="Short-term sundry creditors" Nivel="1" Natur="A"/>
            <catalogocuentas:Ctas CodAgrup="205.06" NumCta="205.06" Desc="Other short-term sundry creditors" SubCtaDe="205" Nivel="2" Natur="A"/>
            <catalogocuentas:Ctas CodAgrup="205.06" NumCta="205.06.01.001" Desc="Extra deep code" SubCtaDe="205.06" Nivel="3" Natur="A"/>
            <catalogocuentas:Ctas CodAgrup="205.06" NumCta="205.06.03" Desc="Dotted name C.V." SubCtaDe="205.06" Nivel="3" Natur="A"/>
            <catalogocuentas:Ctas CodAgrup="401" NumCta="401" Desc="Income" Nivel="1" Natur="A"/>
            <catalogocuentas:Ctas CodAgrup="401.01" NumCta="401.01" Desc="Sales and/or services taxed at the general rate" SubCtaDe="401" Nivel="2" Natur="A"/>
            <catalogocuentas:Ctas CodAgrup="401.01" NumCta="401.01.01" Desc="Sales and/or services taxed at the general rate" SubCtaDe="401.01" Nivel="3" Natur="A"/>
            <catalogocuentas:Ctas CodAgrup="601" NumCta="601" Desc="Overheads" Nivel="1" Natur="D"/>
            <catalogocuentas:Ctas CodAgrup="601.84" NumCta="601.84" Desc="Other overheads" SubCtaDe="601" Nivel="2" Natur="D"/>
            <catalogocuentas:Ctas CodAgrup="601.84" NumCta="601.84.01" Desc="Other overheads" SubCtaDe="601.84" Nivel="3" Natur="D"/>
        </catalogocuentas:Catalogo>
        """

        options = self._generate_options(self.report, '2021-01-01', '2021-12-31')
        self.assertTrue(any(button.get('action_param') == 'action_l10n_mx_generate_coa_sat_xml' for button in options['buttons']))
        options['l10n_mx_sat_ignore_errors'] = True
        with freeze_time(self.frozen_today):
            coa_report = self.env[self.report.custom_handler_model_name].action_l10n_mx_generate_coa_sat_xml(options)['file_content']
        self.assertXmlTreeEqual(
            self.get_xml_tree_from_string(coa_report),
            self.get_xml_tree_from_string(expected_coa_xml),
        )

    def test_generate_coa_xml_with_prefix_7_accounts_having_debit_and_credit_tags(self):
        """ This test will generate a COA report and verify that every
            account with an entry in the selected period has been there. This process
            should pass when having Debit and Credit tags for accounts as 7MM.NN.OO.
        """
        expected_coa_xml = b"""<?xml version='1.0' encoding='utf-8'?>
        <catalogocuentas:Catalogo xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:catalogocuentas="http://www.sat.gob.mx/esquemas/ContabilidadE/1_3/CatalogoCuentas" xsi:schemaLocation="http://www.sat.gob.mx/esquemas/ContabilidadE/1_3/CatalogoCuentas http://www.sat.gob.mx/esquemas/ContabilidadE/1_3/CatalogoCuentas/CatalogoCuentas_1_3.xsd" Version="1.3" RFC="EKU9003173C9" Mes="01" Anio="2021" Sello="___ignore___" Certificado="___ignore___" noCertificado="___ignore___">
            <catalogocuentas:Ctas CodAgrup="201" NumCta="201" Desc="Suppliers" Nivel="1" Natur="A"/>
            <catalogocuentas:Ctas CodAgrup="201.01" NumCta="201.01" Desc="National suppliers" SubCtaDe="201" Nivel="2" Natur="A"/>
            <catalogocuentas:Ctas CodAgrup="201.01" NumCta="201.01.01" Desc="National suppliers" SubCtaDe="201.01" Nivel="3" Natur="A"/>
            <catalogocuentas:Ctas CodAgrup="205" NumCta="205" Desc="Short-term sundry creditors" Nivel="1" Natur="A"/>
            <catalogocuentas:Ctas CodAgrup="205.06" NumCta="205.06" Desc="Other short-term sundry creditors" SubCtaDe="205" Nivel="2" Natur="A"/>
            <catalogocuentas:Ctas CodAgrup="205.06" NumCta="205.06.01.001" Desc="Extra deep code" SubCtaDe="205.06" Nivel="3" Natur="A"/>
            <catalogocuentas:Ctas CodAgrup="205.06" NumCta="205.06.03" Desc="Dotted name C.V." SubCtaDe="205.06" Nivel="3" Natur="A"/>
            <catalogocuentas:Ctas CodAgrup="401" NumCta="401" Desc="Income" Nivel="1" Natur="A"/>
            <catalogocuentas:Ctas CodAgrup="401.01" NumCta="401.01" Desc="Sales and/or services taxed at the general rate" SubCtaDe="401" Nivel="2" Natur="A"/>
            <catalogocuentas:Ctas CodAgrup="401.01" NumCta="401.01.01" Desc="Sales and/or services taxed at the general rate" SubCtaDe="401.01" Nivel="3" Natur="A"/>
            <catalogocuentas:Ctas CodAgrup="601" NumCta="601" Desc="Overheads" Nivel="1" Natur="D"/>
            <catalogocuentas:Ctas CodAgrup="601.84" NumCta="601.84" Desc="Other overheads" SubCtaDe="601" Nivel="2" Natur="D"/>
            <catalogocuentas:Ctas CodAgrup="601.84" NumCta="601.84.01" Desc="Other overheads" SubCtaDe="601.84" Nivel="3" Natur="D"/>
        </catalogocuentas:Catalogo>
        """

        self.env['account.account'].create({
            'code': '702.02.01',
            'name': 'Otros gastos',
            'account_type': 'income',
            'tag_ids': [Command.set((self.account_tag_debit + self.account_tag_credit).ids)],
        })

        options = self._generate_options(self.report, '2021-01-01', '2021-12-31')
        options['l10n_mx_sat_ignore_errors'] = True
        with freeze_time(self.frozen_today):
            coa_report = self.env[self.report.custom_handler_model_name].with_context(skip_xsd=True).action_l10n_mx_generate_coa_sat_xml(options)['file_content']
        self.assertXmlTreeEqual(
            self.get_xml_tree_from_string(coa_report),
            self.get_xml_tree_from_string(expected_coa_xml),
        )

    def test_generate_sat_xml(self):
        """ This test will generate a SAT report and verify that
        every account present in the trial balance (except unaffected
        earnings account) is present in the xml.

        NumCta corresponds to Account Group code
        SaldoIni corresponds to Initial Balance
        Debe corresponds to Debit in the current period
        Haber corresponds to Credit in the current period
        SaldoFin corresponds to End Balance
        """
        expected_sat_xml = b"""<?xml version='1.0' encoding='utf-8'?>
        <BCE:Balanza xmlns:BCE="http://www.sat.gob.mx/esquemas/ContabilidadE/1_3/BalanzaComprobacion" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.sat.gob.mx/esquemas/ContabilidadE/1_3/BalanzaComprobacion http://www.sat.gob.mx/esquemas/ContabilidadE/1_3/BalanzaComprobacion/BalanzaComprobacion_1_3.xsd" Version="1.3" RFC="EKU9003173C9" Mes="01" Anio="2021" TipoEnvio="N" Sello="___ignore___" Certificado="___ignore___" noCertificado="___ignore___">
            <BCE:Ctas NumCta="201" SaldoIni="-1000.00" Debe="75.00" Haber="0.00" SaldoFin="-1075.00"/>
            <BCE:Ctas NumCta="201.01" SaldoIni="-1000.00" Debe="75.00" Haber="0.00" SaldoFin="-1075.00"/>
            <BCE:Ctas NumCta="201.01.01" SaldoIni="-1000.00" Debe="75.00" Haber="0.00" SaldoFin="-1075.00"/>
            <BCE:Ctas NumCta="205" SaldoIni="0.00" Debe="450.00" Haber="450.00" SaldoFin="0.00"/>
            <BCE:Ctas NumCta="205.06" SaldoIni="0.00" Debe="450.00" Haber="450.00" SaldoFin="0.00"/>
            <BCE:Ctas NumCta="205.06.01.001" SaldoIni="0.00" Debe="50.00" Haber="400.00" SaldoFin="350.00"/>
            <BCE:Ctas NumCta="205.06.03" SaldoIni="0.00" Debe="400.00" Haber="50.00" SaldoFin="-350.00"/>
            <BCE:Ctas NumCta="401" SaldoIni="0.00" Debe="0.00" Haber="325.00" SaldoFin="325.00"/>
            <BCE:Ctas NumCta="401.01" SaldoIni="0.00" Debe="0.00" Haber="325.00" SaldoFin="325.00"/>
            <BCE:Ctas NumCta="401.01.01" SaldoIni="0.00" Debe="0.00" Haber="325.00" SaldoFin="325.00"/>
            <BCE:Ctas NumCta="601" SaldoIni="0.00" Debe="250.00" Haber="0.00" SaldoFin="250.00"/>
            <BCE:Ctas NumCta="601.84" SaldoIni="0.00" Debe="250.00" Haber="0.00" SaldoFin="250.00"/>
            <BCE:Ctas NumCta="601.84.01" SaldoIni="0.00" Debe="250.00" Haber="0.00" SaldoFin="250.00"/>
        </BCE:Balanza>
        """

        options = self._generate_options(self.report, '2021-01-01', '2021-12-31')
        self.assertTrue(any(button.get('action_param') == 'action_l10n_mx_generate_sat_xml' for button in options['buttons']))
        options['l10n_mx_sat_ignore_errors'] = True
        with freeze_time(self.frozen_today):
            sat_report = self.env[self.report.custom_handler_model_name].action_l10n_mx_generate_sat_xml(options)['file_content']
        self.assertXmlTreeEqual(
            self.get_xml_tree_from_string(sat_report),
            self.get_xml_tree_from_string(expected_sat_xml),
        )

    def test_generate_sat_xml_supplementary(self):
        """This test will generate a SAT report with TipoEnvio='C' (Complementary/Supplementary) and verify that:
        - TipoEnvio is 'C'
        - FechaModBal attribute IS present in the XML
        - Filename ends with 'BC'
        """
        move_2021_03 = self.env["account.move"].create({
            "move_type": "entry",
            "date": fields.Date.to_date("2021-12-18"),
            "journal_id": self.company_data["default_journal_misc"].id,
            'line_ids': [
                Command.create(
                    {'debit': 250.0, 'credit': 0.0, 'account_id': self.company_data['default_account_expense'].id}),
                Command.create(
                    {'debit': 0.0, 'credit': 250.0, 'account_id': self.company_data['default_account_revenue'].id}),
            ]
        })
        move_2021_03.action_post()
        fecha_mod_bal = fields.Date.to_date(fields.Date.today())
        expected_sat_xml = (
            """<?xml version='1.0' encoding='utf-8'?>
        <BCE:Balanza xmlns:BCE="http://www.sat.gob.mx/esquemas/ContabilidadE/1_3/BalanzaComprobacion" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.sat.gob.mx/esquemas/ContabilidadE/1_3/BalanzaComprobacion http://www.sat.gob.mx/esquemas/ContabilidadE/1_3/BalanzaComprobacion/BalanzaComprobacion_1_3.xsd" Version="1.3" RFC="EKU9003173C9" Mes="01" Anio="2021" TipoEnvio="C" FechaModBal="%s" Sello="___ignore___" Certificado="___ignore___" noCertificado="___ignore___">
            <BCE:Ctas NumCta="201" SaldoIni="-1000.00" Debe="75.00" Haber="0.00" SaldoFin="-1075.00"/>
            <BCE:Ctas NumCta="201.01" SaldoIni="-1000.00" Debe="75.00" Haber="0.00" SaldoFin="-1075.00"/>
            <BCE:Ctas NumCta="201.01.01" SaldoIni="-1000.00" Debe="75.00" Haber="0.00" SaldoFin="-1075.00"/>
            <BCE:Ctas NumCta="205" SaldoIni="0.00" Debe="450.00" Haber="450.00" SaldoFin="0.00"/>
            <BCE:Ctas NumCta="205.06" SaldoIni="0.00" Debe="450.00" Haber="450.00" SaldoFin="0.00"/>
            <BCE:Ctas NumCta="205.06.01.001" SaldoIni="0.00" Debe="50.00" Haber="400.00" SaldoFin="350.00"/>
            <BCE:Ctas NumCta="205.06.03" SaldoIni="0.00" Debe="400.00" Haber="50.00" SaldoFin="-350.00"/>
            <BCE:Ctas NumCta="401" SaldoIni="0.00" Debe="0.00" Haber="575.00" SaldoFin="575.00"/>
            <BCE:Ctas NumCta="401.01" SaldoIni="0.00" Debe="0.00" Haber="575.00" SaldoFin="575.00"/>
            <BCE:Ctas NumCta="401.01.01" SaldoIni="0.00" Debe="0.00" Haber="575.00" SaldoFin="575.00"/>
            <BCE:Ctas NumCta="601" SaldoIni="0.00" Debe="500.00" Haber="0.00" SaldoFin="500.00"/>
            <BCE:Ctas NumCta="601.84" SaldoIni="0.00" Debe="500.00" Haber="0.00" SaldoFin="500.00"/>
            <BCE:Ctas NumCta="601.84.01" SaldoIni="0.00" Debe="500.00" Haber="0.00" SaldoFin="500.00"/>
        </BCE:Balanza>
        """
            % fecha_mod_bal
        ).encode()

        options = self._generate_options(self.report, "2021-01-01", "2021-12-31")
        options["l10n_mx_sat_ignore_errors"] = True
        options["submit_type"] = "C"

        sat_result = self.env[
            self.report.custom_handler_model_name
        ].action_l10n_mx_generate_sat_xml(options)
        sat_report = sat_result["file_content"]
        file_name = sat_result["file_name"]

        self.assertXmlTreeEqual(
            self.get_xml_tree_from_string(sat_report),
            self.get_xml_tree_from_string(expected_sat_xml),
        )
        self.assertTrue(
            file_name.endswith("BC.xml"),
            f"Expected filename to end with 'BC.xml', got {file_name}",
        )

    def test_generate_coa_xml_without_tag(self):
        """This test verifies that all accounts present in the trial balance have a Debit or a Credit balance account tag"""
        self.company_data['default_account_payable'].tag_ids = [Command.clear()]
        options = self._generate_options(self.report, '2021-01-01', '2021-12-31')
        options['l10n_mx_sat_ignore_errors'] = True
        with self.assertRaises(RedirectWarning):
            self.env[self.report.custom_handler_model_name].action_l10n_mx_generate_coa_sat_xml(options)

    def test_mx_trial_balance(self):
        """ This test will test the Mexican Trial Balance (with and without the hierarchy) """
        # Testing the report without hierarchy
        options = self._generate_options(self.report, '2021-01-01', '2021-12-31', {'hierarchy': False, 'unfold_all': True})
        options['l10n_mx_sat_ignore_errors'] = True
        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                                 Initial Balance     Debit    Credit     End Balance
            [0,                                                                  1,         2,        3,         4],
            [
                ('201.01.01 National suppliers',                              1000.0,      75.0,     0.0,    1075.0),
                ('205.06.01.001 Extra deep code',                                0.0,      50.0,   400.0,    -350.0),
                ('205.06.03 Dotted name C.V.',                                   0.0,     400.0,    50.0,     350.0),
                ('401.01.01 Sales and/or services taxed at the general rate',    0.0,       0.0,   325.0,    -325.0),
                ('601.84.01 Other overheads',                                    0.0,     250.0,     0.0,     250.0),
                ('Result Brought Forward - ESCUELA KEMPER URGATE',          -1000.00,      0.00,    0.00,  -1000.00),
                ('Total',                                                        0.0,     775.0,   775.0,       0.0),
            ],
            options,
        )

        # Testing the report with hierarchy
        options['hierarchy'] = True
        self.env.company.totals_below_sections = False
        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                                 Initial Balance     Debit    Credit     End Balance
            [0,                                                                  1,         2,        3,         4],
            [
                ('201 Suppliers',                                             1000.0,      75.0,     0.0,    1075.0),
                ('201.01 National suppliers',                                 1000.0,      75.0,     0.0,    1075.0),
                ('201.01.01 National suppliers',                              1000.0,      75.0,     0.0,    1075.0),
                ('205 Short-term sundry creditors',                              0.0,     450.0,   450.0,       0.0),
                ('205.06 Other short-term sundry creditors',                     0.0,     450.0,   450.0,       0.0),
                ('205.06.01.001 Extra deep code',                                0.0,      50.0,   400.0,    -350.0),
                ('205.06.03 Dotted name C.V.',                                   0.0,     400.0,    50.0,     350.0),
                ('401 Income',                                                   0.0,       0.0,   325.0,    -325.0),
                ('401.01 Sales and/or services taxed at the general rate',       0.0,       0.0,   325.0,    -325.0),
                ('401.01.01 Sales and/or services taxed at the general rate',    0.0,       0.0,   325.0,    -325.0),
                ('601 Overheads',                                                0.0,     250.0,     0.0,     250.0),
                ('601.84 Other overheads',                                       0.0,     250.0,     0.0,     250.0),
                ('601.84.01 Other overheads',                                    0.0,     250.0,     0.0,     250.0),
                ('Result Brought Forward - ESCUELA KEMPER URGATE',          -1000.00,      0.00,    0.00,  -1000.00),
                ('Total',                                                        0.0,     775.0,   775.0,       0.0),
            ],
            options,
        )

    def test_coa_valid_no_certificado(self):
        """
        Test that the noCertificado section in the coa report contains 20 characters as specified by the format description:
        http://www.sat.gob.mx/esquemas/ContabilidadE/1_1/BalanzaComprobacion/BalanzaComprobacion_1_1.xsd
        """

        options = self._generate_options(self.report, '2021-01-01', '2021-12-31')
        options['l10n_mx_sat_ignore_errors'] = True

        with freeze_time(self.frozen_today):
            self.certificate.write({
                'date_start': f'{self.frozen_today.year}-01-01',
                'date_end': f'{self.frozen_today.year}-12-31',
            })
            self.company.l10n_mx_edi_certificate_ids = self.certificate
            coa_report = self.env[self.report.custom_handler_model_name].action_l10n_mx_generate_coa_sat_xml(options)['file_content']

        self.assertEqual(20, len(self.get_xml_tree_from_string(coa_report).attrib.get("noCertificado")))


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nMXTrialBalanceMonth13(TestAccountReportsCommon, HttpCase):
    """ Testing the MX Trial Balance when there are Month 13 closing entries. """
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestAccountReportsCommon.setup_country('mx')
    def setUpClass(cls):
        super().setUpClass()

        # Invoice dated 2021-12-01,
        cls._create_invoice(
            move_type='entry',
            journal_id=cls.company_data['default_journal_sale'],
            date='2021-12-01',
            line_ids=[
                cls._prepare_entry_line(
                    account_id=cls.company_data['default_account_receivable'],
                    debit=1000.0,
                    credit=0.0,
                ),
                cls._prepare_entry_line(
                    account_id=cls.company_data['default_account_revenue'],
                    debit=0.0,
                    credit=1000.0,
                ),
            ],
            post=True,
        )

        account_current_year_earnings = cls.env['account.account'].search([
            ('code', '=', '305.01.01'),
            ('company_ids', '=', cls.company_data['company'].id),
        ])

        # Month 13 closing entry dated 2021-12-31
        cls._create_invoice(
            move_type='entry',
            journal_id=cls.company_data['default_journal_sale'],
            date='2021-12-31',
            l10n_mx_closing_move=True,
            line_ids=[
                cls._prepare_entry_line(
                    account_id=cls.company_data['default_account_revenue'],
                    debit=800.0,
                    credit=0.0,
                ),
                cls._prepare_entry_line(
                    account_id=account_current_year_earnings,
                    debit=0.0,
                    credit=800.0,
                ),
            ],
            post=True,
        )

        # Invoice dated 2022-12-06
        cls._create_invoice(
            move_type='entry',
            journal_id=cls.company_data['default_journal_sale'],
            date='2022-12-06',
            line_ids=[
                cls._prepare_entry_line(
                    account_id=cls.company_data['default_account_receivable'],
                    debit=200.0,
                    credit=0.0,
                ),
                cls._prepare_entry_line(
                    account_id=cls.company_data['default_account_revenue'],
                    debit=0.0,
                    credit=200.0,
                ),
            ],
            post=True,
        )

        # Invoice dated 2022-12-31
        cls._create_invoice(
            move_type='entry',
            journal_id=cls.company_data['default_journal_sale'],
            date='2022-12-31',
            line_ids=[
                cls._prepare_entry_line(
                    account_id=cls.company_data['default_account_receivable'],
                    debit=100.0,
                    credit=0.0,
                ),
                cls._prepare_entry_line(
                    account_id=cls.company_data['default_account_revenue'],
                    debit=0.0,
                    credit=100.0,
                ),
            ],
            post=True,
        )

        # Month 13 closing entry dated 2022-12-31
        cls._create_invoice(
            move_type='entry',
            journal_id=cls.company_data['default_journal_sale'],
            date='2022-12-31',
            l10n_mx_closing_move=True,
            line_ids=[
                cls._prepare_entry_line(
                    account_id=cls.company_data['default_account_revenue'],
                    debit=250.0,
                    credit=0.0,
                ),
                cls._prepare_entry_line(
                    account_id=account_current_year_earnings,
                    debit=0.0,
                    credit=250.0,
                ),
            ],
            post=True,
        )

        # Invoice dated 2023-01-01
        cls._create_invoice(
            move_type='entry',
            journal_id=cls.company_data['default_journal_sale'],
            date='2023-01-01',
            line_ids=[
                cls._prepare_entry_line(
                    account_id=cls.company_data['default_account_receivable'],
                    debit=20.0,
                    credit=0.0,
                ),
                cls._prepare_entry_line(
                    account_id=cls.company_data['default_account_revenue'],
                    debit=0.0,
                    credit=20.0,
                ),
            ],
            post=True,
        )

        cls.report = cls.env.ref('account_reports.trial_balance_report')

    def test_non_month_13(self):
        """ Test the Trial Balance report in the case where the 'Month 13' filter is not set.
            We generate the TB for two periods: from 2022-12-01 to 2022-12-31, and from 2022-12-01 to 2023-01-01.

            For 2022-12-01 to 2022-12-31:
            - the closing entry for 2021 should appear in the initial balance
            - the closing entry for 2022 should not appear

            For 2022-12-01 to 2023-01-01:
            - the closing entry for 2021 should appear in the initial balance
            - the closing entry for 2022 should appear in the current period"""

        # Generate the Trial Balance for Dec 2022.
        options = self._generate_options(self.report, '2022-12-01', '2022-12-31', {'hierarchy': False, 'unfold_all': True})
        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                                    Initial Balance     Debit    Credit    End Balance
            [0,                                                                     1,        2,        3,         4],
            [
                ('105.01.01 Domestic customers',                                 1000.0,    300.0,     0.0,     1300.0),
                ('401.01.01 Sales and/or services taxed at the general rate',       0.0,      0.0,   300.0,     -300.0),
                ('Result Brought Forward - company_1_data',                     -1000.0,      0.0,     0.0,    -1000.0),
                ('Total',                                                           0.0,    300.0,   300.0,        0.0),

            ],
            options,
        )

        # Generate the Trial Balance between 2022-12-01 and 2023-01-01.
        options = self._generate_options(self.report, '2022-12-01', '2023-01-01', {'hierarchy': False, 'unfold_all': True})
        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                                    Initial Balance     Debit    Credit    End Balance
            [0,                                                                     1,        2,        3,         4],
            [
                ('105.01.01 Domestic customers',                                 1000.0,    320.0,      0.0,    1320.0),
                ('305.01.01 Uncut results',                                         0.0,      0.0,    250.0,    -250.0),
                ('401.01.01 Sales and/or services taxed at the general rate',       0.0,    250.0,    320.0,     -70.0),
                ('Result Brought Forward - company_1_data',                     -1000.0,      0.0,    0.0,     -1000.0),
                ('Total',                                                           0.0,    570.0,    570.0,       0.0),
            ],
            options,
        )

    def test_month_13(self):
        """ Test the Trial Balance report in the case where the 'Month 13' filter is set.
            We generate the TB for period 2022-12-01 to 2022-12-31.
            We expect:
            - the invoices in Dec 2022 and the closing entry for 2021 appear in the initial balance
            - the closing entry for 2022 appears in the current period.
        """

        # Generate the Trial Balance for Dec 2022 with the 'Month 13' filter active.
        options = self._generate_options(self.report, '2022-12-01', '2022-12-31', {'hierarchy': False, 'unfold_all': True, 'l10n_mx_month_13': True})
        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                                  [ Initial Balance ] [    Month 13   ] [ End Balance ]
            #   Name                                                           Balance     Debit   Credit      Balance
            [0,                                                                    1,         2,        3,         4],
            [
                ('105.01.01 Domestic customers',                                1300.0,       0.0,      0.0,    1300.0),
                ('305.01.01 Uncut results',                                        0.0,       0.0,    250.0,    -250.0),
                ('401.01.01 Sales and/or services taxed at the general rate',   -300.0,     250.0,      0.0,     -50.0),
                ('Result Brought Forward - company_1_data',                    -1000.0,       0.0,      0.0,   -1000.0),
                ('Total',                                                          0.0,     250.0,    250.0,       0.0),
            ],
            options,
        )

    def test_comparison(self):
        """ Test comparisons when there are Month 13 closing entries.

            - With the Month 13 filter active, comparisons are disabled (so we don't test them)
            - With the Month 13 filter inactive, the closing entry should appear as part of the month of December,
              unless December is the last period in the comparison - in that case the closing entry shouldn't appear.
        """

        # Generate the Trial Balance for Dec 2022, comparing with Nov 2022, and without the 'Month 13' filter.
        options = self._generate_options(self.report, '2022-12-01', '2022-12-31', {
            'hierarchy': False,
            'unfold_all': True,
            'comparison': {
                'filter': 'previous_period',
                'number_period': 1,
                'period_order': 'ascending',
            },
        })
        self.assertLinesValues(
            self.report._get_lines(options),
            #                                                                  [Initial]     [   Nov 2022   ]    [   Dec 2022   ]       [ End ]
            #    Name                                                           Balance       Debit    Credit     Debit    Credit       Balance
            [0,                                                                   1,             2,      3,          4,        5,          6],
            [
                ('105.01.01 Domestic customers',                               1000.0,          0.0,     0.0,      300.0,       0.0,    1300.0),
                # Values manually added to the equity unaffected account
                ('401.01.01 Sales and/or services taxed at the general rate',     0.0,          0.0,     0.0,        0.0,     300.0,    -300.0),
                ('Result Brought Forward - company_1_data',                   -1000.0,          0.0,     0.0,        0.0,       0.0,   -1000.0),
                ('Total',                                                         0.0,          0.0,     0.0,      300.0,     300.0,       0.0),
            ],
            options,
        )

        # Generate the Trial Balance for Jan 2023, comparing with Dec 2022, and without the 'Month 13' filter.
        options = self._generate_options(self.report, '2023-01-01', '2023-01-31', {
            'hierarchy': False,
            'unfold_all': True,
            'comparison': {
                'filter': 'previous_period',
                'number_period': 1,
                'period_order': 'ascending',
            },
        })
        self.assertLinesValues(
            self.report._get_lines(options),
            #                                                                  [Initial]  [   Dec 2022   ]   [Initial]   [ End ]  [   Jan 2023   ]     [ End ]
            #    Name                                                           Balance    Debit    Credit    Balance    Balance   Debit   Credit     Balance
            [0,                                                                    1,         2,        3,        4,        5,       6,       7,          8],
            [
                ('105.01.01 Domestic customers',                               1000.0,     300.0,      0.0,   1300.0,    1300.0,    20.0,      0.0,    1320.0),
                ('305.01.01 Uncut results',                                       0.0,       0.0,    250.0,   -250.0,       0.0,     0.0,      0.0,       0.0),
                ('401.01.01 Sales and/or services taxed at the general rate',     0.0,     250.0,    300.0,    -50.0,       0.0,     0.0,     20.0,     -20.0),
                ('Result Brought Forward - company_1_data',                   -1000.0,       0.0,      0.0,  -1000.0,   -1300.0,     0.0,      0.0,   -1300.0),
                ('Total',                                                         0.0,     550.0,    550.0,      0.0,       0.0,    20.0,     20.0,       0.0),
            ],
            options,
        )

    def test_tour_trial_balance_month13_date_filter(self):
        """ This test is created to ensure the date filter for Month 13 keeps working in case the date filter system
            is refactored, as this module uses a hack to add the Month 13 options with the behavior we want.
        """
        with freeze_time('2022-06-01'):
            self.start_tour("/odoo/action-account_reports.action_account_report_coa", 'trial_balance_month_13_date_filter', login=self.env.user.login)


@tagged('external_l10n', 'post_install', '-at_install', '-standard', 'external')
class TestL10nMXTrialBalanceReportXmlValidity(TestL10nMXTrialBalanceReportCommon):
    _test_user_groups = None  # FIXME list needed groups

    @test_xsd(url='https://www.sat.gob.mx/esquemas/ContabilidadE/1_3/CatalogoCuentas/CatalogoCuentas_1_3.xsd')
    def test_coa_xml_validity(self):
        options = self._generate_options(self.report, '2021-01-01', '2021-12-31')
        options['l10n_mx_sat_ignore_errors'] = True
        return self.env[self.report.custom_handler_model_name].action_l10n_mx_generate_coa_sat_xml(options)['file_content']

    @test_xsd(url='https://www.sat.gob.mx/esquemas/ContabilidadE/1_3/BalanzaComprobacion/BalanzaComprobacion_1_3.xsd')
    def test_sat_xml_validity(self):
        options = self._generate_options(self.report, '2021-01-01', '2021-12-31')
        options['l10n_mx_sat_ignore_errors'] = True
        return self.env[self.report.custom_handler_model_name].action_l10n_mx_generate_sat_xml(options)['file_content']
