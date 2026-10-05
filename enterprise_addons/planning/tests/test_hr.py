# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details
from datetime import datetime, UTC

from freezegun import freeze_time

from odoo import fields
from odoo.tools.intervals import Intervals

from odoo.tests import tagged

from .common import TestCommonPlanning


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestPlanningHr(TestCommonPlanning):
    @classmethod
    def setUpClass(cls):
        super(TestPlanningHr, cls).setUpClass()
        cls.classPatch(cls.env.cr, 'now', fields.Datetime.now)
        with freeze_time('2015-01-01'):
            cls.setUpEmployees()
        calendar_joseph = cls.env['resource.calendar'].create({
            'name': 'Calendar 1',
            'hours_per_day': 8.0,
            'attendance_ids': [
                (0, 0, {'dayofweek': '3', 'hour_from': 9, 'hour_to': 13}),
                (0, 0, {'dayofweek': '3', 'hour_from': 14, 'hour_to': 18}),
            ]
        })
        (cls.employee_joseph + cls.employee_bert).resource_calendar_id = calendar_joseph
        cls.employee_joseph.tz = 'UTC'
        cls.role_a, cls.role_b, cls.role_c = cls.env['planning.role'].create([
            {'name': 'role a'},
            {'name': 'role b'},
            {'name': 'role c'},
        ])

    def test_change_default_planning_role(self):
        self.assertFalse(self.employee_joseph.default_planning_role_id, "Joseph should have no default planning role")
        self.assertFalse(self.employee_joseph.planning_role_ids, "Joseph should have no planning roles")

        self.employee_joseph.default_planning_role_id = self.role_a

        self.assertEqual(self.employee_joseph.default_planning_role_id, self.role_a, "Joseph should have role a as default role")
        self.assertTrue(self.role_a in self.employee_joseph.planning_role_ids, "role a should be added to his planning roles")

        self.employee_joseph.write({'planning_role_ids': [(5, 0, 0)]})
        self.assertFalse(self.employee_joseph.planning_role_ids, "role a should be automatically removed from his planning roles")

        self.employee_joseph.write({'planning_role_ids': self.role_a})
        self.employee_joseph.default_planning_role_id = self.role_b
        self.assertTrue(self.role_a in self.employee_joseph.planning_role_ids, "role a should still be in planning roles")
        self.assertTrue(self.role_b in self.employee_joseph.planning_role_ids, "role b should be added to planning roles")

    def test_relation_employee_role_ids_resource_id_role_ids(self):

        """
            This test checks that the fields employee.planning_role_ids, employee.default_planning_role_id and employee.resource_id.role_ids
            are all consistent and properly update on the change of the fields. Here's the expected behavior :
            Invariant :
                resource_id.role_ids = planning_role_ids
                default_planning_role_id in planning_role_ids
            on planning_role_ids update :
                resource_id.role_ids is set accordingly.
                if planning_role_ids is set to False, set default_role_id to False
                if default_role_id is not in planning_role_ids anymore, set default_role_id to planning_role_ids[0]
            on resource_id.role_ids update :
                planning_role_ids is set accordingly.
                if planning_role_ids is set to False, set default_role_id to False
                if default_role_id is not in planning_role_ids anymore, set default_role_id to planning_role_ids[0]
            on default_planning_role_id update:
                if default_planning_role_id not in planning_role_ids, add default_planning_role_id to planning_role_ids and resource_id.role_ids
                default_planning_role_id is not removed from planning_role_ids
                if planning_role_ids is set to False in the same write as the change of default_planning_role_id, both the fields are set to False
        """
        self.assertFalse(self.employee_joseph.default_planning_role_id, "Joseph should have no default planning role")
        self.assertFalse(self.employee_joseph.planning_role_ids, "Joseph should have no planning roles")

        roles = self.env['planning.role']
        roles |= self.role_a
        roles |= self.role_b
        roles |= self.role_c
        # change on employee.planning_role_ids
        self.employee_joseph.planning_role_ids = roles
        self.assertEqual(self.employee_joseph.default_planning_role_id, self.role_a, "Joseph should have role a as default role")
        self.assertEqual(self.employee_joseph.resource_id.role_ids, roles, "Joseph should have role a, b and c as roles")
        self.assertEqual(self.employee_joseph.planning_role_ids, roles, "Joseph should have role a, b and c as resource_id.role_ids")

        self.employee_joseph.planning_role_ids = False
        self.assertFalse(self.employee_joseph.default_planning_role_id, "Joseph should have role a as default role")
        self.assertFalse(self.employee_joseph.resource_id.role_ids, "Joseph should have role a, b and c as roles")
        self.assertFalse(self.employee_joseph.planning_role_ids, "Joseph should have role a, b and c as resource_id.role_ids")

        #change on employee.resource_id.role_ids
        self.employee_joseph.resource_id.role_ids = roles
        self.assertEqual(self.employee_joseph.resource_id.role_ids, roles, "Joseph should have role a, b and c as roles")
        self.assertEqual(self.employee_joseph.default_planning_role_id, self.role_a, "Joseph should have role a as default role")
        self.assertEqual(self.employee_joseph.planning_role_ids, roles, "Joseph should have role a, b and c as resource_id.role_ids")

        self.employee_joseph.resource_id.role_ids = False
        self.assertFalse(self.employee_joseph.resource_id.role_ids, "Joseph should have role a, b and c as roles")
        self.assertFalse(self.employee_joseph.default_planning_role_id, "Joseph should have role a as default role")
        self.assertFalse(self.employee_joseph.planning_role_ids, "Joseph should have role a, b and c as resource_id.role_ids")

        #change mixin
        role_d, role_e = self.env['planning.role'].create([
            {'name': 'role d'},
            {'name': 'role e'},
        ])
        roles |= role_d
        roles = roles - self.role_a

        self.employee_joseph.write({'planning_role_ids': roles, 'default_planning_role_id': role_e})
        roles |= role_e

        self.assertEqual(self.employee_joseph.resource_id.role_ids, roles, "Joseph should have role b, c, d and e as roles")
        self.assertEqual(self.employee_joseph.default_planning_role_id, role_e, "Joseph should have role e as default role")
        self.assertEqual(self.employee_joseph.planning_role_ids, roles, "Joseph should have role b, c, d and e as resource_id.role_ids")

    def test_hr_employee_view_planning(self):
        self.env['planning.slot'].create({
            'resource_ids': self.resource_bert.ids,
            'start_datetime': datetime(2021, 6, 4, 8, 0),
            'end_datetime': datetime(2021, 6, 5, 17, 0),
        }).copy()
        action = self.employee_bert.action_view_planning()
        # just returns action
        slots = self.env['planning.slot'].search(action['domain'])
        self.assertEqual(action['res_model'], 'planning.slot')
        self.assertEqual(len(slots), 2, 'Bert has 2 planning slots')
        self.assertEqual(action['context']['default_resource_ids'], self.resource_bert.ids)

    def test_employee_contract_validity_per_period(self):
        start = datetime(2015, 11, 8, 00, 00, 00, tzinfo=UTC)
        end = datetime(2015, 11, 21, 23, 59, 59, tzinfo=UTC)
        calendars_validity_within_period = self.employee_joseph.resource_id._get_calendars_validity_within_period(start, end, default_company=self.employee_joseph.company_id)

        self.assertEqual(len(calendars_validity_within_period[self.employee_joseph.resource_id.id]), 1, "There should exist 1 calendar within the period")
        interval_calendar_joseph = Intervals([(
            start,
            end,
            self.env['resource.calendar.attendance']
        )])
        computed_interval = calendars_validity_within_period[self.employee_joseph.resource_id.id][self.employee_joseph.resource_calendar_id]
        self.assertFalse(computed_interval - interval_calendar_joseph, "The interval of validity for the 40h calendar must be from 2015-11-16 to 2015-11-21, not more")
        self.assertFalse(interval_calendar_joseph - computed_interval, "The interval of validity for the 40h calendar must be from 2015-11-16 to 2015-11-21, not less")

    def test_employee_work_intervals(self):
        start = datetime(2015, 11, 8, 00, 00, 00, tzinfo=UTC)
        end = datetime(2015, 11, 21, 23, 59, 59, tzinfo=UTC)
        work_intervals, _ = self.employee_joseph.resource_id._get_valid_work_intervals(start, end)
        sum_work_intervals = sum(
            (stop - start).total_seconds() / 3600
            for start, stop, _resource in work_intervals[self.employee_joseph.resource_id.id]
        )
        self.assertEqual(16, sum_work_intervals, "Sum of the work intervals for the employee Joseph should be 8h+8h = 16h")

    # this is not a test
    def employee_work_planning_hours_info_tests_data(self):
        joseph_resource_id = self.employee_joseph.resource_id
        bert_resource_id = self.employee_bert.resource_id
        department = self.env['hr.department'].create({'name': "dep 1"})
        slots = self.env['planning.slot'].create([{
            'resource_ids': joseph_resource_id.ids,
            'start_datetime': datetime(2015, 11, 8, 8, 0),
            'end_datetime': datetime(2015, 11, 14, 17, 0),
            'role_id': self.role_a.id,
            'department_id': department.id
            # allocated_hours will be : 8h (see calendar)
        }, {
            'resource_ids': joseph_resource_id.ids,
            'start_datetime': datetime(2015, 11, 16, 8, 0),
            'end_datetime': datetime(2015, 11, 16, 17, 0),
            'role_id': self.role_a.id,
            'department_id': department.id
            # allocated_hours will be : 0h (see calendar)
        }, {
            'resource_ids': joseph_resource_id.ids,
            'start_datetime': datetime(2015, 11, 17, 8, 0),
            'end_datetime': datetime(2015, 11, 17, 17, 0),
            'role_id': self.role_a.id,
            'department_id': department.id
            # allocated_hours will be : 0h (see calendar)
        }, {
            'resource_ids': joseph_resource_id.ids,
            'start_datetime': datetime(2015, 11, 18, 8, 0),
            'end_datetime': datetime(2015, 11, 18, 17, 0),
            'role_id': self.role_a.id,
            'department_id': department.id
            # allocated_hours will be : 0h (see calendar)
        }, {
            'resource_ids': joseph_resource_id.ids,
            'start_datetime': datetime(2015, 11, 23, 8, 0),
            'end_datetime': datetime(2015, 11, 27, 17, 0),
            'allocated_percentage': 50.0,
            'role_id': self.role_a.id,
            'department_id': department.id
            # allocated_hours will be : 4h (see calendar)
        }, {
            'resource_ids': bert_resource_id.ids,
            'start_datetime': datetime(2015, 11, 8, 8, 0),
            'end_datetime': datetime(2015, 11, 14, 17, 0),
            'role_id': self.role_b.id,
            'department_id': department.id
            # allocated_hours will be : 8h (see calendar)
        }])

        return slots, department

    def test_employee_work_planning_hours_info(self):
        joseph_resource_id = self.employee_joseph.resource_id
        self.employee_work_planning_hours_info_tests_data()

        planning_hours_info = self.env['planning.slot']._gantt_progress_bar(
            'resource_ids', joseph_resource_id.ids, datetime(2015, 11, 8), datetime(2015, 11, 28, 23, 59, 59)
        )
        self.assertEqual(24, planning_hours_info[joseph_resource_id.id]['max_value'], "Work hours for the employee Jules should be 8h+8h+8h = 24h")
        self.assertEqual(12, planning_hours_info[joseph_resource_id.id]['value'], "Planned hours for the employee Jules should be 8h+4h = 12h")

        planning_hours_info = self.env['planning.slot']._gantt_progress_bar(
            'resource_ids', joseph_resource_id.ids, datetime(2015, 11, 12), datetime(2015, 11, 12, 23, 59, 59)
        )
        self.assertEqual(8, planning_hours_info[joseph_resource_id.id]['max_value'],
                         "Work hours for the employee Jules should be 8h as its a Thursday.")
        self.assertEqual(8, planning_hours_info[joseph_resource_id.id]['value'],
                         "Planned hours for the employee Jules should be 8h as its a Thursday and hours are computed on a forecast slot.")

        planning_hours_info = self.env['planning.slot']._gantt_progress_bar(
            'resource_ids', joseph_resource_id.ids, datetime(2015, 11, 26), datetime(2015, 11, 26, 23, 59, 59)
        )
        self.assertEqual(8, planning_hours_info[joseph_resource_id.id]['max_value'],
                         "Work hours for the employee Jules should be 8h as its a Thursday.")
        self.assertEqual(4, planning_hours_info[joseph_resource_id.id]['value'],
                         "Planned hours for the employee Jules should be 4h as its a Thursday and hours are computed on a forecast slot (allocated_percentage = 50).")

    def test_gantt_progress_bars(self):
        slots, department = self.employee_work_planning_hours_info_tests_data()
        self.employee_joseph.write({
            'planning_role_ids': self.role_a.ids,
            'default_planning_role_id': self.role_a.id,
            'department_id': department.id,
        })
        self.employee_bert.write({
            'planning_role_ids': self.role_b.ids,
            'default_planning_role_id': self.role_b.id,
            'department_id': department.id,
        })

        gantt_data = self.env["planning.slot"].get_gantt_data(
            domain=[('id', 'in', slots.ids)],
            groupby=['role_id', 'resource_ids'],
            progress_bar_fields=['resource_ids', 'role_id'],
            read_specification={'display_name': {}},
            start_date=datetime(2015, 11, 8),
            stop_date=datetime(2015, 11, 28, 23, 59, 59),
        )

        progress_bars = gantt_data['progress_bars']['role_id']
        total_progress_bar = gantt_data['progress_bars']['__default'][False]
        self.assertEqual(12, progress_bars[self.role_a.id]['value'], "slots total = 8 + 4 assigned to Joseph")
        self.assertEqual(24, progress_bars[self.role_a.id]['max_value'], "Joseph have role_a")

        self.assertEqual(8, progress_bars[self.role_b.id]['value'], "slots total = 8 assigned to Bert")
        self.assertEqual(24, progress_bars[self.role_b.id]['max_value'], "Bert have role_b")

        self.assertEqual(20, total_progress_bar['value'], "sum of value of the last key in progress_bars")
        self.assertEqual(48, total_progress_bar['max_value'], "sum of max_value of the last key in progress_bars")

        gantt_data = self.env["planning.slot"].get_gantt_data(
            domain=[('id', 'in', slots.ids)],
            groupby=['department_id', 'resource_ids'],
            progress_bar_fields=['resource_ids', 'department_id'],
            read_specification={'display_name': {}},
            start_date=datetime(2015, 11, 8),
            stop_date=datetime(2015, 11, 28, 23, 59, 59),
        )

        progress_bars = gantt_data['progress_bars']['department_id']
        total_progress_bar = gantt_data['progress_bars']['__default'][False]

        self.assertEqual(20, progress_bars[department.id]['value'], "slots total = 20")
        self.assertEqual(48, progress_bars[department.id]['max_value'], "Both employees work in this department")

        self.assertEqual(20, total_progress_bar['value'], "sum of value of the last key in progress_bars")
        self.assertEqual(48, total_progress_bar['max_value'], "sum of max_value of the last key in progress_bars")
