# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import tagged
from odoo.addons.hr_payroll.tests.common import TestPayrollHolidaysBase

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from freezegun import freeze_time


@tagged('post_install', '-at_install')
class TestTimeoffDefer(TestPayrollHolidaysBase):

    def test_no_defer(self):
        # create payslip -> waiting or draft
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.emp.id,
        })

        # Puts the payslip to draft/waiting
        payslip.compute_sheet()

        # create a time off for our employee, validating it now should not put it as to_defer
        leave = self.env['hr.leave'].create({
            'name': 'Golf time',
            'work_entry_type_id': self.work_entry_type.id,
            'employee_id': self.emp.id,
            'request_date_from': (date.today() + relativedelta(day=13)),
            'request_date_to': (date.today() + relativedelta(day=16)),
        })
        leave.action_approve()

        self.assertNotEqual(leave.payslip_state, 'blocked', 'Leave should not be to defer')

    def test_to_defer(self):
        # create payslip
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.emp.id,
        })

        # Puts the payslip to draft/waiting
        payslip.compute_sheet()
        payslip.action_payslip_done()

        # create a time off for our employee, validating it now should put it as to_defer
        leave = self.env['hr.leave'].create({
            'name': 'Golf time',
            'work_entry_type_id': self.work_entry_type.id,
            'employee_id': self.emp.id,
            'request_date_from': (date.today() + relativedelta(day=13)),
            'request_date_to': (date.today() + relativedelta(day=16)),
        })
        leave.action_approve()
        self.assertEqual(leave.payslip_state, 'blocked', 'Leave should be to defer')

    def test_multi_payslip_defer(self):
        # A leave should only be set to defer if ALL colliding with the time period of the time off are in a done state
        # it should not happen if a payslip for that time period is still in a waiting state

        # create payslip -> waiting
        waiting_payslip = self.env['hr.payslip'].create({
            'employee_id': self.emp.id,
        })
        # payslip -> validated
        done_payslip = self.env['hr.payslip'].create({
            'employee_id': self.emp.id,
        })

        # Puts the waiting payslip to draft/waiting
        waiting_payslip.compute_sheet()
        # Puts the done payslip to the done state
        done_payslip.compute_sheet()
        done_payslip.action_payslip_done()

        # create a time off for our employee, validating it now should not put it as to_defer
        leave = self.env['hr.leave'].create({
            'name': 'Golf time',
            'work_entry_type_id': self.work_entry_type.id,
            'employee_id': self.emp.id,
            'request_date_from': (date.today() + relativedelta(day=13)),
            'request_date_to': (date.today() + relativedelta(day=16)),
        })
        leave.action_approve()

        self.assertNotEqual(leave.payslip_state, 'blocked', 'Leave should not be to defer')

    def test_payslip_paid_past(self):
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.emp.id,
            'date_from': '2022-01-01',
            'date_to': '2022-01-31',
        })

        payslip.compute_sheet()
        self.assertEqual(payslip.state, 'draft')
        self.assertTrue(payslip.line_ids)

        leave_1 = self.env['hr.leave'].with_user(self.vlad).create({
            'name': 'Tennis',
            'work_entry_type_id': self.work_entry_type.id,
            'employee_id': self.emp.id,
            'request_date_from': '2022-01-12',
            'request_date_to': '2022-01-12',
        })
        with freeze_time('2022-02-02'):
            payslip.action_payslip_done()
        self.assertEqual(payslip.state, 'validated')

        leave_1.sudo().action_approve()
        self.assertEqual(leave_1.sudo().payslip_state, 'blocked', 'Leave should be to defer')

        # A Simple User can request a leave if a payslip is paid
        leave_2 = self.env['hr.leave'].with_user(self.vlad).create({
            'name': 'Tennis',
            'work_entry_type_id': self.work_entry_type.id,
            'employee_id': self.emp.id,
            'request_date_from': '2022-01-19',
            'request_date_to': '2022-01-19',
        })
        leave_2.sudo().action_approve()
        self.assertEqual(leave_2.sudo().payslip_state, 'blocked', 'Leave should be to defer')
        try:
            leave_2.with_user(self.env.ref('base.user_admin')).unlink()
        except UserError:
            self.fail('A leave created after payslip validation should be deletable.')

        # Check overlapping periods with no payslip
        leave_3 = self.env['hr.leave'].with_user(self.vlad).create({
            'name': 'Tennis',
            'work_entry_type_id': self.work_entry_type.id,
            'employee_id': self.emp.id,
            'request_date_from': '2022-01-31',
            'request_date_to': '2022-02-01',
        })
        leave_3.sudo().action_approve()
        self.assertEqual(leave_3.sudo().payslip_state, 'blocked', 'Leave should be to defer')

        leave_4 = self.env['hr.leave'].with_user(self.vlad).create({
            'name': 'Tennis',
            'work_entry_type_id': self.work_entry_type.id,
            'employee_id': self.emp.id,
            'request_date_from': '2021-01-31',
            'request_date_to': '2022-01-03',
        })
        leave_4.sudo().action_approve()
        self.assertEqual(leave_4.sudo().payslip_state, 'blocked', 'Leave should be to defer')

    def test_unlink_leave_after_payslip_generation(self):
        """
        Ensures that a request for time off can be deleted after validating
        the payslip for the related period.
        """
        leave = self.env['hr.leave'].with_user(self.vlad).create({
            'name': 'Leave',
            'employee_id': self.emp.id,
            'work_entry_type_id': self.work_entry_type.id,
            'request_date_from': '2022-01-10',
            'request_date_to': '2022-01-10',
        })
        self.assertEqual(leave.state, 'confirm')
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.emp.id,
            'date_from': '2022-01-01',
            'date_to': '2022-01-31',
        })
        payslip.compute_sheet()
        with freeze_time(datetime.now() + timedelta(hours=1)):  # Prevents non-determinism
            payslip.action_payslip_done()
        self.assertEqual(payslip.state, 'validated')
        try:
            leave.with_user(self.env.ref('base.user_admin')).unlink()
        except UserError:
            self.fail('A leave that is not validated should be deletable, even after payslip validation.')

    def test_cancel_payslip_undefer_linked_time_off(self):
        """
        Ensures that cancelling a payslip correctly restores linked time offs to "to compute in next payslip" state over
        the time period covered by the payslip.
        """
        payslip = self.env['hr.payslip'].create({
            'name': 'Donald Payslip',
            'employee_id': self.emp.id,
        })

        # Puts the payslip to draft/waiting
        payslip.compute_sheet()
        payslip.action_payslip_done()

        # create a time off for our employee, validating it now should put it as to_defer
        leave = self.env['hr.leave'].create({
            'name': 'Golf time',
            'work_entry_type_id': self.work_entry_type.id,
            'employee_id': self.emp.id,
            'request_date_from': (date.today() + relativedelta(day=13)),
            'request_date_to': (date.today() + relativedelta(day=16)),
        })
        leave.action_approve()
        self.assertEqual(leave.payslip_state, "blocked")

        payslip.action_payslip_cancel()
        self.assertEqual(leave.payslip_state, "normal")
