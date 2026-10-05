from datetime import date

from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from odoo.tests import tagged


@tagged("post_install_l10n", "post_install", "-at_install")
class TestL10nRoD300Report(TestAccountReportsCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestAccountReportsCommon.setup_country("ro")
    def setUpClass(cls):
        super().setUpClass()
        cls.company.update({
            "vat": "RO1234567897",
            "street": "Str. Victoriei 1",
            "city": "Bucharest",
            "zip": "010001",
            "email": "companyRO@test.com",
            "country_id": cls.env.ref("base.ro").id,
        })
        cls.handler = cls.env["l10n_ro.d300.report.handler"]

    def test_compute_payment_record_number(self):
        """Covers format/checksum (monthly), period prefix (quarterly), and year rollover (December)."""
        cases = [
            (date(2025, 8, 31), "L", "10301010825250925000044"),
            (date(2025, 8, 31), "T", "10302010825250925000045"),
            (date(2025, 12, 31), "L", "10301011225250126000032"),
        ]
        for dt, period, expected in cases:
            with self.subTest(dt=dt, period=period):
                self.assertEqual(self.handler._compute_payment_record_number(dt, period), expected)
