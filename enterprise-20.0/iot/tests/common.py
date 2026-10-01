import logging

from odoo.tests import HttpCase

from odoo.addons.iot.models.iot_channel import IotChannel

_logger = logging.getLogger(__name__)


class IotCommonTest(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.shop_iot_box = (
            cls.env["iot.box"]
            .sudo()
            .create(
                {
                    "name": "Test Shop",
                    "identifier": "test_iot_box",
                    "ip": "127.0.0.1:8069",
                    "version": "L25.07",
                },
            )
        )

        cls.iot_receipt_printer = (
            cls.env["iot.device"]
            .sudo()
            .create(
                {
                    "name": "Receipt Printer",
                    "identifier": "printer_identifier",
                    "iot_id": cls.shop_iot_box.id,
                    "type": "printer",
                    "connection": "network",
                    "connected_status": "connected",
                },
            )
        )

        cls.iot_payment_terminal = (
            cls.env["iot.device"]
            .sudo()
            .create(
                {
                    "name": "Payment Terminal",
                    "identifier": "payment_terminal_identifier",
                    "iot_id": cls.shop_iot_box.id,
                    "type": "payment",
                    "connection": "network",
                    "connected_status": "connected",
                },
            )
        )

    def setUp(self):
        super().setUp()
        self.iot_websocket_messages = []
        self.expected_ws_result = {}
        original_send_message = IotChannel.send_message

        def mock_send_message(iot_channel_record, message, message_type="iot_action"):
            self.iot_websocket_messages.append({message_type: message})
            if message_type == "iot_action":
                return original_send_message(
                    iot_channel_record,
                    {
                        'session_id': message['session_id'],
                        'iot_box_identifier': message['iot_identifier'],
                        'device_identifier': message['device_identifier'],
                        'message': {
                            'status': 'success',
                            'message': '',
                            'result': self.expected_ws_result,
                        },
                    },
                    message_type='operation_confirmation',
                )
            return original_send_message(iot_channel_record, message, message_type)

        def mock_get_iot_channel(_iot_channel_record):
            return "mock_iot_channel"

        mock_get_iot_channel._api_model = True
        mock_send_message._api_model = True

        self.patch(IotChannel, "send_message", mock_send_message)
        self.patch(IotChannel, "get_iot_channel", mock_get_iot_channel)

    def start_iot_tour(
        self,
        url_path: str,
        tour_name: str,
        login="admin",
        expected_ws_msg_types: list | None = None,
        **kwargs,
    ):
        """Helper method to start a tour with the IoT mocks in place.

        First starts the tour considering local network works fine,
        then restart the tour making every network call fail to
        allow testing WebSocket fallback.

        :param url_path: the path to open to start the tour, e.g. "/odoo/iot"
        :param tour_name: the name of the tour to start
        :param login: the user to log in as before starting the tour
        :param expected_ws_msg_types: If set, we will assert that the given list of messages types is exactly
                            the one sent through the WebSocket channel when the local network is down.
        :param kwargs: Keyword arguments forwarded to start_tour
        """
        _logger.info("Starting IoT tour with working local network (Longpolling)...")
        self.start_tour(url_path, tour_name, login=login, cookies={"iot_test": "lp"}, **kwargs)

        self.iot_websocket_messages = []
        _logger.info("Starting IoT tour with broken local network (WebSocket)...")
        self.start_tour(url_path, tour_name, login=login, cookies={"iot_test": "ws"}, **kwargs)

        if expected_ws_msg_types is None:
            expected_ws_msg_types = ["iot_action"]

        actual_message_types = [
            next(iter(msg.keys())) for msg in self.iot_websocket_messages
        ]
        self.assertEqual(
            len(self.iot_websocket_messages),
            len(expected_ws_msg_types),
            (
                "`iot.channel.send_message` should be called exactly %s times: "
                "This time, we received %s"
                % (len(expected_ws_msg_types), actual_message_types)
            ),
        )
        for expected_message_type, actual_message_type in zip(
            expected_ws_msg_types,
            actual_message_types,
        ):
            self.assertEqual(expected_message_type, actual_message_type)
