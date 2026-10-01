# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.planning.tests.common import TestCommonPlanning


class TestPlanningAttendanceCommon(TestCommonPlanning):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setUpEmployees()
        cls.setUpDates()

        cls.env.user.tz = 'Europe/Brussels'
        cls.calendar, cls.flexible_calendar = cls.env['resource.calendar'].create([{
            'name': 'Calendar',
        }, {
            'name': 'Flex Calendar',
            'hours_per_day': 8,
            'hours_per_week': 40,
            'full_time_required_hours': 40,
            'attendance_ids': [],
        }])
        cls.flexible_employee = cls.env['hr.employee'].create({
            'name': 'Flexible Employee',
            'work_email': 'flex@a.be',
            'tz': 'UTC',
            'create_date': '2015-01-01 00:00:00',
            'resource_calendar_id': cls.flexible_calendar.id,
        })
        cls.flex_role = cls.env['planning.role'].create({'name': 'flex role'})
