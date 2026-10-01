# Part of Odoo. See LICENSE file for full copyright and licensing details
from datetime import date, datetime

from odoo.tests import tagged, freeze_time

from odoo.addons.project_forecast.tests.common import TestCommonForecast


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestPlanningTimesheetForecastReport(TestCommonForecast):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.duration_based_calendar = cls.env['resource.calendar'].create({
            'name': '40 hours/week duration based',
            'hours_per_day': 8,
            'full_time_required_hours': 40,
            'attendance_ids': [(5, 0, 0),
                (0, 0, {'dayofweek': '0', 'duration_hours': 6, 'hour_from': 0, 'hour_to': 0}),
                (0, 0, {'dayofweek': '1', 'duration_hours': 6, 'hour_from': 0, 'hour_to': 0}),
                (0, 0, {'dayofweek': '2', 'duration_hours': 6, 'hour_from': 0, 'hour_to': 0}),
                (0, 0, {'dayofweek': '3', 'duration_hours': 6, 'hour_from': 0, 'hour_to': 0}),
                (0, 0, {'dayofweek': '4', 'duration_hours': 6, 'hour_from': 0, 'hour_to': 0}),
            ],
        })

        cls.setUpEmployees()

        cls.setUpProjects()
        cls.project_opera.write({'allow_timesheets': True})

    @freeze_time('2019-06-06 01:00:00')
    def test_timesheets_forecast_analysis_with_weekend_included(self):
        """ Checks that weekends are excluded when a slot spans over one. """
        slot = self.env['planning.slot'].create({
            'project_id': self.project_opera.id,
            'resource_ids': self.resource_bert.ids,
            'start_datetime': datetime(2019, 6, 6, 8, 0, 0),
            # 6/8/2019 and 6/9/2019 are weekend days
            'end_datetime': datetime(2019, 6, 12, 17, 0, 0),
            'allocated_percentage': 100,
            'state': '1_draft',
        })
        self.assertEqual(slot.allocated_hours, 40)

        self.env['planning.slot'].flush_model()
        result = self.env['project.timesheet.forecast.report.analysis'].formatted_read_group(
            domain=[["project_id", "=", self.project_opera.id]],
            groupby=["entry_date:month"],
            aggregates=["planned_hours:sum"],
        )
        self.assertEqual((result[0]['planned_hours:sum']), 40)

    @freeze_time('2019-06-06 01:00:00')
    def test_timesheets_forecast_report_public_holidays(self):
        """ Checks that public holidays are taken into account. """
        self.env['resource.calendar.leaves'].create({
            'name': "Public Holiday",
            'date_from': date(2019, 6, 19),
            'date_to': date(2019, 6, 19),
        })
        self.env['planning.slot'].create({
            'project_id': self.project_opera.id,
            'resource_ids': self.resource_bert.ids,
            'start_datetime': datetime(2019, 6, 18, 8, 0, 0),
            'end_datetime': datetime(2019, 6, 20, 17, 0, 0),
            'allocated_percentage': 100,
            'state': '1_draft',
        })

        self.env['planning.slot'].flush_model()
        result = self.env['project.timesheet.forecast.report.analysis'].formatted_read_group(
            domain=[["project_id", "=", self.project_opera.id]],
            groupby=["entry_date:month"],
            aggregates=["planned_hours:sum"],
        )
        self.assertEqual((result[0]['planned_hours:sum']), 16)

    @freeze_time('2019-06-06 01:00:00')
    def test_timesheets_forecast_report_public_holidays_another_company(self):
        """ Checks that public holidays with another company aren't taken into account. """
        self.env['planning.slot'].create({
            'project_id': self.project_opera.id,
            'resource_ids': self.resource_bert.ids,
            'start_datetime': datetime(2019, 6, 18, 8, 0, 0),
            'end_datetime': datetime(2019, 6, 20, 17, 0, 0),
            'allocated_percentage': 100,
            'state': '1_draft',
            'company_id': self.env.company.id,
        })

        company = self.env['res.company'].create({"name": "Test company"})
        self.env['resource.calendar.leaves'].with_company(company.id).create({
            'name': "Public Holiday",
            'date_from': date(2019, 6, 19),
            'date_to': date(2019, 6, 19),
            'company_id': company.id,
        })

        self.env['planning.slot'].flush_model()
        result = self.env['project.timesheet.forecast.report.analysis'].formatted_read_group(
            domain=[["project_id", "=", self.project_opera.id]],
            groupby=["entry_date:month"],
            aggregates=["planned_hours:sum"],
        )
        self.assertEqual((result[0]['planned_hours:sum']), 24)

    @freeze_time('2019-06-06 01:00:00')
    def test_timesheets_forecast_report_duration_based_calendar(self):
        """ Checks the report includes all slots when the resrouce calendar is duration based. """
        self.resource_bert.calendar_id = self.duration_based_calendar
        slot = self.env['planning.slot'].create({
            'project_id': self.project_opera.id,
            'resource_ids': self.resource_bert.ids,
            'start_datetime': datetime(2019, 6, 6, 8, 0, 0),
            'end_datetime': datetime(2019, 6, 7, 17, 0, 0),
            'allocated_percentage': 100,
            'state': '1_draft',
        })
        self.assertEqual(slot.allocated_hours, 12)

        self.env['planning.slot'].flush_model()
        result = self.env['project.timesheet.forecast.report.analysis'].formatted_read_group(
            domain=[["project_id", "=", self.project_opera.id]],
            groupby=["entry_date:month"],
            aggregates=["planned_hours:sum"],
        )
        self.assertEqual((result[0]['planned_hours:sum']), 12)
