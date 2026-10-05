from odoo.tests import tagged
from odoo.addons.point_of_sale.tests.test_order_receipt import TestPosOrderReceipt


@tagged("post_install", "-at_install", "post_install_l10n")
class TestOrderReceiptL10n(TestPosOrderReceipt):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(self):
        super().setUpClass()

        self.iot_box = self.env["iot.box"].sudo().create({
            "name": "IoT Box",
            "identifier": "TestIot"
        })
        self.iot_scale = self.env["iot.device"].sudo().create({
            "name": "Scale",
            "iot_id": self.iot_box.id,
            "type": "scale",
        })
        self.main_pos_config.iot_scale_id = self.iot_scale

    def test_receipt_data(self):
        super().test_receipt_data()
