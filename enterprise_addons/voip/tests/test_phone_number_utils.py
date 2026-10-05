from odoo.tests import TransactionCase, tagged

from odoo.addons.voip.models.utils import extract_country_code


@tagged("voip", "post_install", "-at_install")
class TestPhoneNumberUtils(TransactionCase):
    def test_extract_country_code_handles_00_prefix_for_shared_country_code(self):
        # "00" is the international call prefix, equivalent to "+". A +1 number
        # must resolve its region from the national number (650 → US) instead of
        # being dropped as an ambiguous shared country code.
        self.assertEqual(extract_country_code("0016504193846"), {"iso": "us", "itu": "1"})

    def test_extract_country_code_plus_prefix_still_resolves(self):
        self.assertEqual(extract_country_code("+32478557788"), {"iso": "be", "itu": "32"})

    def test_extract_country_code_national_number_yields_no_country(self):
        # A purely national number (single "0" trunk prefix, no international
        # prefix) must not be guessed into a country.
        self.assertEqual(extract_country_code("0478557788"), {"iso": "", "itu": ""})

    def test_extract_country_code_double_zero_not_followed_by_country_code(self):
        # "00" followed by "0" is not an international prefix; do not turn it into
        # an invalid "+0…" and do not resolve a country.
        self.assertEqual(extract_country_code("000478557788"), {"iso": "", "itu": ""})

    def test_extract_country_code_only_leading_double_zero_is_normalized(self):
        # A "00" that is not at the start must be left untouched.
        self.assertEqual(extract_country_code("3200478557788"), {"iso": "", "itu": ""})
