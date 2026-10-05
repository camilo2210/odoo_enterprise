# Part of Odoo. See LICENSE file for full copyright and licensing details.
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.point_of_sale.tests.test_order_receipt import TestPosOrderReceipt
from odoo.addons.pos_urban_piper.tests.common import CommonPosUrbanPiperTest


@tagged('post_install', '-at_install')
class TestOrderReceiptUp(CommonPosUrbanPiperTest, TestPosOrderReceipt):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(self):
        super().setUpClass()
        company = self.company_data['company']
        company.vat = 'SE123456789701'
        company.partner_id.additional_identifiers = {'SE_EN': '555555-5555'}

        self.key_to_skip['extra_data'].append('cashier_name')
        self.key_to_skip['pos.order'].append('user_id')

    def test_receipt_data_urban_piper(self):
        self.urban_piper_config.open_ui()
        self.create_urbanpiper_order(qty=4, delivery_instruction='Make it spicy..')
        data = {
            'frontend_data': None,
            'backend_data': None,
        }

        def get_order_frontend_receipt_data(self, frontend_data):
            backend_data = self.order_receipt_generate_data()
            data['frontend_data'] = frontend_data
            data['backend_data'] = backend_data

        with patch.object(self.env.registry['pos.order'], 'get_order_frontend_receipt_data', get_order_frontend_receipt_data, create=True):
            self.start_pos_tour("test_receipt_data_urban_piper", pos_config=self.urban_piper_config, login="pos_admin")
            self.compare_receipt_data(data['frontend_data'], data['backend_data'])
