# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time

from odoo.addons.planning.tests.common import TestCommonPlanning

class TestCommon(TestCommonPlanning):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setUpEmployees()
        cls.setUpDates()

        cls.env.user.tz = 'Europe/Brussels'
        cls.calendar = cls.env['resource.calendar'].create({
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
        cls.env.company.resource_calendar_id = cls.calendar

        # Leave type
        cls.work_entry_type = cls.env['hr.work.entry.type'].create({
            'name': 'time off',
            'code': 'time off',
            'requires_allocation': False,
            'request_unit': 'hour',
            'unit_of_measure': 'hour',
            'count_as': 'absence',
        })

        # Allocations
        cls.allocation_bert = cls.env['hr.leave.allocation'].create({
            'state': 'confirm',
            'work_entry_type_id': cls.work_entry_type.id,
            'employee_id': cls.employee_bert.id,
            'date_from': time.strftime('%Y-01-01'),
            'date_to': time.strftime('%Y-12-31'),
        })
        cls.allocation_bert.action_approve()
        cls.flex_role = cls.env['planning.role'].create({'name': 'flex role'})
