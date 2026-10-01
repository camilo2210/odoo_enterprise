# Part of Odoo. See LICENSE file for full copyright and licensing details
from datetime import datetime
from dateutil.relativedelta import relativedelta
from dateutil.rrule import MO

from odoo.tests.common import TransactionCase, HttpCase

from odoo.addons.mail.tests.common import mail_new_test_user


class TestCommonPlanning(TransactionCase):
    def get_by_employee(self, employee):
        return self.env['planning.slot'].search([('employee_ids', 'in', employee.id)])

    @classmethod
    def setUpEmployees(cls):
        cls.env.user.tz = "Europe/Brussels"

        cls.env.company.resource_calendar_id = cls.env['resource.calendar'].create({
            'attendance_ids': [
                (0, 0,
                    {
                        'dayofweek': weekday,
                        'hour_from': hour,
                        'hour_to': hour + 4,
                    })
                for weekday in ['0', '1', '2', '3', '4']
                for hour in [8, 13]
            ],
            'name': 'Standard 40h/week',
        })

        cls.employee_joseph = cls.env['hr.employee'].create({
            'name': 'joseph',
            'work_email': 'joseph@a.be',
            'tz': 'UTC',
            'create_date': '2015-01-01 00:00:00',
        })
        cls.resource_joseph = cls.employee_joseph.resource_id
        cls.employee_bert = cls.env['hr.employee'].create({
            'name': 'bert',
            'work_email': 'bert@a.be',
            'tz': 'UTC',
            'create_date': '2015-01-01 00:00:00',
        })
        cls.resource_bert = cls.employee_bert.resource_id
        cls.employee_janice = cls.env['hr.employee'].create({
            'name': 'janice',
            'work_email': 'janice@a.be',
            'tz': 'America/New_York',
            'create_date': '2015-01-01 00:00:00',
        })
        cls.resource_janice = cls.employee_janice.resource_id
        cls.planning_manager_user = mail_new_test_user(
            cls.env, login='planning_manager_user', groups='planning.group_planning_manager', name='Planning Manager User'
        )

    @classmethod
    def setUpDates(cls):
        cls.random_date = datetime(2020, 11, 27)  # it doesn't really matter but it lands on a Friday
        cls.random_sunday_date = datetime(2024, 3, 10)  # this should be a Sunday and thus a closing day
        cls.random_monday_date = datetime(2024, 3, 11)  # this should be a Monday

    @classmethod
    def setUpCalendars(cls):
        cls.company_calendar = cls.env['resource.calendar'].create([
            {
                'name': 'Classic 40h/week',
                'hours_per_day': 8.0,
                'attendance_ids': [
                    (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                    (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 17}),
                    (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                    (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 17}),
                    (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
                    (0, 0, {'dayofweek': '2', 'hour_from': 13, 'hour_to': 17}),
                    (0, 0, {'dayofweek': '3', 'hour_from': 6, 'hour_to': 12}),
                    (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 15}),
                    (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
                    (0, 0, {'dayofweek': '4', 'hour_from': 13, 'hour_to': 17})
                ],
            },
        ])


class TestUiCommon(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.resource_calendar_id = cls.env['resource.calendar'].create({
            'attendance_ids': [
                (0, 0,
                    {
                        'dayofweek': weekday,
                        'hour_from': hour,
                        'hour_to': hour + 4,
                    })
                for weekday in ['0', '1', '2', '3', '4']
                for hour in [8, 13]
            ],
            'name': 'Standard 40h/week',
        })
        thibault_calendar = cls.env['resource.calendar'].create({
            'name': 'Flexible Calendar',
            'calendar_type': 'undefined',
            'attendance_ids': [],
            'hours_per_week': 40,
            'hours_per_day': 8.0,
        })
        cls.employee_thibault = cls.env['hr.employee'].create({
            'name': 'Aaron',
            'work_email': 'aaron@a.be',
            'tz': 'Europe/Brussels',
            'resource_calendar_id': thibault_calendar.id,
        })
        start = datetime.now() + relativedelta(weekday=MO(-1), hour=10, minute=0, second=0, microsecond=0)
        cls.env['planning.slot'].create({
            'start_datetime': start,
            'end_datetime': start + relativedelta(hour=11),
        })


class TestPlanningContractCommon(TestCommonPlanning):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setUpEmployees()
        cls.setUpDates()
        cls.employee_contract_type = cls.env.ref('hr.contract_type_employee')
        cls.employee_bert['employee_type_id'] = cls.employee_contract_type.id
        cls.calendar_35h = cls.env['resource.calendar'].create({
            'name': '35h calendar',
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 16}),
                (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 16}),
                (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '2', 'hour_from': 13, 'hour_to': 16}),
                (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 16}),
                (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '4', 'hour_from': 13, 'hour_to': 16})
            ]
        })
        cls.calendar_40h = cls.env['resource.calendar'].create({'name': 'Default calendar'})
