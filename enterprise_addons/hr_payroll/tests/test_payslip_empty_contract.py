# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from dateutil.relativedelta import relativedelta
from odoo.fields import Date
from odoo.tests import tagged, freeze_time
from odoo.addons.hr_payroll.tests.common import TestPayslipContractBase


@tagged('post_install', '-at_install')
class TestPayslipNewEmployeeToday(TestPayslipContractBase):

    def _month_bounds(self, base_date):
        date_from = base_date.replace(day=1)
        date_to = date_from + relativedelta(months=1, days=-1)
        return date_from, date_to

    def _assert_full_out_of_contract(self, slip, lines, expected_duration):
        country_id = slip.struct_id.country_id.id if slip.struct_id and slip.struct_id.country_id else False
        out_type = self.env['hr.work.entry.type'].search([
            ('code', '=', '000.00'),
            ('country_id', '=', country_id),
        ], limit=1) or self.env.ref('hr_work_entry.generic_hr_work_entry_type_out_of_contract',
                                    raise_if_not_found=False)
        self.assertTrue(out_type, "Missing 'Out of Contract' work entry type (code 000.00)")

        out_lines = [l for l in lines if l.get('work_entry_type_id') == out_type.id]
        self.assertTrue(out_lines, f"Missing 'Out of Contract' line in payslip. Lines: {lines}")
        self.assertEqual(len(out_lines), 1, f"Expected exactly one 'Out of Contract' line, got {len(out_lines)}")
        out_line = out_lines[0]

        self.assertAlmostEqual(out_line['number_of_days'], expected_duration['days'], places=2)
        self.assertAlmostEqual(out_line['number_of_hours'], expected_duration['hours'], places=2)

        other_lines = [l for l in lines if l is not out_line]
        self.assertFalse(other_lines, "Expected only 'Out of Contract' line")

    def _make_new_employee_no_contract(self):
        emp = self.env['hr.employee'].create({
            'name': 'Employee Without Contract',
            'company_id': self.company_us.id,
            'resource_calendar_id': self.calendar_richard.id,
        })
        version = emp.version_id
        self.assertEqual(version.date_version, Date.today())
        self.assertFalse(version.contract_date_start)
        return emp, version

    def _make_draft_payslip(self, emp, version, date_from, date_to):
        return self.env['hr.payslip'].new({
            'name': 'Draft',
            'employee_id': emp.id,
            'version_id': version.id,
            'company_id': emp.company_id.id,
            'date_from': date_from,
            'date_to': date_to,
        })

    def test_employee_without_contract_payslip_current_month(self):
        with freeze_time(date(2025, 12, 20)):
            emp, version = self._make_new_employee_no_contract()

            date_from, date_to = self._month_bounds(Date.today())

            slip = self._make_draft_payslip(emp, version, date_from, date_to)
            lines = slip._get_worked_day_lines(versions=version, work_entries_vals=[], check_out_of_version=True)

            expected_duration = {'days': 23.0, 'hours': 184.0}
            self._assert_full_out_of_contract(slip, lines, expected_duration)

    def test_employee_without_contract_payslip_previous_month(self):
        with freeze_time(date(2025, 12, 20)):
            emp, version = self._make_new_employee_no_contract()

            prev_month_date = Date.today() + relativedelta(months=-1)
            date_from, date_to = self._month_bounds(prev_month_date)

            slip = self._make_draft_payslip(emp, version, date_from, date_to)
            lines = slip._get_worked_day_lines(versions=version, work_entries_vals=[], check_out_of_version=True)

            expected_duration = {'days': 20.0, 'hours': 160.0}
            self._assert_full_out_of_contract(slip, lines, expected_duration)

    def test_employee_without_contract_payslip_next_month(self):
        with freeze_time(date(2025, 12, 20)):
            emp, version = self._make_new_employee_no_contract()

            next_month_date = Date.today() + relativedelta(months=1)
            date_from, date_to = self._month_bounds(next_month_date)

            slip = self._make_draft_payslip(emp, version, date_from, date_to)
            lines = slip._get_worked_day_lines(versions=version, work_entries_vals=[], check_out_of_version=True)

            expected_duration = {'days': 22.0, 'hours': 176.0}
            self._assert_full_out_of_contract(slip, lines, expected_duration)
