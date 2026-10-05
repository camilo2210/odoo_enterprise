# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.tests import tagged
from odoo.fields import Command
from odoo.addons.point_of_sale.tests.test_order_receipt import TestPosOrderReceipt
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestOrderReceiptL10n(TestPosOrderReceipt):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountTestInvoicingCommon.setup_country('ke')
    def setUpClass(self):
        super().setUpClass()
        self.example_simple_product.write({
            'l10n_ke_product_type_code': '2',
            'l10n_ke_packaging_unit_id': self.env['l10n_ke_edi_oscu.code'].search([('code', '=', 'BA')], limit=1).id,
            'unspsc_code_id': self.env['product.unspsc.code'].search([
                ('code', '=', '52161557'),
            ], limit=1).id,
            'l10n_ke_origin_country_id': self.env.ref('base.be').id,
            'l10n_ke_packaging_quantity': 2,
            'standard_price': 10.0,
            'taxes_id': [Command.link(self.tax_sale_a.id)]
        })
        self.key_to_skip['prices'].append('discount_amount')  # Computed in backend, not present in frontend data

    def test_receipt_data(self):
        super().test_receipt_data()
