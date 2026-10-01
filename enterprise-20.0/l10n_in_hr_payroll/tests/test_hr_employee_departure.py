# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from freezegun import freeze_time

from odoo.addons.l10n_in_hr_payroll.tests.common import TestPayrollCommon
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestHrEmployeeDeparture(TestPayrollCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.departure_reason = cls.env['hr.departure.reason'].create({
            'name': 'Resignation',
        })
        cls.rahul_emp.work_email = 'rahul@example.com'

    def test_notice_period_defaults(self):
        """Test that notice period start defaults to dismissal_date and departure_date to +1 month"""
        departure = self.env['hr.employee.departure'].create({
            'employee_id': self.rahul_emp.id,
            'departure_reason_id': self.departure_reason.id,
            'dismissal_date': date(2026, 1, 19),
        })

        self.assertEqual(
            departure.l10n_in_notice_period_start,
            date(2026, 1, 19),
            "Notice period start should equal dismissal date"
        )
        self.assertEqual(
            departure.departure_date,
            date(2026, 2, 19),
            "Departure date should default to dismissal date + 1 month"
        )

    def test_notice_period_email_on_schedule(self):
        """Test that email is sent when departure is scheduled"""
        departure = self.env['hr.employee.departure'].create({
            'employee_id': self.rahul_emp.id,
            'departure_reason_id': self.departure_reason.id,
            'dismissal_date': date(2026, 1, 19),
        })

        initial_mail_count = self.env['mail.mail'].search_count([
            ('email_to', '=', self.rahul_emp.work_email),
            ('subject', '=', 'Notice Period Details'),
        ])

        with freeze_time("2026-01-19"):
            departure.action_schedule()

        new_mail_count = self.env['mail.mail'].search_count([
            ('email_to', '=', self.rahul_emp.work_email),
            ('subject', '=', 'Notice Period Details'),
        ])

        self.assertGreater(
            new_mail_count,
            initial_mail_count,
            "Email should be sent on schedule for Indian departures"
        )

    def test_notice_period_email_only_for_indian_company(self):
        """Test that email is only sent for Indian companies"""
        us_company = self.env['res.company'].create({
            'name': 'Company US',
            'country_id': self.env.ref('base.us').id,
        })

        employee_us = self.env['hr.employee'].create({
            'name': 'US Employee',
            'work_email': 'us@example.com',
            'company_id': us_company.id,
            'date_version': date(2025, 1, 1),
            'contract_date_start': date(2025, 1, 1),
            'wage': 5000.0,
        })

        departure = self.env['hr.employee.departure'].create({
            'employee_id': employee_us.id,
            'departure_reason_id': self.departure_reason.id,
            'dismissal_date': date(2026, 1, 19),
        })

        initial_mail_count = self.env['mail.mail'].sudo().search_count([
            ('email_to', '=', 'us@example.com'),
            ('subject', '=', 'Notice Period Details'),
        ])

        with freeze_time("2026-01-20"):
            departure.action_register()

        new_mail_count = self.env['mail.mail'].sudo().search_count([
            ('email_to', '=', 'us@example.com'),
            ('subject', '=', 'Notice Period Details'),
        ])

        self.assertEqual(
            new_mail_count,
            initial_mail_count,
            "Email should not be sent for non-Indian companies"
        )

    def test_fnf_payslip_created_on_register(self):
        """Test FNF payslip is created when action_register is called for Indian departures"""
        departure = self.env['hr.employee.departure'].create({
            'employee_id': self.rahul_emp.id,
            'departure_reason_id': self.departure_reason.id,
            'dismissal_date': date(2026, 1, 19),
        })

        with freeze_time("2026-02-20"):
            action = departure.action_register()

        self.assertEqual(action['res_model'], 'hr.payslip')
        payslip = self.env['hr.payslip'].search(action['domain'])
        self.assertEqual(len(payslip), 1, "Should create one FNF payslip")
        self.assertEqual(payslip.employee_id, self.rahul_emp)

    def test_fnf_payslip_batch_register(self):
        """Test FNF payslips are created for multiple Indian departures at once"""
        departures = self.env['hr.employee.departure'].create([{
            'employee_id': self.rahul_emp.id,
            'departure_reason_id': self.departure_reason.id,
            'dismissal_date': date(2026, 1, 19),
        }, {
            'employee_id': self.jethalal_emp.id,
            'departure_reason_id': self.departure_reason.id,
            'dismissal_date': date(2026, 1, 19),
        }])

        with freeze_time("2026-02-20"):
            action = departures.action_register()

        self.assertEqual(action['res_model'], 'hr.payslip')
        payslips = self.env['hr.payslip'].search(action['domain'])
        self.assertEqual(len(payslips), 2, "Should create two FNF payslips")
        self.assertEqual(payslips.mapped('employee_id'), self.rahul_emp | self.jethalal_emp)
