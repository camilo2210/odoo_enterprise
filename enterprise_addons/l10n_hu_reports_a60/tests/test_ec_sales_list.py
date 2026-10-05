from freezegun import freeze_time

from odoo.tests import Command, tagged

from odoo.addons.account_reports.tests.account_sales_report_common import AccountSalesReportCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class L10n_HuEcSalesListTests(AccountSalesReportCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountSalesReportCommon.setup_country('hu')
    def setUpClass(cls):
        super().setUpClass()
        cls.sale_g_tax = cls.env['account.tax'].search([('name', '=', '0% EU G'), ('company_id', '=', cls.env.company.id), ('type_tax_use', '=', 'sale')], limit=1)
        cls.sale_s_tax = cls.env['account.tax'].search([('name', '=', '0% EU S'), ('company_id', '=', cls.env.company.id), ('type_tax_use', '=', 'sale')], limit=1)
        cls.sale_gb_tax = cls.env['account.tax'].search([('name', '=', '0% EU GB'), ('company_id', '=', cls.env.company.id), ('type_tax_use', '=', 'sale')], limit=1)
        cls.purchase_s_tax = cls.env['account.tax'].search([('name', '=', '27% EU S'), ('company_id', '=', cls.env.company.id), ('type_tax_use', '=', 'purchase')], limit=1)
        cls.purchase_gk_tax = cls.env['account.tax'].search([('name', '=', '27% EU GK'), ('company_id', '=', cls.env.company.id), ('type_tax_use', '=', 'purchase')], limit=1)
        cls.a60_report_page1 = cls.env.ref('l10n_hu_reports_a60.l10n_hu_a60_page_1')
        cls.a60_report_page2 = cls.env.ref('l10n_hu_reports_a60.l10n_hu_a60_page_2')
        cls.a60_report_page3 = cls.env.ref('l10n_hu_reports_a60.l10n_hu_a60_page_3')
        cls.a60_report_page4 = cls.env.ref('l10n_hu_reports_a60.l10n_hu_a60_page_4')
        invoice_datas = [
            {'partner_id': cls.partner_b.id, 'move_type': 'out_invoice', 'tax_ids': [cls.sale_g_tax.id]},
            {'partner_id': cls.partner_a.id, 'move_type': 'out_invoice', 'tax_ids': [cls.sale_g_tax.id]},
            {'partner_id': cls.partner_a.id, 'move_type': 'out_invoice', 'tax_ids': [cls.sale_gb_tax.id]},
            {'partner_id': cls.partner_a.id, 'move_type': 'out_invoice', 'tax_ids': [cls.sale_s_tax.id]},
            {'partner_id': cls.partner_a.id, 'move_type': 'in_invoice', 'tax_ids': [cls.purchase_s_tax.id]},
            {'partner_id': cls.partner_a.id, 'move_type': 'in_invoice', 'tax_ids': [cls.purchase_gk_tax.id]},
        ]

        for data in invoice_datas:
            cls.env['account.move'].create([{
                'partner_id': data['partner_id'],
                'move_type': data['move_type'],
                'date': '2024-12-25',
                'invoice_date': '2024-12-25',
                'invoice_line_ids': [
                    Command.create({
                        'price_unit': 200,
                        'quantity': 20,
                        'tax_ids': data['tax_ids'],
                    }),
                ],
            }]).action_post()

    @freeze_time('2024-12-31')
    def test_a60_page_1(self):
        options = self.a60_report_page1.get_options({'date': {'default_opening_date': 'this_month'}})
        lines = self.a60_report_page1._get_lines(options)
        self.assertLinesValues(
            lines,
            # pylint: disable=C0326
            #   Partner                country code,            VAT Number,          Transaction Type         Amount
            [                      0,                       1,                       2,       3,                  4],
            [
                (  'EC Sales Report',                      '',                      '',      '',            12000.0),
                (self.partner_a.name,  self.partner_a.vat[:2],  self.partner_a.vat[2:],      '',             4000.0),
                (self.partner_a.name,  self.partner_a.vat[:2],  self.partner_a.vat[2:],     'B',             4000.0),
                (self.partner_b.name,  self.partner_b.vat[:2],  self.partner_b.vat[2:],      '',             4000.0),
            ],
            options,
        )

    @freeze_time('2024-12-31')
    def test_a60_page_2(self):
        options = self.a60_report_page2.get_options({'date': {'default_opening_date': 'this_month'}})
        lines = self.a60_report_page2._get_lines(options)
        self.assertLinesValues(
            lines,
            # pylint: disable=C0326
            #   Partner                country code,            VAT Number,          Transaction Type         Amount
            [                      0,                       1,                       2,       3,                  4],
            [
                (  'EC Sales Report',                      '',                      '',      '',             4000.0),
                (self.partner_a.name,  self.partner_a.vat[:2],  self.partner_a.vat[2:],     'K',             4000.0),
            ],
            options,
        )

    @freeze_time('2024-12-31')
    def test_a60_page_3(self):
        options = self.a60_report_page3.get_options({'date': {'default_opening_date': 'this_month'}})
        lines = self.a60_report_page3._get_lines(options)
        self.assertLinesValues(
            lines,
            # pylint: disable=C0326
            #   Partner                country code,            VAT Number,                 Amount
            [                      0,                       1,                       2,          3],
            [
                (  'EC Sales Report',                      '',                      '',     4000.0),
                (self.partner_a.name,  self.partner_a.vat[:2],  self.partner_a.vat[2:],     4000.0),
            ],
            options,
        )

    @freeze_time('2024-12-31')
    def test_a60_page_4(self):
        options = self.a60_report_page4.get_options({'date': {'default_opening_date': 'this_month'}})
        lines = self.a60_report_page4._get_lines(options)
        self.assertLinesValues(
            lines,
            # pylint: disable=C0326
            #   Partner                country code,            VAT Number,                 Amount
            [                      0,                       1,                       2,          3],
            [
                (  'EC Sales Report',                      '',                      '',     4000.0),
                (self.partner_a.name,  self.partner_a.vat[:2],  self.partner_a.vat[2:],     4000.0),
            ],
            options,
        )
