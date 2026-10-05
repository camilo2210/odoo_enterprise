from freezegun import freeze_time

from . import common


class TestHolidayAttestAllocation(common.TestPayrollAccountCommon):
    @classmethod
    @freeze_time('2025-12-30 09:00:00')
    def setUpClass(cls):
        super().setUpClass()

    def test_holiday_attest_allocation(self):
        with freeze_time("2025-12-30"):
            self.start_tour("/odoo", 'holiday_attest_allocation', login='admin')
