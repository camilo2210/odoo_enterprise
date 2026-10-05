from datetime import datetime

from odoo.tests import freeze_time
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPlanningFieldServiceHrAttendanceFlowWithGeolocation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env['res.users'].create({
            'name': "Test User",
            'login': "test",
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        cls.employee = cls.env['hr.employee'].create({
            'name': "Test Employee",
            'user_id': cls.user.id,
            'company_id': cls.env.company.id,
            'resource_calendar_id': cls.env.company.resource_calendar_id.id,
        })

    @freeze_time("2024-02-01 23:00:00")
    def test_cron_auto_check_out(self):
        """ Check that auto checked out users have their live geolocation reset """
        self.env.company.write({
            'auto_check_out': 1,
            'auto_check_out_tolerance': 1,
        })
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2024, 2, 1, 8, 0),
        })
        self.employee.resource_id.write({
            "live_latitude": 10.0,
            "live_longitude": 10.0,
            "live_location_last_update": datetime.now(),
        })
        self.env["hr.attendance"]._cron_auto_check_out()
        self.assertFalse(self.employee.resource_id.live_latitude)
        self.assertFalse(self.employee.resource_id.live_longitude)
        self.assertFalse(self.employee.resource_id.live_location_last_update)
