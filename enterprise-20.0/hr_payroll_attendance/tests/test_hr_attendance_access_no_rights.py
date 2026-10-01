from odoo.tests import HttpCase, tagged
from odoo import Command

from datetime import datetime


@tagged("post_install", "-at_install")
class TestAttendanceAccessNoPayroll(HttpCase):
    """
    test: a basic employee (no payroll rights) must be able to
    access attendance views via the Monthly Hours smart button on the
    employee form or the app without hitting an access error.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create a basic internal user with only Employee rights — no payroll Only he can see his own attendances and has default employee right over timeOff
        cls.basic_user = cls.env["res.users"].create({
            "name": "test_user",
            "login": "test_user",
            "password": "testD12322y/",
            "group_ids": [Command.link(cls.env.ref("base.group_user").id),
                          Command.link(cls.env.ref("hr_attendance.group_hr_attendance_own").id),
                          Command.link(cls.env.ref("hr_holidays.group_hr_holidays_employee").id)]
        })

        cls.employee = cls.env["hr.employee"].create({
            "name": 'test_employee',
            "contract_date_start": "2026-01-01",
            "user_id": cls.basic_user.id,
        })

        # Create some attendance records so views have data to render
        cls.env["hr.attendance"].create([
            {
                "employee_id": cls.employee.id,
                "check_in": datetime.today().replace(day=1, hour=8, minute=0),
                "check_out": datetime.today().replace(day=1, hour=17, minute=0),
            },
            {
                "employee_id": cls.employee.id,
                "check_in": datetime.today().replace(day=8, hour=8, minute=30),
                "check_out": datetime.today().replace(day=8, hour=16, minute=30),
            },
        ])

    def test_attendance_access_without_payroll_rights(self):
        self.start_tour(
            "/odoo",
            "test_attendance_access_no_payroll_rights",
            login="test_user",
        )
