# Part of Odoo. See LICENSE file for full copyright and licensing details.

from freezegun import freeze_time
from datetime import date, datetime

from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.l10n_be_hr_payroll.tests.common import TestBelgiumCommon


@tagged('post_install_l10n', 'post_install', '-at_install', 'eco_vouchers')
class TestEcoVouchers(AccountTestInvoicingCommon, TestBelgiumCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountTestInvoicingCommon.setup_country('be')
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids += cls.quick_ref('hr_holidays.group_hr_holidays_manager') \
            | cls.quick_ref('hr_payroll.group_hr_payroll_officer')
        cls.cp200 = cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200')
        cls.company_data['company'].current_payroll_config_id.l10n_be_employer_category_id = cls.env.ref('l10n_be_hr_payroll.l10n_be_employer_category_00010')

    @freeze_time("2021-01-01")
    def test_eco_vouchers(self):
        # The reference year is 2021, so the reference period is 01/06/2020 -> 31/05/2021 (12 months)
        # The proration is expressed in working days derived from the work entry
        # dates, over the days the calendar theoretically schedules for the whole
        # reference period. Employee is working on:
        # - Full time from 01/06/2020 to 31/10/2020 -> 110 working days, out of the
        #   261 the full time calendar schedules over the reference period
        # - Part time (3/5) from 01/11/2020 to 31/05/2021 -> 91 working days
        #   (Mon/Thu/Fri), out of the 157 the 3/5 calendar schedules over the
        #   reference period. Tuesdays/Wednesdays are credit time: structural,
        #   never counted as working days.
        # The part time schedule is 3/5 with Tuesday and Wednesday off, but those days are on credit time,
        # So the employee is still working with 100% rate of the time.
        # Thus, the employee should be entitled to 100% of the eco vouchers for the whole reference period, minus the unpaid time off in April 2021.
        # Employee is on unpaid time off from the 01/04/2021 to 21/04/2021, covering
        # 9 working days -> 91 - 9 = 82 valid working days.

        # Expected result = 250*110/261 + 200*82/157 = 105.36 + 104.46 = 209.82
        # Expected result = 250*110/261 + 250*82/157 = 105.36 + 130.58 = 235.94

        full_time_calendar = self.env['resource.calendar'].sudo().create([{
            'name': "Test Calendar : 38 Hours/Week",
            'company_id': self.env.company.id,
            'hours_per_week': 38.0,
            'full_time_required_hours': 38.0,
            'attendance_ids': [(5, 0, 0)] + [(0, 0, {
                'dayofweek': dayofweek,
                'hour_from': hour_from,
                'hour_to': hour_to,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_attendance').id

            }) for dayofweek, hour_from, hour_to in [
                ("0", 8.0, 12.0),
                ("0", 13.0, 16.6),
                ("1", 8.0, 12.0),
                ("1", 13.0, 16.6),
                ("2", 8.0, 12.0),
                ("2", 13.0, 16.6),
                ("3", 8.0, 12.0),
                ("3", 13.0, 16.6),
                ("4", 8.0, 12.0),
                ("4", 13.0, 16.6),
            ]],
        }]).sudo(False)

        credit_time_calendar_3_5 = self.env['resource.calendar'].sudo().create([{
            'name': "Test Calendar: 3/5 Tuesday/Wednesday Off",
            'company_id': self.env.company.id,
            'hours_per_week': 22.8,
            'full_time_required_hours': 38.0,
            'attendance_ids': [(5, 0, 0)] + [(0, 0, {
                'dayofweek': dayofweek,
                'hour_from': hour_from,
                'hour_to': hour_to,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_attendance').id

            }) for dayofweek, hour_from, hour_to in [
                ("0", 8.0, 12.0),
                ("0", 13.0, 16.6),
                ("3", 8.0, 12.0),
                ("3", 13.0, 16.6),
                ("4", 8.0, 12.0),
                ("4", 13.0, 16.6),
            ]] + [(0, 0, {
                'dayofweek': dayofweek,
                'hour_from': hour_from,
                'hour_to': hour_to,
                'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_credit_time').id
            }) for dayofweek, hour_from, hour_to in [
                ("1", 8.0, 12.0),
                ("1", 13.0, 16.6),
                ("2", 8.0, 12.0),
                ("2", 13.0, 16.6),
            ]],
        }]).sudo(False)
        employee = self.env['hr.employee'].sudo().create({
            'name': 'Test Employee',
            'date_version': date(2020, 6, 1),
            'contract_date_start': date(2020, 6, 1),
            'contract_date_end': date(2020, 10, 31),
            'resource_calendar_id': full_time_calendar.id,
            'wage': 1000,
            'l10n_be_joint_committee_id': self.cp200.id,
            'lang': 'fr_BE',
        }).sudo(False)

        version_2 = self.env['hr.version'].create({
            'name': 'Part Time Contract',
            'date_version': date(2020, 11, 1),
            'contract_date_start': date(2020, 11, 1),
            'contract_date_end': date(2021, 12, 31),
            'employee_id': employee.id,
            'resource_calendar_id': credit_time_calendar_3_5.id,
            'reference_calendar_id': full_time_calendar.id,
            'wage': 1000,
            'l10n_be_joint_committee_id': self.cp200.id,
        })

        unpaid_time_off_type = self.env.ref('hr_work_entry.be_work_entry_type_unpaid_leave')

        self.env['hr.leave'].create({
            'name': 'Unpaid Time Off 2021',
            'work_entry_type_id': unpaid_time_off_type.id,
            'request_date_from': date(2021, 4, 1),
            'request_date_to': date(2021, 4, 21),
            'employee_id': employee.id,
        })

        april_payslip = self.env['hr.payslip'].create({
            'version_id': version_2.id,
            'date_from': datetime(2021, 4, 1),
            'date_to': datetime(2021, 4, 30),
            'employee_id': employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.env.company.id,
        })
        april_payslip.action_refresh_from_work_entries()
        april_payslip.action_payslip_done()
        june_payslip = self.env['hr.payslip'].create({
            'version_id': version_2.id,
            'date_from': datetime(2021, 6, 1),
            'date_to': datetime(2021, 6, 30),
            'employee_id': employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.env.company.id,
        })
        june_payslip.action_refresh_from_work_entries()
        june_payslip.action_payslip_done()

        wizard = self.env['l10n.be.eco.vouchers.wizard'].create({
            'reference_year': '2021',
        })
        employee_line = wizard.line_ids.filtered(lambda l: l.employee_id == employee)
        expected_result = 235.94
        self.assertAlmostEqual(employee_line.amount, expected_result, places=2)

    @freeze_time("2026-01-01")
    def test_eco_vouchers_full_period_unpaid(self):
        # The employee is on unpaid time off for the whole reference period
        # 01/06/2025 -> 31/05/2026: every theoretically scheduled working day is
        # covered by an unpaid work entry, so no valid working day remains and no
        # eco-voucher is granted.
        full_time_calendar = self.env['resource.calendar'].sudo().create([{
            'name': "Test Calendar : 38 Hours/Week",
            'company_id': self.env.company.id,
            'hours_per_week': 38.0,
            'full_time_required_hours': 38.0,
            'attendance_ids': [(5, 0, 0)] + [(0, 0, {
                'dayofweek': dayofweek,
                'hour_from': hour_from,
                'hour_to': hour_to,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_attendance').id

            }) for dayofweek, hour_from, hour_to in [
                ("0", 8.0, 12.0),
                ("0", 13.0, 16.6),
                ("1", 8.0, 12.0),
                ("1", 13.0, 16.6),
                ("2", 8.0, 12.0),
                ("2", 13.0, 16.6),
                ("3", 8.0, 12.0),
                ("3", 13.0, 16.6),
                ("4", 8.0, 12.0),
                ("4", 13.0, 16.6),
            ]],
        }]).sudo(False)

        employee = self.env['hr.employee'].sudo().create({
            'name': 'Test Absent Employee',
            'date_version': date(2025, 6, 1),
            'contract_date_start': date(2025, 6, 1),
            'resource_calendar_id': full_time_calendar.id,
            'wage': 1000,
            'l10n_be_joint_committee_id': self.cp200.id,
            'lang': 'fr_BE',
        }).sudo(False)

        self.env['hr.leave'].create({
            'name': 'Unpaid Time Off Full Period',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_unpaid_leave').id,
            'request_date_from': date(2025, 6, 1),
            'request_date_to': date(2026, 5, 31),
            'employee_id': employee.id,
        })

        # CP200 eco vouchers are paid in June over the previous 12 months, so the
        # June 2026 payslip is the one computing the amount for the reference period.
        june_payslip = self.env['hr.payslip'].create({
            'version_id': employee.version_id.id,
            'date_from': datetime(2026, 6, 1),
            'date_to': datetime(2026, 6, 30),
            'employee_id': employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.env.company.id,
        })
        june_payslip.action_refresh_from_work_entries()
        june_payslip.action_payslip_done()
        self.assertAlmostEqual(june_payslip._get_eco_vouchers_amount(), 0.0, places=2)
