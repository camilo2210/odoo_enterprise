from collections.abc import Mapping, Sequence
import json

from odoo.addons.l10n_in.tests.common import L10nInTestInvoicingCommon
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from odoo.tools import file_open


class L10nInTestAccountReportsCommon(TestAccountReportsCommon, L10nInTestInvoicingCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # === Companies === #
        cls.default_company.write({'l10n_in_gst_efiling_feature': True})
        cls.user.company_ids = [cls.default_company.id, cls.company_data_2['company'].id]

        # === Taxes === #
        cls.comp_igst_18 = cls.env['account.chart.template'].ref('igst_sale_18')

    @classmethod
    def _read_mock_json(self, filename):
        """
        Reads a JSON file using Odoo's file_open and returns the parsed data.

        :param filename: The name of the JSON file to read.
        :return: Parsed JSON data.
        """
        # Use file_open to open the file from the module's directory
        with file_open(f"{self.test_module}/tests/mock_jsons/{filename}", 'rb') as file:
            data = json.load(file)

        return data

    def comparable_dict(cls, d: Mapping) -> Mapping:
        """
        Recursively sorts lists in a dictionary to make it comparable regardless of order.
        :param d: The dictionary to normalize.
        :return: A new dictionary with sorted lists.
        """
        def normalize(value):
            if isinstance(value, Mapping):
                return {
                    key: normalize(val)
                    for key, val in value.items()
                }
            if isinstance(value, Sequence) and not isinstance(
                value, (str, bytes, bytearray)
            ):
                values = [normalize(item) for item in value]
                return sorted(values, key=lambda item: json.dumps(
                    item, sort_keys=True, separators=(",", ":")
                ))
            return value
        return normalize(d)

    def compare_dict_ignoring_list_order(self, dict1, dict2):
        """
        Compare two dictionaries while ignoring the order of lists within them.
        """
        normalized_dict1 = self.comparable_dict(dict1)
        normalized_dict2 = self.comparable_dict(dict2)
        return self.assertDictEqual(normalized_dict1, normalized_dict2)
