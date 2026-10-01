# Part of Odoo. See LICENSE file for full copyright and licensing details.
from contextlib import contextmanager
from unittest import mock
from unittest.mock import patch

from odoo.addons.account_avatax.lib.avatax_client import AvataxClient
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.tests import freeze_time, tagged
from odoo.tools import file_open
from odoo.tools.safe_eval import json


@freeze_time("2025-03-17T19:02:13+00:00")
@tagged("post_install_l10n", "post_install", "-at_install")
class TestUi(TestPointOfSaleHttpCommon):
    @contextmanager
    def _with_mocked_create_transaction(self, expected_communications):
        """Checks that we send the right requests and returns corresponding mocked responses. Heavily inspired by
        patch_session in l10n_ke_edi_oscu."""
        self.maxDiff = None
        test_case = self
        json_module = json
        expected_communications = iter(expected_communications)

        def mocked_request(self, iap_endpoint, method, endpoint, params=None, json=None, **kwargs):

            def replace_ignore(dict_to_replace):
                """Replace `___ignore___` in the expected request JSONs by unittest.mock.ANY,
                which is equal to everything."""
                for k, v in dict_to_replace.items():
                    if v == "___ignore___":
                        dict_to_replace[k] = mock.ANY
                return dict_to_replace

            expected_method, expected_endpoint, expected_params, request_filename, response_filename = next(
                expected_communications
            )
            test_case.assertEqual(method, expected_method)
            test_case.assertEqual(endpoint, expected_endpoint)
            test_case.assertEqual(params, expected_params)

            with file_open(f"pos_avatax/tests/mocked_requests/{request_filename}.json", "r") as request_file:
                expected_request = json_module.loads(request_file.read(), object_hook=replace_ignore)
                test_case.assertEqual(
                    json,
                    expected_request,
                    f"Expected request did not match actual request for {endpoint}.",
                )

            with file_open(f"pos_avatax/tests/mocked_responses/{response_filename}.json", "r") as response_file:
                api_response = json_module.loads(response_file.read())

                if expected_endpoint == "transactions/createoradjust":
                    sent_lines = json["createTransactionModel"]["lines"]
                    expected_lines = api_response["lines"]

                    # Set the line IDs in the mocked response to the line IDs of this order.
                    for sent_line, received_line in zip(sent_lines, expected_lines, strict=True):
                        received_line["lineNumber"] = sent_line["number"]

                return api_response

        with patch(
            f"{AvataxClient.__module__}.AvataxClient._dispatch",
            autospec=True,
            side_effect=mocked_request,
        ):
            yield

        if next(expected_communications, None):
            self.fail("Not all expected calls were made!")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.main_pos_config.module_pos_avatax = True
        cls.company.write(
            {
                "avalara_api_id": "DUMMY",
                "avalara_api_key": "DUMMY",
                "avalara_connection_method": "manual",
                "street": "250 Executive Park Blvd",
                "city": "San Francisco",
                "state_id": cls.env.ref("base.state_us_5").id,
                "country_id": cls.env.ref("base.us").id,
                "zip": "94134",
            }
        )
        cls.company.partner_id.avalara_partner_code = "TEST CODE"
        cls.wall_shelf.avatax_category_id = cls.env.ref("account_avatax.D0000000")

    def test_01_order(self):
        # Tax returned by Avatax won't always match what Odoo calculates (maybe rounding is different, maybe there's some
        # exemption, ...). This tax is deliberately configured differently from what Avatax returns to test this case.
        self.env["account.tax"].create(
            {
                "name": "CA STATE 6%",
                "amount": 1.0,
                "tax_group_id": self.env["account.tax.group"].create({"name": "CA STATE"}).id,
            }
        )

        self.main_pos_config.with_user(self.pos_user).open_ui()
        amount_of_requests = 2
        expected_communications = [("POST", "transactions/createoradjust", "Lines", "request", "response")] * amount_of_requests
        with self._with_mocked_create_transaction(expected_communications):
            self.start_tour(
                "/pos/ui?config_id=%d" % self.main_pos_config.id,
                "pos_avatax.tour_order",
                login=self.env.user.login,
            )
