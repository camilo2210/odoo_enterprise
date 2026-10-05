from odoo import Command
from odoo.tests import tagged

from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestNLIntrastatReport(TestAccountReportsCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestAccountReportsCommon.setup_country('nl')
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env.ref('account_intrastat.intrastat_report')
        cls.report_handler = cls.env['account.intrastat.goods.report.handler']
        cls.company_data['company'].vat = 'NL123456782B90'
        cls.belgian_customer = cls.env['res.partner'].create({
            'name': 'Belgian Customer',
            'country_id': cls.env.ref('base.be').id,
            'vat': 'BE0477472701',
        })
        cls.product_a.write({
            'intrastat_code_id': cls.env.ref('account_intrastat.commodity_code_2018_94031051').id,
            'intrastat_supplementary_unit_amount': 1,
            'intrastat_origin_country_id': cls.env.ref('base.be').id,
            'weight': 2,
        })

    def create_account_move(self, post=False, **kwargs):
        invoice = self.env['account.move'].create({
            'date': '2023-10-25',
            'invoice_date': '2023-10-25',
            'company_id': self.company_data['company'].id,
            'invoice_line_ids': [
                Command.create({
                    'intrastat_product_origin_country_id': self.env.ref('base.be').id,
                    'product_uom_id': self.env.ref('uom.product_uom_unit').id,
                    'product_id': self.product_a.id,
                    'intrastat_transaction_id': self.env.ref('account_intrastat.account_intrastat_transaction_11').id,
                    'quantity': 4,
                    'price_unit': 10000,
                })
            ],
            **kwargs,
        })

        if post:
            invoice.action_post()

        return invoice

    def test_cbs_export(self):
        """ Test the Intrastat csv export to be sent to CBS """
        self.create_account_move(move_type='out_invoice', partner_id=self.belgian_customer.id, post=True)
        self.create_account_move(move_type='in_invoice', partner_id=self.belgian_customer.id, post=True)
        options = self._generate_options(self.report, '2023-10-01', '2023-10-31')
        csv_file = self.report_handler.l10n_nl_export_to_csv(options)['file_content']
        expected_csv = """9801123456782B90202310company_1_data                                18.0 20260430111813                            
2023107123456782B9000001BE BE 300000 9403105100+0000000032++00000000000000040000+00000000002023/00001    000       11BE0477472701     
2023106123456782B9000002   BE 300000 9403105100+0000000032++00000000000000040000+000000000023/10/0001    000       11BE0477472701     
9899                                                                                                               """  # noqa: W291
        # We don't take the first line, as it contains the Odoo version, it will break on each fwp
        for csv_line, expected_csv_line in zip(csv_file.split('\n')[1:], expected_csv.split('\n')[1:]):
            self.assertEqual(csv_line, expected_csv_line)
