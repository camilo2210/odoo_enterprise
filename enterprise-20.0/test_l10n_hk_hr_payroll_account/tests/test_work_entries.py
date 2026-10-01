# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date

from freezegun import freeze_time

from odoo.tests import tagged

from .common import TestL10NHkHrPayrollAccountCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestWorkEntries(TestL10NHkHrPayrollAccountCommon):

    _test_user_groups = None  # FIXME list needed groups

    @freeze_time('2026-01-31')
    def test_monthly_entries(self):
        """ Simple test generating work entries for Jan 2026 for the basic HK schedule (40h & weekend work entries) """
        # Rest once to be sure.
        from_date, to_date = date(2026, 1, 1), date(2026, 1, 31)
        work_entries_vals = self.employee.version_ids.generate_work_entries(from_date, to_date)
        self.assertSetEqual(
            {(vals['date'], vals['work_entry_type_id'].code) for vals in work_entries_vals},
            {
                (date(2026, 1, 1), "002.00"),
                (date(2026, 1, 2), "002.00"),
                (date(2026, 1, 3), "HKLEAVE600"),
                (date(2026, 1, 4), "HKLEAVE600"),
                (date(2026, 1, 5), "002.00"),
                (date(2026, 1, 6), "002.00"),
                (date(2026, 1, 7), "002.00"),
                (date(2026, 1, 8), "002.00"),
                (date(2026, 1, 9), "002.00"),
                (date(2026, 1, 10), "HKLEAVE600"),
                (date(2026, 1, 11), "HKLEAVE600"),
                (date(2026, 1, 12), "002.00"),
                (date(2026, 1, 13), "002.00"),
                (date(2026, 1, 14), "002.00"),
                (date(2026, 1, 15), "002.00"),
                (date(2026, 1, 16), "002.00"),
                (date(2026, 1, 17), "HKLEAVE600"),
                (date(2026, 1, 18), "HKLEAVE600"),
                (date(2026, 1, 19), "002.00"),
                (date(2026, 1, 20), "002.00"),
                (date(2026, 1, 21), "002.00"),
                (date(2026, 1, 22), "002.00"),
                (date(2026, 1, 23), "002.00"),
                (date(2026, 1, 24), "HKLEAVE600"),
                (date(2026, 1, 25), "HKLEAVE600"),
                (date(2026, 1, 26), "002.00"),
                (date(2026, 1, 27), "002.00"),
                (date(2026, 1, 28), "002.00"),
                (date(2026, 1, 29), "002.00"),
                (date(2026, 1, 30), "002.00"),
                (date(2026, 1, 31), "HKLEAVE600"),
            },
        )
