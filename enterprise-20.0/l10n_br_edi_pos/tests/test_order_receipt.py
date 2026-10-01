# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.tests import tagged
from odoo.addons.point_of_sale.tests.test_order_receipt import TestPosOrderReceipt
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.l10n_br_edi_pos.tests.test_l10n_br_edi_pos import TestL10nBREDIPOSCommon


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestOrderReceiptL10n(TestPosOrderReceipt, TestL10nBREDIPOSCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountTestInvoicingCommon.setup_country('br')
    def setUpClass(self):
        super().setUpClass()
        self.main_pos_config.write(
            {
                "l10n_br_is_nfce": True,
                "l10n_br_invoice_serial": "1",
            }
        )
        self.main_pos_config.company_id.write({
            "name": "Company BR"
        })
        self.example_simple_product.taxes_id = False

    def test_receipt_data(self):
        super().test_receipt_data()
