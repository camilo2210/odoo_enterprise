# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.tests import tagged
from odoo.addons.point_of_sale.tests.test_order_receipt import TestPosOrderReceipt
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestOrderReceiptL10n(TestPosOrderReceipt):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountTestInvoicingCommon.setup_country('cl')
    def setUpClass(self):
        super().setUpClass()
        self.main_pos_config.company_id.name = 'Company CL'
        self.main_pos_config.company_id.country_id = self.env.ref('base.cl')
        self.main_pos_config.company_id.vat = '76086428-5'
        self.main_pos_config.company_id.l10n_cl_dte_resolution_number = '1234'
        self.main_pos_config.company_id.l10n_cl_dte_resolution_date = '2020-01-01'

    def test_receipt_data(self):
        super().test_receipt_data()
