from odoo.fields import Command

from odoo.addons.iot.tests.common import IotCommonTest
from odoo.addons.pos_self_order.tests.self_order_common_test import SelfOrderCommonTest


class TestSelfOrderIoTKiosk(IotCommonTest, SelfOrderCommonTest):
    def setUp(self):
        super().setUp()
        self.iot_websocket_messages = []
        self.pos_config.write(
            {
                "self_ordering_mode": "kiosk",
                "self_ordering_pay_after": "each",
                "self_ordering_service_mode": "counter",
                "payment_method_ids": [(4, self.bank_payment_method.id)],
                "available_preset_ids": [(5, 0)],
            },
        )
        self.pos_config.default_preset_id.service_at = "counter"

    def test_kiosk_receipt_printer(self):
        receipt_printer = self.env["pos.printer"].create({
            "name": "IoT Printer",
            "printer_type": "iot",
            "iot_device_id": self.iot_receipt_printer.id,
            "use_type": "receipt",
        })
        self.pos_config.write({
            "use_iot_box": True,
            "iot_printer_id": self.iot_receipt_printer.id,
            "receipt_printer_ids": [Command.set([receipt_printer.id])],
        })
        self.pos_config.with_user(self.pos_user).open_ui()
        self.pos_config.current_session_id.set_opening_control(0, "")
        self_route = self.pos_config._get_self_order_route()

        self.start_iot_tour(self_route, "self_order_kiosk_iot_printer")

    def test_iot_payment_terminal(self):
        if not self.env['ir.module.module'].search([
            ('name', '=', 'pos_iot_worldline'),
            ('state', '=', 'installed'),
        ]):
            # There is no pos_self_order_iot_worldline module, so we
            # only run in batches with all modules are installed.
            self.skipTest('pos_iot_worldline is not installed')

        worldline_payment_method = self.env['pos.payment.method'].create({
            "name": "Worldline",
            'type': 'bank',
            'journal_id': self.bank_journal.id,
            "payment_provider": "worldline",
            "iot_device_id": self.iot_payment_terminal.id,
        })
        self.pos_config.write({
            "use_iot_box": False,
            "payment_method_ids": [(4, worldline_payment_method.id)],
        })
        self.pos_config.with_user(self.pos_user).open_ui()
        self.pos_config.current_session_id.set_opening_control(0, "")
        self_route = self.pos_config._get_self_order_route()
        self.start_tour(self_route, "self_order_kiosk_iot_worldline")
