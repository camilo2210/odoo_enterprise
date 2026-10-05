from freezegun import freeze_time

from odoo import Command
from odoo.tests import tagged
from odoo.addons.account_reports.tests.account_sales_report_common import AccountSalesReportCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class SlovakControlStatementTest(AccountSalesReportCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountSalesReportCommon.setup_country('sk')
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_sk_1 = cls.env['res.partner'].create({
            'name': 'Slovak Partner 1',
            'country_id': cls.env.ref('base.sk').id,
            'vat': 'SK2023000001',
            'is_company': True,
        })
        cls.partner_sk_2 = cls.env['res.partner'].create({
            'name': 'Slovak Partner 2',
            'country_id': cls.env.ref('base.sk').id,
            'vat': 'SK2720000008',
            'is_company': True,
        })
        cls.partner_eu = cls.env['res.partner'].create({
            'name': 'EU Partner',
            'country_id': cls.env.ref('base.at').id,
            'vat': 'ATU12345675',
            'is_company': True,
        })

        ChartTemplate = cls.env["account.chart.template"].with_company(cls.env.company)

        # Sale Taxes
        cls.tax_sale_23 = ChartTemplate.ref('vy_tuz_23')
        cls.tax_sale_19 = ChartTemplate.ref('vy_tuz_19')
        cls.tax_sale_5 = ChartTemplate.ref('vy_tuz_5')
        cls.tax_sale_rc = ChartTemplate.ref('vy_rc')
        # Purchase Taxes
        cls.tax_purchase_23 = ChartTemplate.ref('vs_tuz_23')
        cls.tax_purchase_19 = ChartTemplate.ref('vs_tuz_19')
        cls.tax_purchase_5 = ChartTemplate.ref('vs_tuz_5')
        cls.tax_purchase_23_simpl = ChartTemplate.ref('vs_tuz_23_simpl')
        cls.tax_purchase_19_simpl = ChartTemplate.ref('vs_tuz_19_simpl')
        cls.tax_purchase_5_simpl = ChartTemplate.ref('vs_tuz_5_simpl')
        cls.tax_purchase_rc_23 = ChartTemplate.ref('vs_rc_23')
        cls.tax_purchase_rc_19 = ChartTemplate.ref('vs_rc_19')
        cls.tax_purchase_eu_23 = ChartTemplate.ref('vs_nad_eu_23')
        cls.tax_purchase_eu_19 = ChartTemplate.ref('vs_nad_eu_19')
        cls.tax_purchase_tri_19 = ChartTemplate.ref('vs_tri_19')

        cls.uom_kg = cls.env.ref('uom.product_uom_kgm')

        cls.product_rc_7308 = cls.env['product.product'].create({
            'name': 'Iron Structures (7308)',
            'uom_id': cls.uom_kg.id,
            'account_tag_ids': [Command.set([cls.env.ref('l10n_sk_reports.tag_tk_7308').id])],
        })

        cls.company.update({
            'country_id': cls.env.ref('base.sk').id,
            'vat': 'SK2022749619',
            'email': 'info@skcompany.com',
        })

        with freeze_time('2024-02-01'):
            cls._create_control_statement_data()

    @classmethod
    def _create_control_statement_data(cls):
        moves_to_post = cls.env['account.move']

        # Section A.1
        invoice_a1_1 = cls.env['account.move'].create({
            'invoice_date': '2024-01-05',
            'date': '2024-01-05',
            'taxable_supply_date': '2024-01-05',
            'move_type': 'out_invoice',
            'partner_id': cls.partner_sk_1.id,
            'invoice_line_ids': [Command.create({'quantity': 1, **line_data}) for line_data in [
                {'price_unit': 1000, 'tax_ids': cls.tax_sale_23.ids},
                {'price_unit': 500, 'tax_ids': cls.tax_sale_19.ids},
            ]],
        })
        moves_to_post += invoice_a1_1

        moves_to_post += cls.env['account.move'].create({
            'invoice_date': '2024-01-08',
            'date': '2024-01-08',
            'taxable_supply_date': '2024-01-08',
            'move_type': 'out_invoice',
            'partner_id': cls.partner_sk_2.id,
            'invoice_line_ids': [Command.create({'quantity': 1, **line_data}) for line_data in [
                {'price_unit': 2000, 'tax_ids': cls.tax_sale_23.ids},
                {'price_unit': 300, 'tax_ids': cls.tax_sale_5.ids},
            ]],
        })

        # Section A.2
        invoice_a2_1 = cls.env['account.move'].create({
            'invoice_date': '2024-01-10',
            'date': '2024-01-10',
            'taxable_supply_date': '2024-01-10',
            'move_type': 'out_invoice',
            'partner_id': cls.partner_sk_1.id,
            'invoice_line_ids': [Command.create({
                'product_id': cls.product_rc_7308.id,
                'quantity': 10,
                'price_unit': 300,
                'product_uom_id': cls.uom_kg.id,
                'tax_ids': cls.tax_sale_rc.ids,
            })],
        })
        moves_to_post += invoice_a2_1

        # Section B.1
        moves_to_post += cls.env['account.move'].create({
            'invoice_date': '2024-01-03',
            'date': '2024-01-03',
            'taxable_supply_date': '2024-01-03',
            'move_type': 'in_invoice',
            'partner_id': cls.partner_eu.id,
            'ref': 'EU-001',
            'invoice_line_ids': [Command.create({'quantity': 1, 'price_unit': 5000, 'tax_ids': cls.tax_purchase_eu_23.ids})],
        })

        moves_to_post += cls.env['account.move'].create({
            'invoice_date': '2024-01-07',
            'date': '2024-01-07',
            'taxable_supply_date': '2024-01-07',
            'move_type': 'in_invoice',
            'partner_id': cls.partner_eu.id,
            'ref': 'EU-002',
            'invoice_line_ids': [Command.create({'quantity': 1, 'price_unit': 3000, 'tax_ids': cls.tax_purchase_eu_19.ids})],
        })

        moves_to_post += cls.env['account.move'].create({
            'invoice_date': '2024-01-12',
            'date': '2024-01-12',
            'taxable_supply_date': '2024-01-12',
            'move_type': 'in_invoice',
            'partner_id': cls.partner_sk_1.id,
            'ref': 'RC-001',
            'invoice_line_ids': [Command.create({'quantity': 1, **line_data}) for line_data in [
                {'price_unit': 1500, 'tax_ids': cls.tax_purchase_rc_23.ids},
                {'price_unit': 800, 'tax_ids': cls.tax_purchase_rc_19.ids},
            ]],
        })

        moves_to_post += cls.env['account.move'].create({
            'invoice_date': '2024-01-14',
            'date': '2024-01-14',
            'taxable_supply_date': '2024-01-14',
            'move_type': 'in_invoice',
            'partner_id': cls.partner_eu.id,
            'ref': 'TRI-001',
            'invoice_line_ids': [Command.create({'quantity': 1, 'price_unit': 4000, 'tax_ids': cls.tax_purchase_tri_19.ids})],
        })

        # Section B.2
        bill_b2_1 = cls.env['account.move'].create({
            'invoice_date': '2024-01-15',
            'date': '2024-01-15',
            'taxable_supply_date': '2024-01-15',
            'move_type': 'in_invoice',
            'partner_id': cls.partner_sk_1.id,
            'ref': 'BILL-001',
            'invoice_line_ids': [Command.create({'quantity': 1, **line_data}) for line_data in [
                {'price_unit': 4000, 'tax_ids': cls.tax_purchase_23.ids},
                {'price_unit': 1000, 'tax_ids': cls.tax_purchase_19.ids},
            ]],
        })
        moves_to_post += bill_b2_1

        moves_to_post += cls.env['account.move'].create({
            'invoice_date': '2024-01-18',
            'date': '2024-01-18',
            'taxable_supply_date': '2024-01-18',
            'move_type': 'in_invoice',
            'partner_id': cls.partner_sk_2.id,
            'ref': 'BILL-002',
            'invoice_line_ids': [Command.create({'quantity': 1, **line_data}) for line_data in [
                {'price_unit': 2000, 'tax_ids': cls.tax_purchase_23.ids},
                {'price_unit': 500, 'tax_ids': cls.tax_purchase_5.ids},
            ]],
        })

        # Section B.3.1
        moves_to_post += cls.env['account.move'].create({
            'invoice_date': '2024-01-20',
            'date': '2024-01-20',
            'taxable_supply_date': '2024-01-20',
            'move_type': 'in_receipt',
            'partner_id': cls.partner_sk_1.id,
            'ref': 'SIMP-001',
            'invoice_line_ids': [Command.create({'quantity': 1, **line_data}) for line_data in [
                {'price_unit': 40, 'tax_ids': cls.tax_purchase_23_simpl.ids},
                {'price_unit': 20, 'tax_ids': cls.tax_purchase_19_simpl.ids},
            ]],
        })

        moves_to_post += cls.env['account.move'].create({
            'invoice_date': '2024-01-22',
            'date': '2024-01-22',
            'taxable_supply_date': '2024-01-22',
            'move_type': 'in_receipt',
            'partner_id': cls.partner_sk_2.id,
            'ref': 'SIMP-002',
            'invoice_line_ids': [Command.create({'quantity': 1, 'price_unit': 50, 'tax_ids': cls.tax_purchase_5_simpl.ids})],
        })

        moves_to_post.action_post()

        # Section C.1
        credit_note_c1 = invoice_a1_1._reverse_moves([{
            'invoice_date': '2024-01-25',
            'date': '2024-01-25',
        }])

        # Section C.1 - A.2 correction (reverse charge credit note, per KVDPH spec §69(12))
        credit_note_c1_rc = invoice_a2_1._reverse_moves([{
            'invoice_date': '2024-01-25',
            'date': '2024-01-25',
        }])

        # Section C.2
        credit_note_c2 = bill_b2_1._reverse_moves([{
            'invoice_date': '2024-01-26',
            'date': '2024-01-26',
            'ref': 'RBILL-001',
        }])

        (credit_note_c1 + credit_note_c1_rc + credit_note_c2).action_post()

        # Section D - create external values for editable report cells
        # D.1
        d1_values = {
            'control_statement_D1_total_turnover': 25000,
            'control_statement_D1_tax_base_basic': 20000,
            'control_statement_D1_tax_amount_basic': 4600,
            'control_statement_D1_tax_base_reduced': 5000,
            'control_statement_D1_tax_amount_reduced': 950,
        }
        for xmlid, value in d1_values.items():
            cls.env['account.report.external.value'].create({
                'name': 'Manual value',
                'target_report_expression_id': cls.env.ref(f'l10n_sk_reports.{xmlid}').id,
                'value': value,
                'date': '2024-01-31',
                'company_id': cls.env.company.id,
            })

        # D.2
        d2_values = {
            'control_statement_D2_tax_base_basic': 3000,
            'control_statement_D2_tax_amount_basic': 690,
            'control_statement_D2_tax_base_reduced': 1000,
            'control_statement_D2_tax_amount_reduced': 190,
        }
        for xmlid, value in d2_values.items():
            cls.env['account.report.external.value'].create({
                'name': 'Manual value',
                'target_report_expression_id': cls.env.ref(f'l10n_sk_reports.{xmlid}').id,
                'value': value,
                'date': '2024-01-31',
                'company_id': cls.env.company.id,
            })

    def test_control_statement_section_a(self):
        section_a = self.env.ref('l10n_sk_reports.control_statement_report_section_a')
        options_a = self._generate_options(section_a, '2024-01-01', '2024-01-31', default_options={'unfold_all': True})
        self.assertLinesValues(
            section_a._get_lines(options_a),
            #   Name                                        VAT Number        Invoice Number      Date           Tax Base  Tax Amount  Tax Rate  Goods Code  Goods Type  Quantity  UoM
            [   0,                                          1,                2,                  3,             4,        5,          6,        7,          8,          9,        10],
            [
                ('A.1. Standard taxable supplies',          '',               '',                 '',            3800,     800,        0,        '',         '',         '',       ''),
                ('INV/2024/00002',                          'SK2720000008',   'INV/2024/00002',   '2024-01-08',  2300,     475,        0,        '',         '',         '',       ''),
                ( '5%',                                     'SK2720000008',   'INV/2024/00002',   '2024-01-08',  300,      15,         5,        '',         '',         1.0,      ''),
                ( '23%',                                    'SK2720000008',   'INV/2024/00002',   '2024-01-08',  2000,     460,        23,       '',         '',         1.0,      ''),
                ('INV/2024/00001',                          'SK2023000001',   'INV/2024/00001',   '2024-01-05',  1500,     325,        0,        '',         '',         '',       ''),
                ( '19%',                                    'SK2023000001',   'INV/2024/00001',   '2024-01-05',  500,      95,         19,       '',         '',         1.0,      ''),
                ( '23%',                                    'SK2023000001',   'INV/2024/00001',   '2024-01-05',  1000,     230,        23,       '',         '',         1.0,      ''),
                ('A.2. Domestic reverse charge supplies',   '',               '',                 '',            3000,     0,          0,        '',         '',         '',       ''),
                ('INV/2024/00003',                          'SK2023000001',   'INV/2024/00003',   '2024-01-10',  3000,     0,          0,        '',         '',         '',       ''),
                ( 'TK 7308',                                'SK2023000001',   'INV/2024/00003',   '2024-01-10',  3000,     0,          0,        '7308',     '',         10.0,     'kg'),
            ],
            options_a,
        )

    def test_control_statement_section_b(self):
        section_b = self.env.ref('l10n_sk_reports.control_statement_report_section_b')
        options_b = self._generate_options(section_b, '2024-01-01', '2024-01-31', default_options={'unfold_all': True})
        self.assertLinesValues(
            section_b._get_lines(options_b),
            #   Name                                                  VAT Number        Invoice Number  Date           Tax Base  Tax Amount  Tax Rate  Deducted
            [   0,                                                    1,                2,              3,             4,        5,          6,        7],
            [
                ('B.1. Reverse charge purchases',                     '',               '',             '',            14300,    2977,       0,        2977),
                ('BILL/2024/01/0004 (TRI-001)',                       'ATU12345675',    'TRI-001',      '2024-01-14',  4000,     760,        0,        760),
                ( '19%',                                              'ATU12345675',    'TRI-001',      '2024-01-14',  4000,     760,        19,       760),
                ('BILL/2024/01/0003 (RC-001)',                        'SK2023000001',   'RC-001',       '2024-01-12',  2300,     497,        0,        497),
                ( '19%',                                              'SK2023000001',   'RC-001',       '2024-01-12',  800,      152,        19,       152),
                ( '23%',                                              'SK2023000001',   'RC-001',       '2024-01-12',  1500,     345,        23,       345),
                ('BILL/2024/01/0002 (EU-002)',                        'ATU12345675',    'EU-002',       '2024-01-07',  3000,     570,        0,        570),
                ( '19%',                                              'ATU12345675',    'EU-002',       '2024-01-07',  3000,     570,        19,       570),
                ('BILL/2024/01/0001 (EU-001)',                        'ATU12345675',    'EU-001',       '2024-01-03',  5000,     1150,       0,        1150),
                ( '23%',                                              'ATU12345675',    'EU-001',       '2024-01-03',  5000,     1150,       23,       1150),
                ('B.2. Standard purchases with deduction',            '',               '',             '',            7500,     1595,       0,        1595),
                ('BILL/2024/01/0006 (BILL-002)',                      'SK2720000008',   'BILL-002',     '2024-01-18',  2500,     485,        0,        485),
                ( '5%',                                               'SK2720000008',   'BILL-002',     '2024-01-18',  500,      25,         5,        25),
                ( '23%',                                              'SK2720000008',   'BILL-002',     '2024-01-18',  2000,     460,        23,       460),
                ('BILL/2024/01/0005 (BILL-001)',                      'SK2023000001',   'BILL-001',     '2024-01-15',  5000,     1110,       0,        1110),
                ( '19%',                                              'SK2023000001',   'BILL-001',     '2024-01-15',  1000,     190,        19,       190),
                ( '23%',                                              'SK2023000001',   'BILL-001',     '2024-01-15',  4000,     920,        23,       920),
                ('B.3.1. Simplified invoices (total < 3,000 EUR)',    '',               '',             '',            110,      15.5,       '',       15.5),
                ('B.3.2. Simplified invoices (total >= 3,000 EUR)',   '',               '',             '',            0,        0,          '',       0),
            ],
            options_b,
        )

    def test_control_statement_section_c(self):
        section_c = self.env.ref('l10n_sk_reports.control_statement_report_section_c')
        options_c = self._generate_options(section_c, '2024-01-01', '2024-01-31', default_options={'unfold_all': True})
        self.assertLinesValues(
            section_c._get_lines(options_c),
            #   Name                                        VAT Number        Corrective Invoice      Original Invoice   Base Diff  Tax Diff  Tax Rate  Ded. Diff  Goods Code  Goods Type  Quantity  UoM    Bad Debt
            [   0,                                          1,                2,                      3,                 4,         5,        6,        7,         8,          9,          10,       11,    12],
            [
                ('C.1. Corrections to issued supplies',     '',               '',                     '',                -4500,     -325,     0,        0,         '',         '',         '',       '',    'No'),
                ('RINV/2024/00002',                         'SK2023000001',   'RINV/2024/00002',      'INV/2024/00003',  -3000,      0,       0,        0,         '7308',     '',         '',       '',    'No'),
                ( 'No Tax',                                 'SK2023000001',   'RINV/2024/00002',      'INV/2024/00003',  -3000,      0,       0,        0,         '7308',     '',         -10.0,    'kg',  'No'),
                ('RINV/2024/00001',                         'SK2023000001',   'RINV/2024/00001',      'INV/2024/00001',  -1500,     -325,     0,        0,         '',         '',         '',       '',    'No'),
                ( '19%',                                    'SK2023000001',   'RINV/2024/00001',      'INV/2024/00001',  -500,      -95,      19,       0,         '',         '',         -1.0,     '',    'No'),
                ( '23%',                                    'SK2023000001',   'RINV/2024/00001',      'INV/2024/00001',  -1000,     -230,     23,       0,         '',         '',         -1.0,     '',    'No'),
                ('C.2. Corrections to received supplies',   '',               '',                     '',                -5000,     -1110,    0,        -1110,     '',         '',         '',       '',    'No'),
                ('RBILL/2024/01/0001 (RBILL-001)',                      'SK2023000001',   'RBILL-001',            'BILL-001',        -5000,     -1110,    0,        -1110,     '',         '',         '',       '',    'No'),
                ( '19%',                                    'SK2023000001',   'RBILL-001',            'BILL-001',        -1000,     -190,     19,       -190,      '',         '',         1.0,      '',    'No'),
                ( '23%',                                    'SK2023000001',   'RBILL-001',            'BILL-001',        -4000,     -920,     23,       -920,      '',         '',         1.0,      '',    'No'),
            ],
            options_c,
        )

    def test_control_statement_section_d(self):
        section_d = self.env.ref('l10n_sk_reports.control_statement_report_section_d')
        options_d = self._generate_options(section_d, '2024-01-01', '2024-01-31')
        self.assertLinesValues(
            section_d._get_lines(options_d),
            #   Name                               Total Turnover  Base Basic  Amount Basic  Base Reduced  Amount Reduced
            [   0,                                  1,              2,          3,            4,            5],
            [
                ('D.1. E-KASA Aggregate Totals',    25000,          20000,      4600,         5000,         950),
                ('D.2. Other Supplies',             '',             3000,       690,          1000,         190),
            ],
            options_d,
        )

    def test_generate_xml_control_statement(self):
        report = self.env.ref('l10n_sk_reports.control_statement_report')
        options = self._generate_options(report, '2024-01-01', '2024-01-31')

        expected_xml = """
        <KVDPH_2025 xmlns="https://ekr.financnasprava.sk/Formulare/XSD/kv_dph_2025.xsd">
            <Identifikacia>
                <IcDphPlatitela>SK2022749619</IcDphPlatitela>
                <Druh>R</Druh>
                <Obdobie>
                    <Rok>2024</Rok>
                    <Mesiac>1</Mesiac>
                </Obdobie>
                <Nazov>company_1_data</Nazov>
                <Stat>Slovakia</Stat>
                <Obec/>
                <Tel>+32475123456</Tel>
                <Email>info@skcompany.com</Email>
            </Identifikacia>
            <Transakcie>
                <A1 Odb="SK2720000008" F="INV/2024/00002" Den="2024-01-08" Z="300.00" D="15.00" S="5"/>
                <A1 Odb="SK2720000008" F="INV/2024/00002" Den="2024-01-08" Z="2000.00" D="460.00" S="23"/>
                <A1 Odb="SK2023000001" F="INV/2024/00001" Den="2024-01-05" Z="500.00" D="95.00" S="19"/>
                <A1 Odb="SK2023000001" F="INV/2024/00001" Den="2024-01-05" Z="1000.00" D="230.00" S="23"/>
                <A2 Odb="SK2023000001" F="INV/2024/00003" Den="2024-01-10" Z="3000.00" TK="7308" Mn="10.00" MJ="kg"/>
                <B1 Dod="ATU12345675" F="TRI-001" Den="2024-01-14" Z="4000.00" D="760.00" S="19" O="760.00"/>
                <B1 Dod="SK2023000001" F="RC-001" Den="2024-01-12" Z="800.00" D="152.00" S="19" O="152.00"/>
                <B1 Dod="SK2023000001" F="RC-001" Den="2024-01-12" Z="1500.00" D="345.00" S="23" O="345.00"/>
                <B1 Dod="ATU12345675" F="EU-002" Den="2024-01-07" Z="3000.00" D="570.00" S="19" O="570.00"/>
                <B1 Dod="ATU12345675" F="EU-001" Den="2024-01-03" Z="5000.00" D="1150.00" S="23" O="1150.00"/>
                <B2 Dod="SK2720000008" F="BILL-002" Den="2024-01-18" Z="500.00" D="25.00" S="5" O="25.00"/>
                <B2 Dod="SK2720000008" F="BILL-002" Den="2024-01-18" Z="2000.00" D="460.00" S="23" O="460.00"/>
                <B2 Dod="SK2023000001" F="BILL-001" Den="2024-01-15" Z="1000.00" D="190.00" S="19" O="190.00"/>
                <B2 Dod="SK2023000001" F="BILL-001" Den="2024-01-15" Z="4000.00" D="920.00" S="23" O="920.00"/>
                <B31 Z="110.00" D="15.50" O="15.50"/>
                <C1 Odb="SK2023000001" FO="RINV/2024/00002" FP="INV/2024/00003" ZR="-3000.00" DR="0.00" TK="7308" Mn="-10.00" MJ="kg"/>
                <C1 Odb="SK2023000001" FO="RINV/2024/00001" FP="INV/2024/00001" ZR="-500.00" DR="-95.00" S="19" Mn="-1.00"/>
                <C1 Odb="SK2023000001" FO="RINV/2024/00001" FP="INV/2024/00001" ZR="-1000.00" DR="-230.00" S="23" Mn="-1.00"/>
                <C2 Dod="SK2023000001" FO="RBILL-001" FP="BILL-001" ZR="-1000.00" DR="-190.00" S="19" OR="-190.00"/>
                <C2 Dod="SK2023000001" FO="RBILL-001" FP="BILL-001" ZR="-4000.00" DR="-920.00" S="23" OR="-920.00"/>
                <D1 SumaObratov="25000.00" Z="20000.00" D="4600.00" ZZn="5000.00" DZn="950.00"/>
                <D2 Z="3000.00" D="690.00" ZZn="1000.00" DZn="190.00"/>
            </Transakcie>
        </KVDPH_2025>
        """

        actual_xml = self.env[report.custom_handler_model_name].l10n_sk_export_vat_control_report_to_xml(options)['file_content']
        self.assertXmlTreeEqual(
            self.get_xml_tree_from_string(actual_xml),
            self.get_xml_tree_from_string(expected_xml)
        )
