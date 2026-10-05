# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.tests import tagged
from odoo.addons.point_of_sale.tests.test_order_receipt import TestPosOrderReceipt
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestOrderReceiptL10n(TestPosOrderReceipt):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountTestInvoicingCommon.setup_country('de')
    def setUpClass(self):
        super().setUpClass()

    def test_receipt_data(self):
        super().test_receipt_data()
