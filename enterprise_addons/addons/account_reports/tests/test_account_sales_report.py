from odoo import Command
from odoo.addons.account_reports.tests.account_sales_report_common import AccountSalesReportCommon
from odoo.tests import tagged
from freezegun import freeze_time


@tagged('post_install', '-at_install')
class AccountSalesReportTest(AccountSalesReportCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.totals_below_sections = False
        cls.report_generic = cls.env.ref('account_reports.generic_ec_sales_report')
        cls.env.company.account_fiscal_country_id = cls.env.ref('base.pt').id

        columns = ['country_code', 'vat_number', 'goods', 'services', 'triangular', 'balance']
        cls.report_groupby_partner = cls._create_ec_sales_report(grouping_key='partner_id', columns=columns, name="Report using grouping per partner")

        columns = ['country_code', 'vat_number', 'sale_type_shortcut', 'balance']
        cls.report_groupby_partner_and_category = cls._create_ec_sales_report(grouping_key='partner_id_and_sale_type', columns=columns, name="Report using grouping per partner and category")

        cls.goods_tag = cls.env['account.account.tag'].create([{
            'name': "goods",
            'applicability': 'taxes',
            'country_id': cls.env.company.account_fiscal_country_id.id,
        }])
        cls.services_tag = cls.env['account.account.tag'].create([{
            'name': "services",
            'applicability': 'taxes',
            'country_id': cls.env.company.account_fiscal_country_id.id,
        }])
        cls.triangular_tag = cls.env['account.account.tag'].create([{
            'name': "triangular",
            'applicability': 'taxes',
            'country_id': cls.env.company.account_fiscal_country_id.id,
        }])

        tax_group = cls.env['account.tax.group'].create({
            'name': 'Test tax group',
            'country_id': cls.env.company.account_fiscal_country_id.id,
            'company_id': cls.env.company.id,
        })

        cls.goods_tax = cls.env['account.tax'].create([{
            'name': 'goods',
            'amount_type': 'percent',
            'amount': 0,
            'type_tax_use': 'sale',
            'price_include_override': 'tax_excluded',
            'include_base_amount': False,
            'country_id': cls.env.company.account_fiscal_country_id.id,
            'tax_group_id': tax_group.id,
            'invoice_repartition_line_ids': [
                Command.create({
                    'repartition_type': 'base',
                    'tag_ids': [Command.set(cls.goods_tag.ids)],
                }),
                Command.create({'repartition_type': 'tax'}),
            ],
        }])
        cls.triangular_tax = cls.env['account.tax'].create([{
            'name': 'triangular',
            'amount_type': 'percent',
            'amount': 0,
            'type_tax_use': 'sale',
            'price_include_override': 'tax_excluded',
            'include_base_amount': False,
            'country_id': cls.env.company.account_fiscal_country_id.id,
            'tax_group_id': tax_group.id,
            'invoice_repartition_line_ids': [
                Command.create({
                    'repartition_type': 'base',
                    'tag_ids': [Command.set(cls.triangular_tag.ids)],
                }),
                Command.create({'repartition_type': 'tax'}),
            ],
        }])
        cls.services_tax = cls.env['account.tax'].create([{
            'name': 'services',
            'amount_type': 'percent',
            'amount': 0,
            'type_tax_use': 'sale',
            'price_include_override': 'tax_excluded',
            'include_base_amount': False,
            'country_id': cls.env.company.account_fiscal_country_id.id,
            'tax_group_id': tax_group.id,
            'invoice_repartition_line_ids': [
                Command.create({
                    'repartition_type': 'base',
                    'tag_ids': [Command.set(cls.services_tag.ids)],
                }),
                Command.create({'repartition_type': 'tax'}),
            ],
        }])
        cls.bad_tax_1 = cls.env['account.tax'].create([{
            'name': 'bad_1',
            'amount_type': 'fixed',
            'amount': 0,
            'type_tax_use': 'sale',
            'price_include_override': 'tax_excluded',
            'include_base_amount': False,
        }])
        cls.bad_tax_2 = cls.env['account.tax'].create([{
            'name': 'bad_2',
            'amount_type': 'percent',
            'amount': 10,
            'type_tax_use': 'sale',
            'price_include_override': 'tax_excluded',
            'include_base_amount': False,
        }])
        cls.bad_tax_3 = cls.env['account.tax'].create([{
            'name': 'bad_2',
            'amount_type': 'percent',
            'amount': 0,
            'type_tax_use': 'purchase',
            'price_include_override': 'tax_excluded',
            'include_base_amount': False,
        }])

    # -------------------------------------------------------------------------
    # HELPER METHODS
    # -------------------------------------------------------------------------

    @classmethod
    def _create_ec_sales_report(cls, grouping_key, columns, name):
        return cls.env['account.report'].create([{
            'name': name,
            'root_report_id': cls.env.ref('account_reports.generic_ec_sales_report').id,
            'custom_handler_model_id': cls.env.ref('account_reports.model_account_ec_sales_with_tags_report_handler').id,
            'column_ids': [
                Command.create({
                    'name': col,
                    'expression_label': col,
                    'figure_type': 'string',
                    'sortable': True
                })
                for col in columns
            ],
            'line_ids': [
                Command.create({
                    'name': 'EC Sales Report',
                    'code': 'ec',
                    'groupby': grouping_key,
                    'foldability': 'always_unfolded',
                    'expression_ids': [
                        Command.create({
                            'label': col,
                            'engine': 'custom',
                            'formula': '_report_engine_ec_sales_report',
                            'auditable': True,
                            'subformula': col
                        })
                        for col in columns
                    ],
                })
            ]
        }])

    def _generate_ec_sales_report_options(self, report, date_from, date_to, default_options=None):
        """ Generates options and simulate what each custom options initializer is supposed to do in localizations.
            The name key is only useful for report with a grouping 'partner_id_and_sale_type'
        """
        default_options = {} if default_options is None else default_options
        default_options['sales_report_operation_types'] = {
            'goods': {
                'tax_tag_ids': self.goods_tag.ids,
                'name': 'Goods',
                'shortcut': 'G',
            },
            'services': {
                'tax_tag_ids': self.services_tag.ids,
                'name': 'Services',
                'shortcut': 'S',
            },
            'triangular': {
                'tax_tag_ids': self.triangular_tag.ids,
                'name': 'Triangular',
                'shortcut': 'T',
            },
        }
        options = self._generate_options(report, date_from, date_to, default_options)

        return options

    # -------------------------------------------------------------------------
    # TESTS
    # -------------------------------------------------------------------------

    @freeze_time('2019-12-31')
    def test_ec_sales_report(self):
        self._create_invoices([
            (self.partner_a, self.goods_tax[:1], 100),
            (self.partner_a, self.goods_tax[:1], 200),
            (self.partner_a, self.triangular_tax[:1], 300),
            (self.partner_b, self.triangular_tax[:1], 100),
            (self.partner_a, self.services_tax[:1], 400),
            (self.partner_b, self.services_tax[:1], 500),
            (self.partner_b, self.bad_tax_1[:1], 700),  # Should be ignored from generic report due to fixed amount
            (self.partner_b, self.bad_tax_2[:1], 700),  # Should be ignored from generic report due to non-null amount
            (self.partner_b, self.bad_tax_3[:1], 700),  # Should be ignored from generic report due to purchase tax
        ])

        # Generic Report
        options = self._generate_options(self.report_generic, '2019-12-01', '2019-12-31')
        self.assertLinesValues(
            self.report_generic._get_lines(options),
            #   Partner                          country code                VAT Number       Amount
            [0,                                             1,                        2,          3],
            [
                ('EC Sales Report',                         '',                       '',    1600.0),
                (self.partner_a.name,   self.partner_a.vat[:2],   self.partner_a.vat[2:],    1000.0),
                (self.partner_b.name,   self.partner_b.vat[:2],   self.partner_b.vat[2:],     600.0),
            ],
            options,
        )

        # Report Groupby Partner
        options = self._generate_ec_sales_report_options(self.report_groupby_partner, '2019-12-01', '2019-12-31')
        self.assertLinesValues(
            self.report_groupby_partner._get_lines(options),
            #   Partner                          country code                VAT Number      Goods    Services    Triangular      Amount
            [0,                                             1,                        2,         3,          4,           5,          6],
            [
                ('EC Sales Report',                        '',                       '',     300.0,      900.0,       400.0,     1600.0),
                (self.partner_a.name,   self.partner_a.vat[:2],   self.partner_a.vat[2:],    300.0,      400.0,       300.0,     1000.0),
                (self.partner_b.name,   self.partner_b.vat[:2],   self.partner_b.vat[2:],      0.0,      500.0,       100.0,      600.0),
            ],
            options,
        )

        # Report Groupby Partner and Tax Code
        options = self._generate_ec_sales_report_options(self.report_groupby_partner_and_category, '2019-12-01', '2019-12-31')
        self.assertLinesValues(
            self.report_groupby_partner_and_category._get_lines(options),
            #   Partner                          country code                VAT Number      Tax Code       Amount
            [0,                                             1,                        2,           3,           4],
            [
                ('EC Sales Report',                        '',                       '',           '',     1600.0),
                (self.partner_a.name,   self.partner_a.vat[:2],   self.partner_a.vat[2:],         'G',      300.0),
                (self.partner_a.name,   self.partner_a.vat[:2],   self.partner_a.vat[2:],         'S',      400.0),
                (self.partner_a.name,   self.partner_a.vat[:2],   self.partner_a.vat[2:],         'T',      300.0),
                (self.partner_b.name,   self.partner_b.vat[:2],   self.partner_b.vat[2:],         'S',      500.0),
                (self.partner_b.name,   self.partner_b.vat[:2],   self.partner_b.vat[2:],         'T',      100.0),
            ],
            options,
        )

    @freeze_time('2019-12-31')
    def test_ec_sales_report_with_northern_irish_customer(self):
        """
        Ensure that Northern Irish companies are included in the EC sales report.
        """
        northern_ireland = self.env.ref('base.xi')
        self.partner_a.write({
            'country_id': northern_ireland.id,
            'vat': 'IE1234567FA',
        })

        self._create_invoices([(self.partner_a, self.goods_tax, 100)])
        options = self._generate_options(self.report_generic, '2019-12-01', '2019-12-31')

        self.assertLinesValues(
            self.report_generic._get_lines(options),
            #   Partner,                        country code,             VAT Number,       Amount
            [   0,                                  1,                        2,                3],
            [
                ('EC Sales Report',     '',                       '',                       100.0),
                (self.partner_a.name,   self.partner_a.vat[:2],   self.partner_a.vat[2:],   100.0),
            ],
            options,
        )

    def test_ec_sales_set_as_main(self):
        """Test setting a partner as the main in EC Sales Report when two partners share the same VAT.
        Scenario:
        - Two partners have the same VAT.
        - Set one partner as the main partner.
        - Validate that the second partner is linked correctly as a child and that moves are updated.
        """
        # Prepare partners
        partner_main = self.partner_a
        partner_duplicate = self.partner_b
        partner_duplicate.vat = partner_main.vat

        move_vals = {
            'move_type': 'out_invoice',
            'invoice_date': '2025-04-29',
            'invoice_line_ids': [Command.create({
                'quantity': 1,
                'price_unit': 500.0,
                'tax_ids': [],
            })],
        }
        # Create and post invoice for the main partner
        move_main = self.env['account.move'].create({**move_vals, 'partner_id': partner_main.id})
        move_main.action_post()
        # Create and post invoice for the duplicate partner
        move_duplicate = self.env['account.move'].create({**move_vals, 'partner_id': partner_duplicate.id})
        move_duplicate.action_post()

        # Call with context
        partner_main.with_context(duplicate_partners_vat=[partner_main.vat, partner_duplicate.vat]).set_commercial_partner_main()

        # Assertions: partner relationships
        self.assertEqual(
            partner_duplicate.commercial_partner_id, partner_main,
            "Duplicate partner's commercial partner should be the main partner."
        )
        self.assertEqual(
            partner_duplicate.parent_id, partner_main,
            "Duplicate partner's parent should be set to the main partner."
        )

        # Assertions: accounting move reassignment
        self.assertEqual(
            move_duplicate.commercial_partner_id, partner_main,
            "The move's commercial partner should also be reassigned."
        )

        # Assertions: journal items (move lines)
        self.assertEqual(
            move_duplicate.line_ids.partner_id, partner_main,
            "Each move line should now be assigned to the main partner."
        )

    def test_ec_sales_report_with_other_groupby_levels(self):
        """Ensure generic EC Sales report works with other groupings, either before or after the default 'partner_id' key"""
        self._create_invoices([
            (self.partner_a, self.goods_tax[:1], 100),
            (self.partner_b, self.goods_tax[:1], 200),
            (self.partner_a, self.services_tax[:1], 300),
            (self.partner_b, self.services_tax[:1], 400),
        ])

        # Generic Report
        self.report_generic.line_ids[0].user_groupby = 'company_id,partner_id,id'
        self.report_generic.filter_unfold_all = True
        options = self._generate_options(self.report_generic, '2019-12-01', '2019-12-31', default_options={'unfold_all': True})
        self.assertLinesValues(
            self.report_generic._get_lines(options),
            #   Partner,                     country code          VAT Number         Amount
            [0,                                     1,                  2,              3],
            [
                ('EC Sales Report',                   '',                '',         1000.0),
                ('company_1_data',                    '',                '',         1000.0),
                ('Partner A',                       'FR',     '23334175221',          400.0),
                ('INV/2019/00003 line_1',             '',                '',          300.0),
                ('INV/2019/00001 line_1',             '',                '',          100.0),
                ('Partner B',                       'BE',      '0477472701',          600.0),
                ('INV/2019/00004 line_1',             '',                '',          400.0),
                ('INV/2019/00002 line_1',             '',                '',          200.0),
            ],
            options,
        )

        # Report Groupby Partner
        self.report_groupby_partner.line_ids[0].user_groupby = 'company_id,partner_id,id'
        self.report_groupby_partner.filter_unfold_all = True
        options = self._generate_ec_sales_report_options(self.report_groupby_partner, '2019-12-01', '2019-12-31', default_options={'unfold_all': True})
        self.assertLinesValues(
            self.report_groupby_partner._get_lines(options),
            #   Partner                      country code        VAT Number      Goods   Services  Triangular   Amount
            [0,                                        1,                 2,         3,        4,      5,          6],
            [
                ('EC Sales Report',                   '',                '',     300.0,    700.0,    0.0,    1000.0),
                ('company_1_data',                    '',                '',     300.0,    700.0,    0.0,    1000.0),
                ('Partner A',                       'FR',     '23334175221',     100.0,    300.0,    0.0,     400.0),
                ('INV/2019/00003 line_1',             '',                '',       0.0,    300.0,    0.0,     300.0),
                ('INV/2019/00001 line_1',             '',                '',     100.0,      0.0,    0.0,     100.0),
                ('Partner B',                       'BE',      '0477472701',     200.0,    400.0,    0.0,     600.0),
                ('INV/2019/00004 line_1',             '',                '',       0.0,    400.0,    0.0,     400.0),
                ('INV/2019/00002 line_1',             '',                '',     200.0,      0.0,    0.0,     200.0),
            ],
            options,
        )

        # Report Groupby Partner and Tax Code
        self.report_groupby_partner_and_category.line_ids[0].user_groupby = 'company_id,partner_id,partner_id_and_sale_type,id'
        self.report_groupby_partner_and_category.filter_unfold_all = True
        options = self._generate_ec_sales_report_options(self.report_groupby_partner_and_category, '2019-12-01', '2019-12-31', default_options={'unfold_all': True})
        self.assertLinesValues(
            self.report_groupby_partner_and_category._get_lines(options),
            #   Partner                      country code          VAT Number   Tax Code      Amount
            [0,                                        1,                  2,         3,          4],
            [
                ('EC Sales Report',                     '',                '',       '',     1000.0),
                (  'company_1_data',                    '',                '',       '',     1000.0),
                (    'Partner A',                      'FR',     '23334175221',      '',      400.0),
                (      'Partner A',                    'FR',     '23334175221',     'G',      100.0),
                (        'INV/2019/00001 line_1',        '',                '',      '',      100.0),
                (      'Partner A',                    'FR',     '23334175221',     'S',      300.0),
                (        'INV/2019/00003 line_1',        '',                '',      '',      300.0),
                (    'Partner B',                      'BE',      '0477472701',      '',      600.0),
                (      'Partner B',                    'BE',      '0477472701',     'G',      200.0),
                (        'INV/2019/00002 line_1',        '',                '',      '',      200.0),
                (      'Partner B',                    'BE',      '0477472701',     'S',      400.0),
                (        'INV/2019/00004 line_1',        '',                '',      '',      400.0),
            ],
            options,
        )

    @freeze_time('2019-12-31')
    def test_ec_sales_generic_report_double_taxes_applied(self):
        """ A move with 2 valid taxes should not be counted twice in the report """
        invoice = self.env['account.move'].create([{
            'move_type': 'out_invoice',
            'date': '2019-12-01',
            'partner_id': self.partner_a.id,
            'invoice_line_ids': [
                Command.create({
                    'name': "line 1",
                    'price_unit': 100,
                    'tax_ids': [Command.set((self.goods_tax + self.services_tax).ids)],
                })
            ]
        }])
        invoice.action_post()

        options = self._generate_options(self.report_generic, '2019-12-01', '2019-12-31')

        self.assertLinesValues(
            self.report_generic._get_lines(options),
            #   Partner,               country code          VAT Number         Amount
            [0,                                   1,                  2,            3],
            [
                ('EC Sales Report',              '',                '',          100.0),
                ('Partner A',                  'FR',     '23334175221',          100.0),
            ],
            options,
        )

    @freeze_time('2019-12-31')
    def test_ec_sales_report_double_tags_applied(self):
        """ Ensure that if 2 tags are used on the same account move line, then the aml is not
        counted twice on the report (Austrian use case, reason of the CTE in the query) """

        other_goods_tag = self.env['account.account.tag'].create([{
            'name': "goods_2",
            'applicability': 'taxes',
            'country_id': self.env.company.country_id.id,
        }])

        goods_tax_double_tags = self.env['account.tax'].create([{
            'name': 'goods with double tags',
            'amount_type': 'percent',
            'amount': 0,
            'type_tax_use': 'sale',
            'price_include_override': 'tax_excluded',
            'include_base_amount': False,
            'invoice_repartition_line_ids': [
                Command.create({
                    'repartition_type': 'base',
                    'tag_ids': [Command.set((self.goods_tag | other_goods_tag).ids)],
                }),
                Command.create({'repartition_type': 'tax'}),
            ],
        }])

        invoice = self.env['account.move'].create([{
            'move_type': 'out_invoice',
            'date': '2019-12-01',
            'partner_id': self.partner_a.id,
            'invoice_line_ids': [
                Command.create({
                    'name': "line 1",
                    'price_unit': 100,
                    'tax_ids': [Command.set(goods_tax_double_tags.ids)],
                })
            ]
        }])
        invoice.action_post()

        options = self._generate_ec_sales_report_options(self.report_groupby_partner, '2019-12-01', '2019-12-31')
        options['sales_report_operation_types']['goods']['tax_tag_ids'] = (self.goods_tag | other_goods_tag).ids
        self.assertLinesValues(
            self.report_groupby_partner._get_lines(options),
            #   Partner                      country code        VAT Number      Goods   Services  Triangular   Amount
            [0,                                        1,                 2,         3,        4,      5,          6],
            [
                ('EC Sales Report',                   '',                '',      100.0,      0.0,    0.0,      100.0),
                ('Partner A',                       'FR',     '23334175221',      100.0,      0.0,    0.0,      100.0),
            ],
            options,
        )

    def test_ec_sales_report_filter_selection(self):
        """ Ensure that the ec categories are filtered out if the corresponding filter is not selected """
        self._create_invoices([
            (self.partner_a, self.goods_tax[:1], 100),
            (self.partner_a, self.services_tax[:1], 100),  # Should be hidden since service filter is not selected
        ])

        options = self._generate_ec_sales_report_options(self.report_groupby_partner_and_category, '2019-12-01', '2019-12-31')
        options['filter_sale_type_selection'] = [
            {'id': 'goods', 'name': 'goods', 'selected': True},
            {'id': 'services', 'name': 'services', 'selected': False},
            {'id': 'triangular', 'name': 'triangular', 'selected': True},
        ]

        self.assertLinesValues(
            self.report_groupby_partner_and_category._get_lines(options),
            #   Partner                          country code                VAT Number      Tax Code       Amount
            [0,                                             1,                        2,           3,           4],
            [
                ('EC Sales Report',                        '',                       '',           '',      100.0),
                (self.partner_a.name,   self.partner_a.vat[:2],   self.partner_a.vat[2:],         'G',      100.0),
            ],
            options,
        )

    def test_ec_sales_report_warnings(self):
        """ Ensure warnings are generated if their conditions are met """
        partner_without_vat = self.env['res.partner'].create([{
            'name': 'Partner Without VAT Number',
            'country_id': self.env.ref('base.ee').id,
        }])

        partner_same_country = self.env['res.partner'].create([{
            'name': 'Partner Same Country',
            'vat': '12345678',
            'country_id': self.company_data['company'].country_id.id,
        }])

        partner_no_ec_country = self.env['res.partner'].create([{
            'name': 'Partner outside EC countries',
            'vat': '11345678',
            'country_id': self.env.ref('base.ma').id,
        }])

        self._create_invoices([
            (partner_without_vat, self.goods_tax[:1], 100),
            (partner_same_country, self.goods_tax[:1], 100),
            (partner_no_ec_country, self.goods_tax[:1], 100),
        ])

        options = self._generate_ec_sales_report_options(self.report_groupby_partner, '2019-12-01', '2019-12-31')
        report_information = self.report_groupby_partner.get_report_information(options)
        self.assertEqual(
            report_information['warnings'],
            {
                'account_reports.sales_report_warning_missing_vat': {'alert_type': 'warning'},
                'account_reports.sales_report_warning_non_ec_country': {'alert_type': 'warning'},
                'account_reports.sales_report_warning_same_country': {'alert_type': 'warning'},
            }
        )

    def test_ec_sales_report_warnings_children(self):
        """ Ensure warnings are generated if their conditions are met """
        partner_same_country = self.env['res.partner'].create([{
            'name': 'Partner Same Country',
            'vat': '12345678',
            'country_id': self.company_data['company'].country_id.id,
            'child_ids': [
                Command.create({
                    'type': 'delivery',
                    'country_id': self.env.ref('base.fr').id,
                })
            ]
        }])

        partner_no_ec_country = self.env['res.partner'].create([{
            'name': 'Partner outside EC countries',
            'vat': '11345678',
            'country_id': self.env.ref('base.ma').id,
            'child_ids': [
                Command.create({
                    'type': 'delivery',
                    'country_id': self.env.ref('base.fr').id,
                })
            ]
        }])

        self._create_invoices([
            (partner_same_country.child_ids[0], self.goods_tax[:1], 100),
            (partner_no_ec_country.child_ids[0], self.goods_tax[:1], 100),
        ])

        options = self._generate_ec_sales_report_options(self.report_groupby_partner, '2019-12-01', '2019-12-31')
        report_information = self.report_groupby_partner.get_report_information(options)
        self.assertEqual(
            report_information['warnings'],
            {
                'account_reports.sales_report_warning_non_ec_country': {'alert_type': 'warning'},
                'account_reports.sales_report_warning_same_country': {'alert_type': 'warning'},
            }
        )

    def test_ec_sales_report_warnings_delivery_address(self):
        """ Ensure warnings are generated if their conditions are met on delivery address """
        partner = self.env['res.partner'].create([{
            'name': 'Partner',
            'vat': '12345678',
            'country_id': self.company_data['company'].country_id.id,
        }])

        delivery_address_no_ec_sales_list = self.env['res.partner'].create([{
            'name': 'Delivery Address',
            'country_id': self.env.ref('base.je').id,
            'type': 'delivery',
            'parent_id': partner.id,
        }])

        delivery_address_same_country = self.env['res.partner'].create([{
            'name': 'Delivery Address',
            'country_id': partner.country_id.id,
            'type': 'delivery',
            'parent_id': partner.id,
        }])

        self._create_invoices([
            (partner, self.goods_tax[:1], 100, delivery_address_no_ec_sales_list),
            (partner, self.goods_tax[:1], 100, delivery_address_same_country),
        ])

        options = self._generate_ec_sales_report_options(self.report_groupby_partner, '2019-12-01', '2019-12-31')
        report_information = self.report_groupby_partner.get_report_information(options)
        self.assertEqual(
            report_information['warnings'],
            {
                'account_reports.sales_report_warning_non_ec_country': {'alert_type': 'warning'},
                'account_reports.sales_report_warning_same_country': {'alert_type': 'warning'},
            }
        )
