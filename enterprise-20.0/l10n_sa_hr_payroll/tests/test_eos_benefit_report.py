# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, timedelta


from odoo.tests import tagged
from odoo.addons.hr_payroll.tests.common import TestPayslipContractBase
from dateutil.relativedelta import relativedelta


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestEOSBenefitReport(TestPayslipContractBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.sa_company = cls.env['res.company'].create({
            'name': 'SA Test Co',
            'country_id': cls.env.ref('base.sa').id,
        })

        cls.structure_type = cls.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').type_id.id
        cls.sa = cls.env.ref('base.sa')
        cls.env.user.write({
            'company_id': cls.sa_company.id,
            'company_ids': [(4, cls.sa_company.id)]
        })
        cls.env = cls.env(context=dict(cls.env.context,
                                        allowed_company_ids=[cls.sa_company.id]))

    def _create_employee(self, name, contract_date_start, date_version,
                         wage=10000.0, contract_date_end=False):
        vals = {
            'name': name,
            'company_id': self.sa_company.id,
            'country_id': self.sa.id,
            'contract_date_start': contract_date_start,
            'date_version': date_version,
            'wage': wage,
            'structure_type_id': self.structure_type,
        }
        if contract_date_end:
            vals['contract_date_end'] = contract_date_end
        return self.env['hr.employee'].create(vals)

    def _create_version(self, employee, contract_date_start, date_version,
                        wage=10000.0):
        return self.env['hr.version'].create({
            'employee_id': employee.id,
            'company_id': self.sa_company.id,
            'country_id': self.sa.id,
            'contract_date_start': contract_date_start,
            'date_version': date_version,
            'wage': wage,
            'structure_type_id': self.structure_type,
        })

    def _create_report(self, date_to=date(2027, 1, 1), employee_ids=None):
        return self.env['l10n.sa.eos.benefit.wizard'].create({
            'company_id': self.sa_company.id,
            'date_to': date_to,
            'employee_ids': employee_ids,
        })

    def _create_leave_and_approve(self, employee, date_from, date_to, work_entry_type):
        leave = self.env['hr.leave'].create({
            'name': "New Holiday",
            'employee_id': employee.id,
            'request_date_from': date_from,
            'request_date_to': date_to,
            'work_entry_type_id': work_entry_type.id,
        })
        leave.action_approve()

    def test_report_computation(self):
        """
        Employee ids are provided normally, and the report is computed without any issues or
        missing salary rules.

        Three employees are created, one employee for each category of EOS benefit
        brackets: <1, 1-5, >5 years of service.

        One employee will have a single contract, another will have multiple contracts
        without gaps, and the last will have multiple contracts with gaps, to ensure that
        the report correctly computes different cases.

        - Employee 1: starts on 2026-01-02 and their contract does not end, with a wage of 10000.
        This employee will receive 0 EOSB for being in service.
        - Employee 2: starts on 2021-01-01, ends on 2021-12-31, and another contract starts
        on 2022-01-01 but does not end, with a wage of 10000. This employee will receive 45000
        EOSB for being in service for 5 years.
        - Employee 3: starts on 2020-01-01, ends on 2021-12-31, and another contract starts
        on 2024-01-01 but does not end. with a wage of 10000. This employee will receive 28000
        EOSB for being in service for 3 years which are the latter 3.
        """
        employee_1 = self._create_employee("Employee 1", date(2026, 1, 2), date(2026, 1, 2))
        employee_2 = self._create_employee("Employee 2", date(2021, 1, 1), date(2021, 1, 1), contract_date_end=date(2021, 12, 31))
        self._create_version(employee_2, date(2022, 1, 1), date(2022, 1, 1))
        employee_3 = self._create_employee("Employee 3", date(2020, 1, 1), date(2020, 1, 1), contract_date_end=date(2021, 12, 31))
        self._create_version(employee_3, date(2024, 1, 1), date(2024, 1, 1))
        report = self._create_report(employee_ids=[employee_1.id, employee_2.id, employee_3.id])
        report_data = report._get_report_data()
        expected_report_data = [
            {
                'employee_name': "Employee 1",
                'employee_id': employee_1.id,
                'first_contract_date': date(2026, 1, 2),
                'selected_end_date': date(2027, 1, 1),
                'eosb_amount': 5055.56,
            },
            {
                'employee_name': "Employee 2",
                'employee_id': employee_2.id,
                'first_contract_date': date(2021, 1, 1),
                'selected_end_date': date(2027, 1, 1),
                'eosb_amount': 35861.11,
            },
            {
                'employee_name': "Employee 3",
                'employee_id': employee_3.id,
                'first_contract_date': date(2020, 1, 1),
                'selected_end_date': date(2027, 1, 1),
                'eosb_amount': 15222.22,
            },
        ]
        self.maxDiff = 1000
        self.assertEqual(report.issues, False)
        self.assertEqual(report_data, expected_report_data)

    def _report_computation_with_timeoff(self, l10n_sa_eos_number_of_days_in_year):
        contract_start_date = date(2020, 1, 1)
        if l10n_sa_eos_number_of_days_in_year == 'actual':
            # with the actual year basis, dates are computed by calendar duration instead of a fixed number of days
            contract_last_date = contract_start_date + relativedelta(years=5, months=6, days=-1)
        else:
            employment_duration = 5.5 * 360  # 5.5 years
            contract_last_date = contract_start_date + timedelta(days=employment_duration)
        employee = self._create_employee("Test Employee", contract_start_date, contract_start_date, contract_date_end=contract_last_date, wage=2000)
        employee.l10n_sa_eos_number_of_days_in_year = l10n_sa_eos_number_of_days_in_year

        employee.company_id.l10n_sa_unpaid_leave_eos_threshold = 90  # excess parts above 90 should be deducted, if 100 days leave, 10 days must be deducted
        report = self._create_report(date_to=contract_last_date, employee_ids=[employee.id])
        report_data = report._get_report_data()
        # oesb_amount = (5 * compensation / 2) + ((total_years - 5) * compensation) when years > 5
        # 5 * 2000 / 2 + 0.5 * 2000 = 6000
        expected_report_data = [
            {
                'employee_name': "Test Employee",
                'employee_id': employee.id,
                'first_contract_date': contract_start_date,
                'selected_end_date': contract_last_date,
                'eosb_amount': 6000,
            }
        ]
        self.assertEqual(employee._l10n_sa_get_number_of_years(contract_start_date, contract_last_date), 5.5)
        self.assertEqual(report_data, expected_report_data)

        unpaid_work_entry_type = self.env.ref('hr_work_entry.sa_work_entry_type_unpaid_leave')
        legal_leave_work_entry_type = self.env.ref('hr_work_entry.sa_work_entry_type_legal_leave')

        # legal leave is a paid leave, only unpaid leaves are relevant for the end of service calculations
        # still the calculation is over 5.5 years and the result is still 6000
        self._create_leave_and_approve(employee, '2023-01-01', '2024-12-31', legal_leave_work_entry_type)
        report = self._create_report(date_to=contract_last_date, employee_ids=[employee.id])
        report_data = report._get_report_data()
        self.assertEqual(employee._l10n_sa_get_number_of_years(contract_start_date, contract_last_date), 5.5)
        self.assertEqual(report_data, expected_report_data)

        # they are unpaid but the duration of leaves (number_of_days) < 90 so they won't get deducted in the year calculation
        # the result will be still calculated over 5.5 years and should be 6000
        self._create_leave_and_approve(employee, '2021-10-01', '2021-12-31', unpaid_work_entry_type)
        self._create_leave_and_approve(employee, '2022-01-01', '2022-03-31', unpaid_work_entry_type)
        self._create_leave_and_approve(employee, '2022-04-01', '2022-06-30', unpaid_work_entry_type)
        self._create_leave_and_approve(employee, '2022-07-01', '2022-09-30', unpaid_work_entry_type)
        self._create_leave_and_approve(employee, '2022-10-01', '2022-12-31', unpaid_work_entry_type)
        report = self._create_report(date_to=contract_last_date, employee_ids=[employee.id])
        report_data = report._get_report_data()
        self.assertEqual(employee._l10n_sa_get_number_of_years(contract_start_date, contract_last_date), 5.5)
        self.assertEqual(report_data, expected_report_data)

        if l10n_sa_eos_number_of_days_in_year == 'actual':
            # unpaid leave with 455 number_of_days
            # with the actual year basis, the year is calculated by calendar duration instead of a fixed number of days
            # it is more than 90 and 455-90=365 excess days will be deducted in year calculation, the calculated year = 4.5
            # when the year is 4.5 the eosb_amount = total_years * compensation / 2 = 4.5 * 2000 / 2 = 4500
            self._create_leave_and_approve(employee, '2020-01-01', '2021-09-28', unpaid_work_entry_type)
        else:
            # unpaid leave with 450 number_of_days
            # it is more than 90 and 450-90=360 excess days will be deducted in year calculation, the calculated year = 4.5
            # when the year is 4.5 the eosb_amount = total_years * compensation / 2 = 4.5 * 2000 / 2 = 4500
            self._create_leave_and_approve(employee, '2020-01-01', '2021-09-21', unpaid_work_entry_type)

        report = self._create_report(date_to=contract_last_date, employee_ids=[employee.id])
        report_data = report._get_report_data()
        expected_report_data[0]['eosb_amount'] = 4500
        self.assertEqual(employee._l10n_sa_get_number_of_years(contract_start_date, contract_last_date), 4.5)
        self.assertEqual(report_data, expected_report_data)

    def test_report_computation_with_timeoff(self):
        legal_leave_work_entry_type = self.env.ref('hr_work_entry.sa_work_entry_type_legal_leave')
        legal_leave_work_entry_type.sudo().requires_allocation = False
        self._report_computation_with_timeoff('360')
        self._report_computation_with_timeoff('actual')

    def test_report_computation_without_employees(self):
        """
        Employee ids are not provided and are fetched automatically within the report,
        and the report is computed without any issues or missing salary rules.

        Three employees are created, one employee for each category of EOS benefit
        brackets: <1, 1-5, >5 years of service.

        One employee will have a single contract, another will have multiple contracts
        without gaps, and the last will have multiple contracts with gaps, to ensure that
        the report correctly computes different cases.

        - Employee 1: starts on 2026-01-02 and their contract does not end, with a wage of 10000.
        This employee will receive 0 EOSB for being in service.
        - Employee 2: starts on 2021-01-01, ends on 2021-12-31, and another contract starts
        on 2022-01-01 but does not end, with a wage of 10000. This employee will receive 45000
        EOSB for being in service for 5 years.
        - Employee 3: starts on 2020-01-01, ends on 2021-12-31, and another contract starts
        on 2024-01-01 but does not end. with a wage of 10000. This employee will receive 28000
        EOSB for being in service for 3 years which are the latter 3.
        """
        employee_1 = self._create_employee("Employee 1", date(2026, 1, 2), date(2026, 1, 2))
        employee_2 = self._create_employee("Employee 2", date(2021, 1, 1), date(2021, 1, 1), contract_date_end=date(2021, 12, 31))
        self._create_version(employee_2, date(2022, 1, 1), date(2022, 1, 1))
        employee_3 = self._create_employee("Employee 3", date(2020, 1, 1), date(2020, 1, 1), contract_date_end=date(2021, 12, 31))
        self._create_version(employee_3, date(2024, 1, 1), date(2024, 1, 1))
        report = self._create_report()
        report_data = report._get_report_data()
        expected_report_data = [
            {
                'employee_name': "Employee 1",
                'employee_id': employee_1.id,
                'first_contract_date': date(2026, 1, 2),
                'selected_end_date': date(2027, 1, 1),
                'eosb_amount': 5055.56,
            },
            {
                'employee_name': "Employee 2",
                'employee_id': employee_2.id,
                'first_contract_date': date(2021, 1, 1),
                'selected_end_date': date(2027, 1, 1),
                'eosb_amount': 35861.11,
            },
            {
                'employee_name': "Employee 3",
                'employee_id': employee_3.id,
                'first_contract_date': date(2020, 1, 1),
                'selected_end_date': date(2027, 1, 1),
                'eosb_amount': 15222.22,
            },
        ]
        self.maxDiff = 1000
        self.assertEqual(report.issues, False)
        self.assertEqual(report_data, expected_report_data)

    def test_report_computation_with_issues(self):
        """
        Employee ids are provided normally, but the report is computed with issues
        and without missing salary rules.

        Two employees are created, one employee with an issue while the other does not.

        One employee will have a single contract with end date before report date
        while the other will have normal running contract to ensure that the report
        correctly computes different cases.

        - Employee 1: starts on 2020-01-01 and ends on 2026-07-01, with a
        wage of 10000. This employee will receive 0 EOSB for being in service.
        - Employee 2: starts on 2020-01-01 but does not end, with a wage of
        10000. This employee will receive 45000 EOSB for being in service for 5 years.
        """
        employee_1 = self._create_employee("Employee 1", date(2020, 1, 1), date(2020, 1, 1), contract_date_end=date(2026, 7, 1))
        employee_1.version_id.departure_id = self.env["hr.employee.departure"].create({
            "employee_id": employee_1.id,
            "departure_date": date(2026, 7, 1),
            "departure_reason_id": self.env.ref('l10n_sa_hr_payroll.saudi_departure_end_of_contract').id
        })
        employee_2 = self._create_employee("Employee 2", date(2020, 1, 1), date(2020, 1, 1))
        report = self._create_report(employee_ids=[employee_1.id, employee_2.id])
        report_data = report._get_report_data()
        expected_report_data = [
            {
                'employee_name': "Employee 1",
                'employee_id': employee_1.id,
                'first_contract_date': date(2020, 1, 1),
                'selected_end_date': date(2027, 1, 1),
                'eosb_amount': 46027.78,
            },
            {
                'employee_name': "Employee 2",
                'employee_id': employee_2.id,
                'first_contract_date': date(2020, 1, 1),
                'selected_end_date': date(2027, 1, 1),
                'eosb_amount': 46027.78,
            },
        ]
        self.assertEqual(report.issues, True)
        self.assertEqual(report_data, expected_report_data)
