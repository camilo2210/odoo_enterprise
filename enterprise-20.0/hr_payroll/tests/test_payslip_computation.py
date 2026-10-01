# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.rrule import rrule, DAILY
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from odoo.fields import Date, Command
from odoo.tests import Form, tagged
from odoo.exceptions import UserError
from odoo.addons.hr_payroll.tests.common import TestPayslipContractBase


@tagged('payslip_computation')
@tagged('at_install', '-post_install')  # LEGACY at_install
class TestPayslipComputation(TestPayslipContractBase):

    @classmethod
    def setUpClass(cls):
        super(TestPayslipComputation, cls).setUpClass()

        cls.env.user.group_ids |= cls.env.ref('hr_payroll.group_hr_payroll_manager')
        cls.richard_emp.write({'review_state': '1_reviewed'})
        cls.richard_payslip = cls.env['hr.payslip'].create({
            'name': 'Payslip of Richard',
            'employee_id': cls.richard_emp.id,
            'version_id': cls.contract_cdi.id,  # wage = 5000 => average/day (over 3months/13weeks): 230.77
            'struct_id': cls.developer_pay_structure.id,
            'date_from': date(2016, 1, 1),
            'date_to': date(2016, 1, 31)
        })
        cls.richard_emp.resource_calendar_id = cls.contract_cdi.resource_calendar_id

        cls.richard_payslip_quarter = cls.env['hr.payslip'].create({
            'name': 'Payslip of Richard Quarter',
            'employee_id': cls.richard_emp.id,
            'version_id': cls.contract_cdi.id,
            'struct_id': cls.developer_pay_structure.id,
            'date_from': date(2016, 1, 1),
            'date_to': date(2016, 3, 31)
        })
        # To avoid having is_paid = False in some tests, as all the records are created on the
        # same transaction which is quite unlikely supposed to happen in real conditions
        worked_days = (cls.richard_payslip + cls.richard_payslip_quarter).worked_days_line_ids
        worked_days._compute_is_paid()
        worked_days.flush_model(['is_paid'])

    def test_unpaid_amount(self):
        self.richard_payslip.compute_sheet()
        wage = self.richard_payslip._get_contract_wage()
        unpaid_amount = wage - self.richard_payslip._get_line_values(['BASIC'])['BASIC'][self.richard_payslip.id]['total']
        self.assertAlmostEqual(unpaid_amount, 0, places=2, msg="It should be paid the full wage")

        self.env['resource.calendar.leaves'].create({
            'name': 'Doctor Appointment',
            'date_from': datetime.strptime('2016-01-11 07:00:00', '%Y-%m-%d %H:%M:%S'),
            'date_to': datetime.strptime('2016-01-11 18:00:00', '%Y-%m-%d %H:%M:%S'),
            'resource_id': self.richard_emp.resource_id.id,
            'calendar_id': self.richard_emp.resource_calendar_id.id,
            'work_entry_type_id': self.work_entry_type_unpaid.id,
            'count_as': 'absence',
        })

        self.richard_payslip._compute_worked_days_line_ids()
        self.richard_payslip.compute_sheet()
        # TBE: In master the Monetary field were not rounded because the currency_id wasn't computed yet.
        # The test was incorrect using the value 238.09, with 238.11 it is ok
        unpaid_amount = wage - self.richard_payslip._get_line_values(['BASIC'])['BASIC'][self.richard_payslip.id]['total']
        self.assertAlmostEqual(unpaid_amount, 238.11, delta=0.01, msg="It should be paid 238.11 less")

    def test_worked_days_amount_with_unpaid(self):
        self.env['resource.calendar.leaves'].create({
            'name': 'Doctor Appointment',
            'date_from': datetime.strptime('2016-01-11 07:00:00', '%Y-%m-%d %H:%M:%S'),
            'date_to': datetime.strptime('2016-01-11 18:00:00', '%Y-%m-%d %H:%M:%S'),
            'resource_id': self.richard_emp.resource_id.id,
            'calendar_id': self.richard_emp.resource_calendar_id.id,
            'work_entry_type_id': self.work_entry_type_leave.id,
            'count_as': 'absence',
        })

        self.env['resource.calendar.leaves'].create({
            'name': 'Unpaid Doctor Appointment',
            'date_from': datetime.strptime('2016-01-21 07:00:00', '%Y-%m-%d %H:%M:%S'),
            'date_to': datetime.strptime('2016-01-21 18:00:00', '%Y-%m-%d %H:%M:%S'),
            'resource_id': self.richard_emp.resource_id.id,
            'calendar_id': self.richard_emp.resource_calendar_id.id,
            'work_entry_type_id': self.work_entry_type_unpaid.id,
            'count_as': 'absence',
        })

        self.richard_payslip._compute_worked_days_line_ids()
        work_days = self.richard_payslip.worked_days_line_ids

        self.richard_payslip.compute_sheet()
        self.assertAlmostEqual(sum(work_days.mapped('amount')), self.richard_payslip._get_line_values(['BASIC'])['BASIC'][self.richard_payslip.id]['total'])

        leave_line = work_days.filtered(lambda l: l.code == self.work_entry_type_leave.code)
        self.assertAlmostEqual(leave_line.amount, 238.11, delta=0.01, msg="His paid time off must be paid 238.11")

        extra_attendance_line = work_days.filtered(lambda l: l.code == self.work_entry_type_unpaid.code)
        self.assertAlmostEqual(extra_attendance_line.amount, 0.0, places=2, msg="His unpaid time off must be paid 0.")

        attendance_line = work_days.filtered(lambda l: l.code == self.env.ref('hr_work_entry.generic_work_entry_type_attendance').code)
        self.assertAlmostEqual(attendance_line.amount, 4524.11, delta=0.01, msg="His attendance must be paid 4524.11")

    def test_worked_days_with_unpaid(self):
        self.contract_cdi.resource_calendar_id = self.calendar_38h
        self.richard_emp.resource_calendar_id = self.calendar_38h

        # Create 2 hours upaid leave every day during 2 weeks
        for day in rrule(freq=DAILY, byweekday=[0, 1, 2, 3, 4], count=10, dtstart=datetime(2016, 2, 8)):
            start = day + timedelta(hours=13.6)
            end = day + timedelta(hours=15.6)
            self.env['resource.calendar.leaves'].create({
                'name': 'Unpaid Leave',
                'date_from': start,
                'date_to': end,
                'resource_id': self.richard_emp.resource_id.id,
                'calendar_id': self.richard_emp.resource_calendar_id.id,
                'work_entry_type_id': self.work_entry_type_unpaid.id,
                'count_as': 'absence',
            })

        self.richard_payslip_quarter._compute_worked_days_line_ids()
        work_days = self.richard_payslip_quarter.worked_days_line_ids

        leave_line = work_days.filtered(lambda l: l.code == self.env.ref('hr_work_entry.generic_work_entry_type_attendance').code)
        self.assertAlmostEqual(leave_line.number_of_days, 62.5, places=2)

        extra_attendance_line = work_days.filtered(lambda l: l.code == self.work_entry_type_unpaid.code)
        self.assertAlmostEqual(extra_attendance_line.number_of_days, 2.5, places=2)

    def test_worked_days_16h_with_unpaid(self):
        self.contract_cdi.resource_calendar_id = self.calendar_16h
        self.richard_emp.resource_calendar_id = self.calendar_16h

        # Create 2 hours upaid leave every Thursday Evening during 5 weeks
        for day in rrule(freq=DAILY, byweekday=3, count=5, dtstart=datetime(2016, 2, 4)):
            start = day + timedelta(hours=12.5)
            end = day + timedelta(hours=14.5)
            self.env['resource.calendar.leaves'].create({
                'name': 'Unpaid Leave',
                'date_from': start,
                'date_to': end,
                'resource_id': self.richard_emp.resource_id.id,
                'calendar_id': self.richard_emp.resource_calendar_id.id,
                'work_entry_type_id': self.work_entry_type_unpaid.id,
                'count_as': 'absence',
            })

        self.richard_payslip_quarter._compute_worked_days_line_ids()
        work_days = self.richard_payslip_quarter.worked_days_line_ids

        leave_line = work_days.filtered(lambda l: l.code == self.env.ref('hr_work_entry.generic_work_entry_type_attendance').code)
        self.assertAlmostEqual(leave_line.number_of_days, 49.5, places=2)

        extra_attendance_line = work_days.filtered(lambda l: l.code == self.work_entry_type_unpaid.code)
        self.assertAlmostEqual(extra_attendance_line.number_of_days, 2.5, places=2)

    def test_worked_days_38h_friday_with_unpaid(self):
        self.contract_cdi.resource_calendar_id = self.calendar_38h_friday_light
        self.richard_emp.resource_calendar_id = self.calendar_38h_friday_light

        # Create 4 hours (all work day) upaid leave every Friday during 5 weeks
        for day in rrule(freq=DAILY, byweekday=4, count=5, dtstart=datetime(2016, 2, 4)):
            start = day + timedelta(hours=7)
            end = day + timedelta(hours=11)
            self.env['resource.calendar.leaves'].create({
                'name': 'Unpaid Leave',
                'date_from': start,
                'date_to': end,
                'resource_id': self.richard_emp.resource_id.id,
                'calendar_id': self.richard_emp.resource_calendar_id.id,
                'work_entry_type_id': self.work_entry_type_unpaid.id,
                'count_as': 'absence',
            })

        self.richard_payslip_quarter._compute_worked_days_line_ids()
        work_days = self.richard_payslip_quarter.worked_days_line_ids

        leave_line = work_days.filtered(lambda l: l.code == self.env.ref('hr_work_entry.generic_work_entry_type_attendance').code)
        self.assertAlmostEqual(leave_line.number_of_days, 62.5, places=2)

        extra_attendance_line = work_days.filtered(lambda l: l.code == self.work_entry_type_unpaid.code)
        self.assertAlmostEqual(extra_attendance_line.number_of_days, 2.5, places=2)

    def test_sum_category(self):
        self.richard_payslip.compute_sheet()
        self.richard_payslip.action_payslip_done()

        self.richard_payslip2 = self.env['hr.payslip'].create({
            'employee_id': self.richard_emp.id,
            'version_id': self.contract_cdi.id,
            'struct_id': self.developer_pay_structure.id,
            'date_from': date(2016, 1, 1),
            'date_to': date(2016, 1, 31)
        })
        self.richard_payslip2.compute_sheet()
        self.assertEqual(3010.13, self.richard_payslip2.line_ids.filtered(lambda x: x.code == 'SUMALW').total)

    def test_payslip_generation_with_extra_work(self):
        # /!\ this is in the weekend (Sunday) => no calendar attendance at this time
        start = datetime(2015, 11, 1, 10, 0, 0)
        end = datetime(2015, 11, 1, 17, 0, 0)

        self.env['hr.leave'].create({
            'name': 'Extra',
            'employee_id': self.richard_emp.id,
            'work_entry_type_id': self.work_entry_type.id,
            'date_from': start,
            'date_to': end,
            'request_date_from': start,
            'request_date_to': end,
            'request_hour_from': 10,
            'request_hour_to': 17,
            'number_of_days': 1,
        })

        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': Date.to_string(start),
            'date_end': Date.to_string(end + relativedelta(days=1)),
            'structure_id': self.developer_pay_structure.id,
        })

        payslip_run._generate_payslips()

        payslip = self.env['hr.payslip'].search([
            ('employee_id', '=', self.richard_emp.id),
            ('payslip_run_id', '=', payslip_run.id),
        ])
        work_line = payslip.worked_days_line_ids.filtered(lambda l: l.work_entry_type_id.code == '002.00')  # From default calendar.attendance
        extra_work_line = payslip.worked_days_line_ids.filtered(lambda l: l.work_entry_type_id == self.work_entry_type)

        self.assertTrue(work_line, "It should have a work line in the payslip")
        self.assertTrue(extra_work_line, "It should have an extra work line in the payslip")
        self.assertEqual(work_line.number_of_hours, 8.0, "It should have 8 hours of work")  # Monday
        self.assertEqual(extra_work_line.number_of_hours, 7.0, "It should have 7 hours of extra work")  # Sunday

    def test_payslip_generation_with_overtime_work_rate(self):
        """ Test the computation of overtime amount in the payslip as per rate. """
        start = datetime(2024, 12, 16, 18, 0, 0)
        end = datetime(2024, 12, 16, 22, 0, 0)
        self.env['hr.leave'].create({
            'name': 'Overtime Work',
            'employee_id': self.richard_emp.id,
            'work_entry_type_id': self.work_entry_type_overtime_duty.id,
            'date_from': start,
            'date_to': end,
            'request_date_from': start,
            'request_date_to': end,
            'request_hour_from': 18,
            'request_hour_to': 22,
            'number_of_days': 1,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.richard_emp.id,
            'version_id': self.contract_cdi.id,
            'date_from': date(2024, 12, 1),
            'date_to': date(2024, 12, 31),
        })
        payslip.compute_sheet()
        overtime_line = payslip.worked_days_line_ids.filtered(lambda l: l.work_entry_type_id == self.work_entry_type_overtime_duty)
        expected_hours = 4.0
        expected_amount = 64.93
        self.assertEqual(overtime_line.number_of_hours, expected_hours, "Overtime hours mismatch")
        self.assertAlmostEqual(overtime_line.amount, expected_amount, delta=0.01, msg="Overtime amount calculation mismatch")

    def test_payslip_without_contract(self):
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.richard_emp.id,
            'date_from': date(2015, 11, 1),
            'date_to': date(2015, 11, 30)
        })
        self.assertTrue(payslip.version_id)
        payslip.version_id = False
        self.assertEqual(payslip._get_contract_wage(), 0, "It should have a default wage of 0")
        self.assertEqual(payslip.basic_wage, 0, "It should have a default wage of 0")
        self.assertEqual(payslip.gross_wage, 0, "It should have a default wage of 0")
        self.assertEqual(payslip.net_wage, 0, "It should have a default wage of 0")

    def test_payslip_with_salary_attachment(self):
        #Create multiple salary attachments, some running, some closed
        self.env['hr.salary.attachment'].create([
            {
                'employee_id': self.richard_emp.id,
                'amount': 150,
                'salary_rule_id': self.child_support_rule.id,
                'date_start': date(2016, 1, 1),
                'description': 'Child Support',
            },
            {
                'employee_id': self.richard_emp.id,
                'amount': 1000,
                'paid_amount': 1000,
                'salary_rule_id': self.assign_salary_rule.id,
                'date_start': date(2015, 1, 1),
                'date_end': date(2015, 4, 1),
                'description': 'Unpaid fine',
                'state': '2_close',
            },
        ])

        car_accident = self.env['hr.salary.attachment'].create({
                'employee_id': self.richard_emp.id,
                'amount': 1500,
                'paid_amount': 1450,
                'salary_rule_id': self.attach_salary_rule.id,
                'date_start': date(2016, 1, 1),
                'description': 'Car accident',
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.richard_emp.id,
            'version_id': self.contract_cdi.id,
            'date_from': date(2016, 1, 1),
            'date_to': date(2016, 1, 31)
        })
        input_lines = payslip.input_line_ids
        self.assertTrue(input_lines.filtered(lambda r: r.code == 'CHILD_SUPPORT'), 'There should be an input line for child support.')
        self.assertTrue(input_lines.filtered(lambda r: r.code == 'ATTACH_SALARY'), 'There should be an input line for the car accident.')
        self.assertTrue(input_lines.filtered(lambda r: r.code == 'ATTACH_SALARY').amount <= 50, 'The amount for the car accident input line should be 50 or less.')
        self.assertFalse(input_lines.filtered(lambda r: r.code == 'ASSIG_SALARY'), 'There should not be an input line for the unpaid fine.')
        payslip.compute_sheet()
        lines = payslip.line_ids
        self.assertTrue(lines.filtered(lambda r: r.code == 'CHILD_SUPPORT'), 'There should be a salary line for child support.')
        self.assertTrue(lines.filtered(lambda r: r.code == 'ATTACH_SALARY'), 'There should be a salary line for car accident.')
        payslip.action_payslip_done()
        payslip.action_payslip_paid()
        self.assertEqual(car_accident.state, '2_close', 'The Payslip adjustment should be completed.')

    def test_payslip_with_multiple_input_same_type(self):
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.richard_emp.id,
            'version_id': self.contract_cdi.id,
            'date_from': date(2016, 1, 1),
            'date_to': date(2016, 1, 31)
        })
        self.env['hr.payslip.input'].create([
            {
                'payslip_id': payslip.id,
                'sequence': 1,
                'salary_rule_id': self.attach_salary_rule.id,
                'amount': 100,
                'version_id': self.contract_cdi.id
            },
            {
                'payslip_id': payslip.id,
                'sequence': 2,
                'salary_rule_id': self.attach_salary_rule.id,
                'amount': 200,
                'version_id': self.contract_cdi.id
            },
        ])
        payslip.compute_sheet()
        lines = payslip.line_ids
        self.assertEqual(len(lines.filtered(lambda r: r.code == 'BASIC')), 1)

    def test_payslip_with_multiple_input_same_type_aggregations(self):
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.richard_emp.id,
            'version_id': self.contract_cdi.id,
            'date_from': date(2016, 1, 1),
            'date_to': date(2016, 1, 31)
        })
        self.env['hr.payslip.input'].create([
            {
                'payslip_id': payslip.id,
                'sequence': 1,
                'salary_rule_id': self.deduction_rule.id,
                'amount': 300,
                'version_id': self.contract_cdi.id,
            },
            {
                'payslip_id': payslip.id,
                'sequence': 1,
                'salary_rule_id': self.deduction_rule.id,
                'amount': 200,
                'version_id': self.contract_cdi.id,
            },
        ])
        self.developer_pay_structure.write({
            'rule_ids': [
            (0, 0, {
                'name': 'Test 1',
                'sequence': 1000000,
                'code': 'TEST1',
                'category_ids': [(4, self.env.ref('hr_payroll.ALW').id)],
                'amount_select': 'code',
                'amount_python_compute': 'result = inputs["DEDUCTION"].amount',
            }), (0, 0, {
                'name': 'Test 2',
                'sequence': 1000000,
                'code': 'TEST2',
                'category_ids': [(4, self.env.ref('hr_payroll.ALW').id)],
                'amount_select': 'code',
                'amount_python_compute': 'result = inputs["DEDUCTION"][0].amount + inputs["DEDUCTION"][1].amount',
            }), (0, 0, {
                'name': 'Test 3',
                'sequence': 1000000,
                'code': 'TEST3',
                'category_ids': [(4, self.env.ref('hr_payroll.ALW').id)],
                'amount_select': 'code',
                'amount_python_compute': 'result = inputs["DEDUCTION"][0].amount',
            }),
        ]})
        payslip.compute_sheet()
        assert(payslip.line_ids.filtered(lambda r: r.code == 'TEST1').total == 500.00)
        assert(payslip.line_ids.filtered(lambda r: r.code == 'TEST2').total == 500.00)
        assert(payslip.line_ids.filtered(lambda r: r.code == 'TEST3').total == 300.00)

    def test_payslip_with_multiple_input_same_type_no_matching_rule_aggregations(self):
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.richard_emp.id,
            'version_id': self.contract_cdi.id,
            'date_from': date(2016, 1, 1),
            'date_to': date(2016, 1, 31)
        })
        input_rule = self.env['hr.salary.rule'].create({
            'name': 'ABCD',
            'code': 'ABCD',
            'amount_select': 'code',
            'amount_python_compute': 'result = inputs["ABCD"].amount',
            'struct_ids': [(4, self.developer_pay_structure.id)],
            'category_ids': [(4, self.env.ref('hr_payroll.ALW').id)],
        })
        self.env['hr.payslip.input'].create([
            {
                'payslip_id': payslip.id,
                'sequence': 1,
                'salary_rule_id': input_rule.id,
                'amount': 300,
                'version_id': self.contract_cdi.id,
            },
            {
                'payslip_id': payslip.id,
                'sequence': 2,
                'salary_rule_id': input_rule.id,
                'amount': 200,
                'version_id': self.contract_cdi.id,
            },
        ])
        self.developer_pay_structure.write({'rule_ids': [
            (0, 0, {
                'name': 'Non matching code rule',
                'sequence': 5,
                'code': 'EFGH',
                'category_ids': [(4, self.env.ref('hr_payroll.COMP').id)],
                'amount_select': 'code',
                'amount_python_compute': 'result = inputs["ABCD"].amount',
            })]})
        payslip.compute_sheet()
        self.assertEqual(payslip.line_ids.filtered(lambda r: r.code == 'EFGH').total, 500.00)

    def test_payslip_multiple_inputs_and_attachments_same_type(self):
        self.env['hr.salary.attachment'].create([
            {
                'employee_id': self.richard_emp.id,
                'amount': 100,
                'salary_rule_id': self.attach_salary_rule.id,
                'date_start': date(2016, 1, 1),
                'description': 'Some attachment',
            },
            {
                'employee_id': self.richard_emp.id,
                'amount': 200,
                'salary_rule_id': self.attach_salary_rule.id,
                'date_start': date(2016, 1, 1),
                'description': 'Another attachment',
            },
        ])

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.richard_emp.id,
            'version_id': self.contract_cdi.id,
            'date_from': date(2016, 1, 1),
            'date_to': date(2016, 1, 31),
        })

        with Form(payslip) as payslip_form:
            payslip_form.input_line_ids.remove(0)  # remove merged input of attachments and use 2 inputs instead
            with payslip_form.input_line_ids.new() as line:
                line.salary_rule_id = self.attach_salary_rule
                line.amount = 100
            with payslip_form.input_line_ids.new() as line:
                line.salary_rule_id = self.attach_salary_rule
                line.amount = 200

        payslip.compute_sheet()
        payslip.action_payslip_done()
        payslip.action_payslip_paid()

        self.assertEqual(sum(s.paid_amount for s in payslip.salary_attachment_ids), 100 + 200)

    def test_defaultdict_get(self):
        # defaultdict.get(key) returns None if the key doesn't exist instead of default factory value
        # which could lead to a traceback
        self.developer_pay_structure.rule_ids.filtered(lambda r: r.code == "NET").amount_python_compute = "result = categories['BASIC'] + categories['ALW'] + categories['DED'] + categories.get('TEST')"
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.richard_emp.id,
            'date_from': date(2015, 11, 1),
            'date_to': date(2015, 11, 30)
        })
        payslip.compute_sheet()

    def test_payslip_warning_message_without_duration_dates(self):
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.richard_emp.id,
            'version_id': self.contract_cdi.id,
            'date_from': date(2016, 2, 1),
            'date_to': date(2016, 2, 29)
        })
        payslip.compute_sheet()  # To make sure the net wage is computed to avoid zero/negative payslip issue.
        self.assertFalse(payslip.issues)
        payslip_form = Form(payslip)
        payslip_form.date_to = False  # Manually removing the end_date of the payslip doesn't cause any issues.
        self.assertFalse(payslip.issues)

    def test_rule_without_category(self):
        """Test that salary rules without category can be created and computed correctly"""
        # Create a salary rule without category
        bonus_rule = self.env['hr.salary.rule'].create({
            'name': 'Special Bonus',
            'sequence': 200,
            'amount_select': 'fix',
            'amount_fix': 500.0,
            'code': 'BONUS',
            'struct_ids': [(4, self.developer_pay_structure.id)],
        })
        self.assertFalse(bonus_rule.category_ids, "Rule should be created without a category")

        # Create and compute a payslip with this rule
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.richard_emp.id,
            'version_id': self.contract_cdi.id,
            'struct_id': self.developer_pay_structure.id,
            'date_from': date(2016, 1, 1),
            'date_to': date(2016, 1, 31)
        })
        payslip.compute_sheet()

        # Verify the bonus rule appears in the payslip lines
        bonus_line = payslip.line_ids.filtered(lambda l: l.code == 'BONUS')
        self.assertTrue(bonus_line, "Bonus rule should appear in payslip lines")
        self.assertEqual(bonus_line.total, 500.0, "Bonus amount should be correctly computed")
        self.assertFalse(bonus_line.category_ids, "Bonus line should have no category")

    def test_zero_or_negative_payslip(self):
        # Creating new employee with new pay structures without benefits/allowances to ensure zero value payslip.
        self.structure_type_developer = self.env['hr.payroll.structure.type'].create({
            'name': 'Employee',
        })
        self.structure_developer = self.env['hr.payroll.structure'].create({
            'name': 'Developer Structure',
            'type_id': self.structure_type_developer.id
        })
        self.structure_type_developer.default_struct_id = self.structure_developer.id

        self.rambo_emp = self.env['hr.employee'].create({
            'name': 'Rambo',
            'date_version': Date.to_date('2018-01-01'),
            'contract_date_start': Date.to_date('2018-01-01'),
            'contract_date_end': Date.today() + relativedelta(years=2),
            'wage': 0,
            'structure_type_id': self.structure_type_developer.id,
        })
        self.rambo_bank_acc = self.env['res.partner.bank'].create({
            'account_number': 'BE00123123123123',
            "partner_id": self.rambo_emp.work_contact_id.id,
            "allow_out_payment": True
        })
        self.rambo_emp.bank_account_ids = [Command.link(self.rambo_bank_acc.id)]
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.rambo_emp.id,
            'version_id': self.rambo_emp.version_id.id,
            'date_from': date(2018, 3, 1),
            'date_to': date(2018, 3, 31)
        })
        payslip.compute_sheet()
        issues = payslip.issues
        self.assertTrue(
            any(
                issue["message"] == "Net pay is zero or negative."
                for issue in issues.values()
            )
        )

    def test_duplicate_payslips_duplicate_deletion(self):
        """ If there are multiple duplciate payslips(in this case 2 payslip), And if we delete any one payslips
            duplicate warning should not appear on the original payslip """
        rich_payslip1 = self.env['hr.payslip'].create({
            'employee_id': self.richard_emp.id,
            'version_id': self.contract_cdi.id,
            'struct_id': self.developer_pay_structure.id,
            'date_from': date(2016, 5, 1),
            'date_to': date(2016, 5, 31),
        })
        self.assertNotIn('Duplicate payslips', str(rich_payslip1.issues))
        rich_payslip2 = self.env['hr.payslip'].create({
            'employee_id': self.richard_emp.id,
            'version_id': self.contract_cdi.id,
            'struct_id': self.developer_pay_structure.id,
            'date_from': date(2016, 5, 1),
            'date_to': date(2016, 5, 31),
        })
        rich_payslip1._compute_issues()
        self.assertIn('Duplicate payslips', str(rich_payslip1.issues))
        self.assertIn('Duplicate payslips', str(rich_payslip2.issues))
        rich_payslip2.unlink()
        self.assertNotIn('Duplicate payslips', str(rich_payslip1.issues))

    def test_payslip_run_counts_issue_totals(self):
        """The pay run aggregates must sum warnings/errors across all slips."""
        today = Date.today()

        test_emp1 = self.env['hr.employee'].create({'name': 'Temp 1'})
        test_emp1.create_version({
            'date_version': today - relativedelta(months=3),
            'contract_date_start': today - relativedelta(months=3),
            'structure_type_id': self.structure_type.id,
        })

        test_emp2 = self.env['hr.employee'].create({'name': 'Temp 2'})
        test_emp2.create_version({
            'date_version': today - relativedelta(months=3),
            'contract_date_start': today - relativedelta(months=3),
            'structure_type_id': self.structure_type.id,
        })

        payslip_run = self.env['hr.payslip.run'].create({
            'name': 'Issue Totals',
            'date_start': today,
            'date_end': today + relativedelta(day=31),
            'structure_id': self.developer_pay_structure.id,
        })

        payslip_run._generate_payslips()

        slips = payslip_run.slip_ids
        self.assertEqual(len(slips), 4)

        slip0, slip1, slip2, slip3 = slips

        slip0.write({'warning_count': 2, 'error_count': 0})
        slip1.write({'warning_count': 0, 'error_count': 2})
        slip2.write({'warning_count': 1, 'error_count': 2})
        slip3.write({'warning_count': 0, 'error_count': 0})

        payslip_run._compute_payslips_with_warnings_and_errors()

        self.assertEqual(payslip_run.payslips_with_warnings, 3)
        self.assertEqual(payslip_run.payslips_with_errors, 4)

    def test_out_of_contract_worked_days(self):
        self.contract_cdi.write({
            'contract_date_start': datetime.strptime('2025-06-15', '%Y-%m-%d'),
            'contract_date_end': datetime.strptime('2025-07-15', '%Y-%m-%d'),
        })
        payslips = self.env['hr.payslip'].create([
            {
                # Before contract
                'employee_id': self.richard_emp.id,
                'version_id': self.contract_cdi.id,
                'struct_id': self.developer_pay_structure.id,
                'date_from': date(2025, 2, 1),
                'date_to': date(2025, 2, 28),
            },
            {
                # Partial overlap
                'employee_id': self.richard_emp.id,
                'version_id': self.contract_cdi.id,
                'struct_id': self.developer_pay_structure.id,
                'date_from': date(2025, 6, 1),
                'date_to': date(2025, 6, 30),
            },
            {
                # After contract
                'employee_id': self.richard_emp.id,
                'version_id': self.contract_cdi.id,
                'struct_id': self.developer_pay_structure.id,
                'date_from': date(2025, 11, 1),
                'date_to': date(2025, 11, 30),
            },
        ])
        payslips._compute_worked_days_line_ids()
        expectations = [(20.0, 140.0), (10.0, 70.0), (20.0, 140.0)]
        out_of_contract_code = self.env.ref('hr_work_entry.generic_hr_work_entry_type_out_of_contract').code
        for payslip, (exp_days, exp_hours) in zip(payslips, expectations):
            line = payslip.worked_days_line_ids.filtered(lambda l: l.code == out_of_contract_code)
            self.assertAlmostEqual(line.number_of_days, exp_days, places=2, msg=f"Wrong days for {payslip.name}")
            self.assertAlmostEqual(line.number_of_hours, exp_hours, places=2, msg=f"Wrong hours for {payslip.name}")

    def test_payslip_fully_flexible_employee_without_calendar(self):
        """
        Test that payslips and worked days lines are computed for fully flexible employees.
        """
        flexible_calendar = self.env['resource.calendar'].create({
            'name': 'Fully Flexible Calendar',
            'calendar_type': 'undefined',
            'attendance_ids': [],
        })
        flexible_structure = self.env['hr.payroll.structure'].create({
            'name': 'Flexible Employee Structure',
            'type_id': self.structure_type.id,
            'use_worked_day_lines': True,
        })
        flexible_employee = self.env['hr.employee'].create({
            'name': 'Fully Flexible Employee',
            'company_id': self.env.company.id,
            'resource_calendar_id': flexible_calendar.id,
        })
        flexible_contract = self.env['hr.version'].create({
            'name': 'Contract - Fully Flexible Employee',
            'employee_id': flexible_employee.id,
            'contract_date_start': date(2024, 1, 1),
            'date_version': date(2024, 1, 1),
            'wage': 5000.0,
            'structure_type_id': flexible_structure.type_id.id,
            'resource_calendar_id': flexible_calendar.id,
        })
        # Create a payslip for the flexible employee
        payslip = self.env['hr.payslip'].create({
            'employee_id': flexible_employee.id,
            'version_id': flexible_contract.id,
            'struct_id': flexible_structure.id,
            'date_from': date(2024, 1, 1),
            'date_to': date(2024, 1, 31),
        })
        payslip._compute_worked_days_line_ids()
        self.assertTrue(
            payslip.worked_days_line_ids,
            "Worked days lines should be generated for fully flexible employees"
        )
        payslip.compute_sheet()
        self.assertTrue(
            payslip.line_ids,
            "Payslip lines should be generated for fully flexible employees"
        )
        self.assertEqual(payslip.basic_wage, 5000.0,
                     "Basic wage should equal contract wage for flexible employees")
        self.assertGreater(payslip.gross_wage, 0,
                        "Gross wage should be computed for flexible employees")
        self.assertAlmostEqual(payslip.net_wage, 5000.0, places=2,
                          msg="Net wage computation changed for flexible employees - possible regression")

    def test_public_holiday_worked_days_calculation(self):
        """
        Ensure that public holidays are correctly handled when calculating the amount of the worked days lines.
        We expect the attendance line + holiday line to amount to the wage of the employee, nothing more or less than that.
        """
        self.env['resource.calendar.leaves'].create({
            'name': 'Public Holiday',
            'date_from': datetime.strptime('2016-01-11 07:00:00', '%Y-%m-%d %H:%M:%S'),
            'date_to': datetime.strptime('2016-01-11 18:00:00', '%Y-%m-%d %H:%M:%S'),
            'calendar_id': self.richard_emp.resource_calendar_id.id,
            'work_entry_type_id': self.work_entry_type_leave.id,
            'count_as': 'absence',
        })

        self.richard_payslip._compute_worked_days_line_ids()
        self.richard_payslip.compute_sheet()
        self.assertRecordValues(
            self.richard_payslip.worked_days_line_ids,
            [{
                'code': 'LEAVETEST100',
                'number_of_days': 1.0,
                'number_of_hours': 7.0,
                'amount': 238.11,
            }, {
                'code': '002.00',
                'number_of_days': 20.0,
                'number_of_hours': 140.0,
                'amount': 4762.22,
            }]
        )
        self.assertEqual(self.richard_emp.wage, self.richard_payslip._get_line_values(['BASIC'])['BASIC'][self.richard_payslip.id]['total'])

    def test_recompute_payslip_after_changing_inputs(self):
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.richard_emp.id,
            'version_id': self.contract_cdi.id,
            'struct_id': self.developer_pay_structure.id,
            'date_from': date(2016, 1, 1),
            'date_to': date(2016, 1, 31),
        })
        input_line = self.env['hr.payslip.input'].create({
            'payslip_id': payslip.id,
            'salary_rule_id': self.deduction_rule.id,
            'amount': 100.0,
        })

        payslip.compute_sheet()
        deduction_line = payslip.line_ids.filtered(lambda l: l.code == 'DEDUCTION')
        self.assertEqual(deduction_line.total, -100.0, "Deduction amount should be 100.0")

        payslip.write({'input_line_ids': [(1, input_line.id, {'amount': 150.0})]})
        deduction_line = payslip.line_ids.filtered(lambda l: l.code == 'DEDUCTION')
        self.assertEqual(deduction_line.total, -150.0, "Deduction amount should be 150.0")

    def test_warning_cleared_after_recompute(self):
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.richard_emp.id,
            'version_id': self.contract_cdi.id,
            'struct_id': self.developer_pay_structure.id,
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 1, 31),
        })

        payslip.compute_sheet()
        payslip.action_payslip_done()

        # Make a modification on the version that should trigger the warning on the payslip
        # Note: we need to wait a bit before writing on the version to ensure that the payslip has been fully computed and the warning triggered before the write
        # ,otherwise the warning will not be triggered at all and the test will be invalid.
        self.richard_emp.write({
            'wage': 10000.0,
        })

        # Cancel & draft the payslip
        payslip.action_payslip_cancel()
        payslip.action_payslip_draft()

        # Recompute & validate the payslip again
        payslip.compute_sheet()
        payslip.action_payslip_done()

        self.assertFalse(payslip.has_wrong_data, "Warning should not reappear after recompute.")

    def test_structure_without_worked_days_clears_lines(self):
        '''Changing the structure type to one that does not use worked days lines should clear the worked days lines immediately.'''
        no_worked_days_structure = self.env['hr.payroll.structure'].create({
            'name': '13th Month Structure',
            'type_id': self.developer_pay_structure.type_id.id,
            'use_worked_day_lines': False,
            'country_id': self.env.ref('base.be').id if self.env.ref('base.be', False) else False,
        })

        self.richard_payslip._compute_worked_days_line_ids()
        self.assertTrue(
            self.richard_payslip.worked_days_line_ids,
            "Initial payslip should have worked day lines generated."
        )

        with Form(self.richard_payslip) as payslip_form:
            payslip_form.struct_id = no_worked_days_structure

        self.assertFalse(
            self.richard_payslip.worked_days_line_ids,
            "Worked days lines must be cleared immediately when switching to a structure with use_worked_day_lines=False."
        )

        with Form(self.richard_payslip) as payslip_form:
            payslip_form.struct_id = self.developer_pay_structure

        self.assertTrue(
            self.richard_payslip.worked_days_line_ids,
            "Worked days lines should be re-computed when switching back to a regular structure."
        )

    def test_payslip_manual_line_edit_and_compute(self):
        """Ensure that manually editing a payslip line recalculates the payslip without UnboundLocalError."""
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.richard_emp.id,
            'version_id': self.contract_cdi.id,
            'struct_id': self.developer_pay_structure.id,
            'date_from': date(2016, 4, 1),
            'date_to': date(2016, 4, 30)
        })
        payslip.compute_sheet()

        basic_line = payslip.line_ids.filtered(lambda l: l.code == 'BASIC')
        basic_line.salary_rule_id.explanation_template = "This is a test explanation"
        net_line = payslip.line_ids.filtered(lambda l: l.code == 'NET')
        original_basic_amount = basic_line.amount
        original_net_total = net_line.total

        new_basic_amount = original_basic_amount + 1000.0
        payslip.write({
            'line_ids': [Command.update(basic_line.id, {'amount': new_basic_amount})]
        })
        basic_line_updated = payslip.line_ids.filtered(lambda l: l.code == 'BASIC')
        net_line_updated = payslip.line_ids.filtered(lambda l: l.code == 'NET')
        self.assertEqual(basic_line_updated.amount, new_basic_amount, "The BASIC amount should be updated.")
        self.assertNotEqual(net_line_updated.total, original_net_total, "The NET total should be recomputed after manual edit.")
        self.assertTrue(payslip.edited, "The payslip should be marked as edited.")

        payslip.compute_sheet()
        basic_line_reset = payslip.line_ids.filtered(lambda l: l.code == 'BASIC')
        net_line_reset = payslip.line_ids.filtered(lambda l: l.code == 'NET')
        self.assertEqual(basic_line_reset.amount, original_basic_amount, "The BASIC amount should be reset to its computed value.")
        self.assertEqual(net_line_reset.total, original_net_total, "The NET total should be reset to its computed value.")

    def test_onchange_remove_payslip_dates(self):
        """Ensure clearing payslip dates does not change the payslip version."""
        self.assertTrue(self.richard_emp.version_id.contract_date_start)

        slip_form = Form(self.env['hr.payslip'])
        slip_form.employee_id = self.richard_emp
        slip_form.date_from = False
        slip_form.date_to = False

        self.assertEqual(slip_form.version_id, self.richard_emp._get_version(False))
