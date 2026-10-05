from datetime import date, datetime, timedelta

from odoo.addons.mail.tests.common import MailCommon, mail_new_test_user
from odoo.tests import TransactionCase, tagged, users


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestHrEmployee(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company_us, self.company_be = self.env['res.company'].create([
            {
                'name': 'US Company',
                'country_id': self.env.ref('base.us').id
            },
            {
                'name': 'BE Company',
                'country_id': self.env.ref('base.be').id
            }
        ])
        self.env.user.company_ids |= self.company_us
        self.env.user.company_id = self.company_us  # hr.version retrieves this partner in _get_default_address_id()

    def test_company_context(self):
        # This test is testing a hr_employee/hr_version feature, but must be in l10n_us as we need the l10n_us_ssn constraint.
        # We ensure that the company is passed in the context to the version by creating a belgian employee from the
        # US company with an invalid US SNN. It must not raise a ValidationError.
        be1, be2, us1, be3, us2 = self.env['hr.employee'].with_company(self.company_us).create([
            {'name': 'Belgian Employee 1', 'l10n_us_ssn': '1', 'company_id': self.company_be.id},
            {'name': 'Belgian Employee 2', 'l10n_us_ssn': '2', 'company_id': self.company_be.id},
            {'name': 'US Employee 1', 'l10n_us_ssn': '111111111', 'company_id': self.company_us.id},
            {'name': 'Belgian Employee 3', 'l10n_us_ssn': '3', 'company_id': self.company_be.id},
            {'name': 'US Employee 2', 'l10n_us_ssn': '222222222', 'company_id': self.company_us.id},
        ])
        # We also test that the record are correctly re-ordered
        self.assertEqual(be1.l10n_us_ssn, '1')
        self.assertEqual(be2.l10n_us_ssn, '2')
        self.assertEqual(be3.l10n_us_ssn, '3')
        self.assertEqual(us1.l10n_us_ssn, '111111111')
        self.assertEqual(us2.l10n_us_ssn, '222222222')


@tagged('post_install_l10n', 'post_install', '-at_install', 'mail_track')
class TestLeaveAllocation(MailCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_us = cls.env['res.company'].create({
            'name': 'US Company',
            'country_id': cls.env.ref('base.us').id
        })
        cls.env.user.company_ids |= cls.company_us

        cls.user_us_payroll = mail_new_test_user(
            cls.env,
            company_id=cls.company_us.id,
            country_id=cls.env.ref('base.us').id,
            groups='base.group_user,base.group_partner_manager,hr.group_hr_manager,hr_payroll.group_hr_payroll_user,hr_holidays.group_hr_holidays_manager',
            login='user_us_payroll',
            name='Urusla Udidgood',
        )

        with cls.mock_datetime_and_now(datetime(2025, 12, 1, 10, 0, 0)):
            cls.test_employee = cls.env['hr.employee'].with_company(cls.company_us).create({
                'name': 'Us Employee', 'company_id': cls.company_us.id,
            })

            cls.accrual_entry_type, cls.no_accrual_entry_type = cls.env['hr.work.entry.type'].with_user(cls.user_us_payroll).create([
                {
                    'code': 'youplaboum',
                    'count_as': 'absence',
                    'l10n_us_show_on_payslip': True,
                    'name': 'Test Accrual',
                }, {
                    'code': 'tagadatatsoin',
                    'count_as': 'absence',
                    'l10n_us_show_on_payslip': False,
                    'name': 'Test No Accrual',
                },
            ])

    @users('user_us_payroll')
    def test_accrual(self):
        """ Test accrual computation, which is globally computing number of days
        for a given date, taking into account manual update done for that
        timeframe. """
        now = datetime(2025, 12, 1, 10, 0, 0)
        now_1d = now + timedelta(days=1)
        now_5d = now + timedelta(days=5)
        now_6d = now + timedelta(days=6)
        now_10d = now + timedelta(days=10)
        next_month = datetime(2026, 1, 1, 10, 0, 0)

        with self.mock_datetime_and_now(now):
            alloc = self.env['hr.leave.allocation'].create({
                'date_from': now.date(),
                'date_to': False,
                'employee_id': self.test_employee.id,
                'number_of_days': 2,
                'work_entry_type_id': self.accrual_entry_type.id,
            })
            alloc_2 = self.env['hr.leave.allocation'].create({
                'date_from': now.date(),
                'date_to': False,
                'employee_id': self.test_employee.id,
                'number_of_days': 1.5,
                'work_entry_type_id': self.accrual_entry_type.id,
            })
            alloc_no_accrual = self.env['hr.leave.allocation'].create({
                'date_from': now.date(),
                'date_to': False,
                'employee_id': self.test_employee.id,
                'number_of_days': 2,
                'work_entry_type_id': self.no_accrual_entry_type.id,
            })
            all_alloc = alloc + alloc_2 + alloc_no_accrual
            all_alloc.action_approve()
            self.flush_tracking()

        # Five days later: we check accrual: sum of first allocation on accrual types
        with self.mock_datetime_and_now(now_5d):
            hours_count = alloc._l10n_us_get_total_allocated(now_5d.date())
        self.assertEqual(hours_count, 16, 'Two work days')
        with self.mock_datetime_and_now(now_5d):
            hours_count = alloc_no_accrual._l10n_us_get_total_allocated(now_5d.date())
        self.assertEqual(hours_count, 0, 'Accrual counted even if no use (aka no filtering in computation)')
        with self.mock_datetime_and_now(now_5d):
            hours_count = alloc_2._l10n_us_get_total_allocated(now_5d.date())
        self.assertEqual(hours_count, 12, 'One and an half work days')
        with self.mock_datetime_and_now(now_5d):
            hours_count = all_alloc._l10n_us_get_total_allocated(now_5d.date())
        self.assertEqual(hours_count, 28, 'Should sum everything')

        # Changed allocations in 1 and 6 days
        with self.mock_datetime_and_now(now_1d):
            alloc.write({
                'number_of_days': 5,
            })
            self.flush_tracking()
        with self.mock_datetime_and_now(now_6d):
            alloc.write({
                'number_of_days': 1,
            })
            self.flush_tracking()

        hours_count = alloc._l10n_us_get_total_allocated(now_5d.date())
        self.assertEqual(hours_count, 40, 'Five work days')
        hours_count = alloc._l10n_us_get_total_allocated(now_6d.date())
        self.assertEqual(hours_count, 8, 'One work days')

        # Add some allocations, and check payslips afterwards to check batch computation
        with self.mock_datetime_and_now(now_10d):
            alloc_2.write({
                'number_of_days': 5.5,
            })
            self.flush_tracking()
        with self.mock_datetime_and_now(next_month):
            new_alloc = self.env['hr.leave.allocation'].create({
                'date_from': next_month.date(),
                'date_to': False,
                'employee_id': self.test_employee.id,
                'number_of_days': 4,
                'work_entry_type_id': self.accrual_entry_type.id,
            })
            new_alloc.action_approve()
            self.flush_tracking()
        with self.mock_datetime_and_now(now_5d):
            hours_count = all_alloc._l10n_us_get_total_allocated(next_month.date() - timedelta(days=1))
        self.assertEqual(hours_count, 52,
                         'Sum: alloc is 1 day, alloc_2 is 5.5 days, alloc_no_accrual is 2 days, total is 8.5 days -> 68 hours (*8)')

        # Create a leave request, just to check payslip hours computation
        with self.mock_datetime_and_now(now_10d):
            self.env['hr.leave'].create([
                {
                    'employee_id': self.test_employee.id,
                    'name': 'Test Leave',
                    'request_date_from': now_5d.date(),
                    'request_date_to': now_5d.date() + timedelta(days=2),
                    'work_entry_type_id': self.accrual_entry_type.id,
                }, {
                    'employee_id': self.test_employee.id,
                    'name': 'Test Leave',
                    'request_date_from': now_10d.date(),
                    'request_date_to': now_10d.date() + timedelta(days=2),
                    'work_entry_type_id': self.accrual_entry_type.id,
                }
            ])
            self.flush_tracking()

        # Test with payslips (hehe, slip)
        month_payslip = self.env["hr.payslip"].create({
            'date_from': date(2025, 12, 1),
            'date_to': date(2025, 12, 31),
            'employee_id': self.test_employee.id,
            'name': "This Month Payslip",
        })
        month_leave_lines = month_payslip._l10n_us_get_leave_lines()
        self.assertEqual(month_leave_lines[0]['accrual'], 52,
                         'Sum: alloc is 1 day, alloc_2 is 5.5 days, alloc_no_accrual is not counted, total is 6.5 days -> 52 hours (*8)')
        self.assertEqual(month_leave_lines[0]['balance'], 28,
                         'Remove leaves (24h)')

        next_month_payslip = self.env["hr.payslip"].create({
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 1, 31),
            'employee_id': self.test_employee.id,
            'name': "Next Month Payslip",
        })
        month_leave_lines = next_month_payslip._l10n_us_get_leave_lines()
        self.assertEqual(month_leave_lines[0]['accrual'], 32,
                         'This month has only new_alloc, 4 days')
        self.assertEqual(month_leave_lines[0]['balance'], 60)
