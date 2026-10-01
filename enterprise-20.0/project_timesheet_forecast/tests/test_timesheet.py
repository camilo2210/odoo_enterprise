# Part of Odoo. See LICENSE file for full copyright and licensing details
from datetime import date, datetime

from odoo.addons.project_forecast.tests.common import TestCommonForecast

from odoo.tests import tagged


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestPlanningTimesheet(TestCommonForecast):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.setUpEmployees()
        cls.setUpProjects()

    def test_gantt_progress_bar_group_by_project(self):
        """
        This test ensures that the _gantt_progress_bar_project_id return values is correct.
        - Every project_id present in the res_ids should be present in the dict.
        - The 'value' should be 0 if the project contains no planning slot available in the date range given, else it should be equal to the total of every available slot for the given date range.
        - The 'max value' should be equal to the 'allocated_hours' field for each project.
        """
        projects = project_without_slot, project_slot_not_in_date_range, project_slot_in_date_range = self.env['project.project'].create([{
            'name': 'Project no slot',
            'allocated_hours': 40,
        }, {
            'name': 'Project slot not in date range',
            'allocated_hours': 50,
        }, {
            'name': 'Project slot in date range',
            'allocated_hours': 60,
        }])
        start_date = datetime(2021, 10, 22, 8, 0, 0)
        end_date = datetime(2021, 10, 29, 8, 0, 0)
        planning_vals = {
            'resource_ids': self.resource_joseph.ids,
            'state': '2_published',
            'allow_timesheets': True,
        }
        self.env["planning.slot"].create([{
            **planning_vals,
            'project_id': project_slot_in_date_range.id,
            'start_datetime': datetime(2021, 10, 25, 8, 0, 0),
            'end_datetime': datetime(2021, 10, 26, 12, 0, 0),
        }, {
            **planning_vals,
            'project_id': project_slot_in_date_range.id,
            'start_datetime': datetime(2021, 10, 26, 13, 0, 0),
            'end_datetime': datetime(2021, 10, 26, 17, 0, 0),
        }, {
            **planning_vals,
            'project_id': project_slot_not_in_date_range.id,
            'start_datetime': datetime(2021, 10, 20, 8, 0, 0),
            'end_datetime': datetime(2021, 10, 21, 12, 0, 0),
        }])
        res_ids = projects.ids
        expected_values = {
            project_without_slot.id: {'value': 0.0, 'max_value': 40.0},
            project_slot_not_in_date_range.id: {'value': 0.0, 'max_value': 50.0},
            project_slot_in_date_range.id: {'value': 16.0, 'max_value': 60.0}, # 12 hours in the 1st slot + 4 hours in the 2nd slot
        }
        values = self.env["planning.slot"]._gantt_progress_bar_project_id(res_ids, start_date, end_date)
        self.assertDictEqual(values, expected_values)

    def test_compute_slot_effective_hours(self):
        slot = self.env["planning.slot"].create({
            'resource_ids': self.employee_bert.resource_id.ids,
            'project_id': self.project_opera.id,
            'task_id': self.task_opera_place_new_chairs.id,
            'start_datetime': datetime(2024, 1, 1, 8, 0, 0),
            'end_datetime': datetime(2024, 1, 31, 17, 0, 0),
        })
        self.assertEqual(slot.effective_hours, 0)
        self.env['account.analytic.line'].create({
            'name': 'Test Timesheet',
            'unit_amount': 2,
            'project_id': self.project_opera.id,
            'task_id': self.task_opera_place_new_chairs.id,
            'employee_id': self.employee_bert.id,
            'date': date(2024, 1, 15),
        })
        self.assertEqual(slot.effective_hours, 2)

    def test_planning_analysis_report_fields(self):
        ''' This test ensure that the fields of the planning analysis report are correctly computed'''
        slot = self.env["planning.slot"].create({
            'resource_ids': self.employee_bert.resource_id.ids,
            'project_id': self.project_opera.id,
            'start_datetime': datetime(2025, 1, 22, 0, 0, 0),
            'end_datetime': datetime(2025, 1, 23, 0, 0, 0),
            'state': '2_published',
            'allow_timesheets': True,
        })
        self.env['account.analytic.line'].create({
            'name': 'Test Timesheet',
            'unit_amount': 2,
            'project_id': self.project_opera.id,
            'task_id': self.task_opera_place_new_chairs.id,
            'employee_id': self.employee_bert.id,
            'date': date(2025, 1, 22),
        })
        slot.invalidate_recordset()

        effective_hours, remaining_hours, percentage_hours = self.env['planning.analysis.report']._read_group(
            [('slot_id', '=', slot.id)],
            aggregates=['effective_hours:sum', 'remaining_hours:sum', 'percentage_hours:avg'],
        )[0]

        self.assertEqual(effective_hours, 2.0, "Effective hours should match the timesheet entry")
        self.assertEqual(remaining_hours, 6.0, "Remaining hours should be Allocated Hours - Effective hours")
        self.assertEqual(percentage_hours, 25.0, "Percentage hours should be calculated properly")

    def test_assistant_planning_slot_respects_allocated_hours(self):
        """Assistant planning events should end after allocated_hours, not end_datetime."""
        self.employee_bert.user_id = self.employee_bert._get_or_create_light_user()
        slot = self.env["planning.slot"].create({
            "resource_ids": self.employee_bert.resource_id.ids,
            "project_id": self.project_opera.id,
            "start_datetime": datetime(2025, 1, 22, 8, 0, 0),
            "end_datetime": datetime(2025, 1, 22, 17, 0, 0),  # 9-hour span
            "allocated_hours": 6,
            "state": "2_published",
        })

        planning_getter = next(
            getter["getter"]
            for getter in self.env["account.analytic.line"]
                .with_user(self.employee_bert.user_id)
                ._get_assistant_events_getters()
            if getter["getter"].__name__ == "get_planning_slots"
        )
        events = planning_getter(datetime(2025, 1, 22), datetime(2025, 1, 23))
        self.assertEqual(len(events), 1, "Expected exactly one planning event to be returned.")

        event = events[0]
        self.assertEqual(event["start"], slot.start_datetime, "The planning event start should match the planning slot start_datetime.")
        self.assertEqual(event["stop"], slot.end_datetime, "The planning event stop should match the planning slot end_datetime.")
        self.assertEqual(event["duration"], 6, "The planning event stop should be computed from allocated_hours.")

    def test_planning_analysis_report_multi_resource(self):
        self.employee_bert.resource_calendar_id = self.env['resource.calendar'].create({
            'name': 'Flexible',
            'company_id': self.employee_bert.company_id.id,
            'calendar_type': 'undefined',
        })
        slot_allocated_hours = self.env['planning.slot'].create({
            'resource_ids': [self.employee_bert.resource_id.id, self.employee_janice.resource_id.id, self.employee_joseph.resource_id.id],
            'project_id': self.project_opera.id,
            'start_datetime': datetime(2025, 1, 22, 0, 0, 0),
            'end_datetime': datetime(2025, 1, 22, 23, 59, 59),
            'state': '2_published',
            'allow_timesheets': True,
        }).allocated_hours
        self.env['planning.slot'].flush_model()
        reports = self.env['project.timesheet.forecast.report.analysis'].formatted_read_group(
            domain=[('project_id', "=", self.project_opera.id)],
            groupby=["employee_id"],
            aggregates=["planned_hours:sum", "planned_hours:count"],
        )
        individual_allocated_hours = slot_allocated_hours / len(reports)
        for report in reports:
            self.assertEqual(individual_allocated_hours, report['planned_hours:sum'], "Hours should be evenly split between each resource in the analysis report")
