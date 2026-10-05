# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from freezegun import freeze_time

from odoo.tests import tagged
from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestPayrollEmployeeActivities(TestPayrollCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with freeze_time('2025-01-02'):
            cls.employee = cls.create_employee({
                'name': 'Some Dude',
                'date_version': date(2025, 1, 1),
                'contract_date_start': date(2025, 1, 1),
                'contract_date_end': False,
            })
            cls.version = cls.employee.version_id

            credit_time_calendar = cls.env['resource.calendar'].sudo().create({
                'name': 'Credit Time Calendar',
                'company_id': cls.env.company.id,
                'hours_per_day': 7.6,
                'full_time_required_hours': 38,
                'attendance_ids': [
                    (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                    (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 16.6}),
                    (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                    (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 16.6}),
                    (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                    (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 16.6}),
                    (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
                    (0, 0, {'dayofweek': '4', 'hour_from': 13, 'hour_to': 16.6})
                ] + [
                    (0, 0, {
                        'dayofweek': dayofweek,
                        'hour_from': hour_from,
                        'hour_to': hour_to,
                        'work_entry_type_id': cls.env.ref('hr_work_entry.l10n_be_work_entry_type_credit_time').id
                    }) for dayofweek, hour_from, hour_to in [
                        ("2", 8.0, 12.0),
                        ("2", 13.0, 16.6),
                    ]
                ],
            })

            wizard = cls.env['l10n_be.hr.payroll.schedule.change.wizard'].with_context(allowed_company_ids=cls.env.company.ids).new({
                'version_id': cls.version.id,
                'date_start': date(2025, 1, 2),
                'date_end': date(2025, 4, 30),
                'resource_calendar_id': credit_time_calendar.id,
            })
            wizard.action_validate()

    def test_only_one_part_time_activity_for_hr_version(self):
        """
        Test that a version only creates a related part time activity
        if there is none yet.
        """
        employee_domain = [('res_model', '=', 'hr.employee'), ('res_id', '=', self.employee.id)]

        employee_activities = self.env['mail.activity'].search(employee_domain)
        part_time_activities = employee_activities.filtered(lambda a: a.summary == 'Part Time')
        self.assertEqual(len(part_time_activities), 1, 'A part time activity should have been created.')

        self.employee._trigger_l10n_be_next_activities()

        employee_activities = self.env['mail.activity'].search(employee_domain)
        part_time_activities = employee_activities.filtered(lambda a: a.summary == 'Part Time')
        self.assertEqual(len(part_time_activities), 1, 'The existing part time activity should prevent the creation of a new one.')

    def test_part_time_activity_for_new_version(self):
        """
        Test that a new part time activity is created for new contracts, even if previous part time contract
        """
        version = self.employee.create_version({
            'date_version': date(2025, 2, 1),
        })

        with freeze_time('2025-02-03'):
            self.employee._cron_update_current_version_id()
            employee_domain = [('res_model', '=', 'hr.employee'), ('res_id', '=', self.employee.id)]

            employee_activities = self.env['mail.activity'].search(employee_domain)
            part_time_activities = employee_activities.filtered(lambda a: a.summary == 'Part Time')
            self.assertEqual(len(part_time_activities), 1, 'Only one part time activity should exist.')

        with freeze_time('2025-03-03'):
            version.write({
                'contract_date_end': date(2025, 2, 28),
            })
            march_version = self.employee.create_version({
                'date_version': date(2025, 3, 1),
                'contract_date_start': date(2025, 3, 1),
                'contract_date_end': date(2025, 4, 30),
            })

            self.employee._cron_update_current_version_id()
            employee_activities = self.env['mail.activity'].search(employee_domain)
            part_time_activities = employee_activities.filtered(lambda a: a.summary == 'Part Time')
            self.assertEqual(len(part_time_activities), 2, 'A second part time activity should have been created for the new contract.')

        with freeze_time('2025-04-01'):
            march_version.write({
                'contract_date_end': date(2025, 4, 2),
            })
            self.employee.create_version({
                'date_version': date(2025, 4, 3),
                'contract_date_start': date(2025, 4, 3),
                'contract_date_end': date(2025, 4, 30),
            })

        with freeze_time('2025-04-04'):
            self.employee._cron_update_current_version_id()
            employee_activities = self.env['mail.activity'].search(employee_domain)
            part_time_activities = employee_activities.filtered(lambda a: a.summary == 'Part Time')
            self.assertEqual(len(part_time_activities), 3, 'A third part time activity should have been created for the new contract.')

    def test_credit_time_unusual_days_dashboard(self):
        date_from = '2025-01-06 00:00:00'  # Monday
        date_to = '2025-01-12 23:59:59'  # Sunday

        dashboard_unusual_days = self.env['hr.leave'].with_context(employee_id=self.employee.id).get_unusual_days(date_from, date_to)

        self.assertTrue(dashboard_unusual_days.get('2025-01-08'))  # Wednesday = credit time
        self.assertFalse(dashboard_unusual_days.get('2025-01-09'))  # Thursday = normal attendance
