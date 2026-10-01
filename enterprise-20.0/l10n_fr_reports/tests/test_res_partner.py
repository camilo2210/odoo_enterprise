from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'post_install_l10n')
class ResPartnerTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env["res.partner"]

    def test_split_french_street_supported_patterns(self):
        test_cases = [
            ("12B Rue de la Paix", ("Rue de la Paix", "12", "B")),
            ("Avenue des Champs-Élysées 55", ("Avenue des Champs-Élysées", "55", False)),
            ("3 ter Boulevard Saint-Michel", ("Boulevard Saint-Michel", "3", "T")),
            ("5 bis Rue du Faubourg Saint-Honoré", ("Rue du Faubourg Saint-Honoré", "5", "B")),
            ("15BIS Avenue Victor Hugo", ("Avenue Victor Hugo", "15", "B")),
            ("20C Boulevard Haussmann", ("Boulevard Haussmann", "20", "C")),
            ("Rue de la Paix 12B", ("Rue de la Paix", "12", "B")),
        ]

        for street, expected in test_cases:
            with self.subTest(street=street):
                self.assertEqual(self.Partner._split_french_street(street), expected)

    def test_split_french_street_empty_values(self):
        self.assertEqual(self.Partner._split_french_street(""), (False, False, False))
        self.assertEqual(self.Partner._split_french_street(None), (False, False, False))
        self.assertEqual(self.Partner._split_french_street("   "), (False, False, False))

    def test_parse_address_parts_normalizes_suffix(self):
        self.assertEqual(self.Partner._parse_address_parts("bis", "Rue X", is_start=True), ("B", "Rue X"))
        self.assertEqual(self.Partner._parse_address_parts("TER.", "Rue X", is_start=True), ("T", "Rue X"))
        self.assertEqual(self.Partner._parse_address_parts("quater;", "Rue X", is_start=True), ("Q", "Rue X"))
        self.assertEqual(self.Partner._parse_address_parts("c:", "Rue X", is_start=True), ("C", "Rue X"))

    def test_parse_address_parts_unknown_suffix_kept_in_street(self):
        self.assertEqual(self.Partner._parse_address_parts("XYZ", "Rue X", is_start=True), ("", "XYZ Rue X"))
        self.assertEqual(self.Partner._parse_address_parts("XYZ", "Rue X", is_start=False), ("", "Rue X XYZ"))
