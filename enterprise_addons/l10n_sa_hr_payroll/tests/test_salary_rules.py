from .common import TestSACommon
from odoo.tests.common import tagged
from datetime import date
from dateutil.relativedelta import relativedelta


@tagged("post_install", "post_install_l10n", "-at_install", "payslips_validation")
class TestPayslipValidation(TestSACommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref("hr_holidays.group_hr_holidays_manager")
        cls.env.user.group_ids |= cls.env.ref("hr_payroll.group_hr_payroll_manager")
        cls.saudi_employee = cls.env["hr.employee"].create(
            {
                "name": "KSA Local Employee",
                "address_id": cls.saudi_work_contact.id,
                "company_id": cls.env.company.id,
                "country_id": cls.env.ref("base.sa").id,
                "structure_type_id": cls.env.ref(
                    "l10n_sa_hr_payroll.ksa_employee_payroll_structure_type"
                ).id,
                "resource_calendar_id": cls.resource_calendar.id,
                "tz": "Asia/Riyadh",
                "date_version": date(2024, 1, 1),
                "contract_date_start": date(2024, 1, 1),
                "wage": 12000,
                "l10n_sa_housing_allowance": 1000,
                "l10n_sa_transportation_allowance": 200,
                "l10n_sa_other_allowances": 500,
                "l10n_sa_number_of_days": 21,
                "l10n_sa_company_social_insurance_percentage": 0.09,
                "l10n_sa_company_oh_insurance_percentage": 0.0075,
                "l10n_sa_company_unemployment_insurance_percentage": 0.02,
                "l10n_sa_employee_social_insurance_percentage": 0.09,
                "l10n_sa_employee_oh_insurance_percentage": 0.0025,
                "l10n_sa_employee_unemployment_insurance_percentage": 0.005,
                "l10n_sa_iqama_annual_amount": 6000.0,
                "l10n_sa_medical_insurance_annual_amount": 4800.0,
                "l10n_sa_work_permit_annual_amount": 3600.0,
            }
        )

    def _test_eos_calculation(self, start_date, end_date, dismissal_date, departure_reason_id, payslip_start, payslip_end,
                            expected_eosb, wage=15000.0, expected_eospc=None, prior_months=0,
                            housing_allowance=1000.0, transportation_allowance=500.0, other_allowances=300.0):
        """Helper method to test end of service salary rule calculations."""
        test_employee = self.env['hr.employee'].create({
            'name': 'Test Employee',
            'structure_type_id': self.env.ref('l10n_sa_hr_payroll.ksa_employee_payroll_structure_type').id,
            'country_id': self.env.ref('base.sa').id,
            'wage': wage,
            'l10n_sa_housing_allowance': housing_allowance,
            'l10n_sa_transportation_allowance': transportation_allowance,
            'l10n_sa_other_allowances': other_allowances,
            'date_version': start_date,
            'contract_date_start': start_date,
            "contract_date_end": end_date,
        })

        # Generate prior payslips to accrue EOSP provisions
        for i in range(1, prior_months + 1):
            prior_start = payslip_start.replace(day=1) - relativedelta(months=i)
            prior_end = prior_start + relativedelta(months=1, days=-1)

            prior_payslip = self._generate_payslip(prior_start, prior_end, employee_id=test_employee.id, version_id=test_employee.version_id.id)
            prior_payslip.compute_sheet()
            prior_payslip.action_payslip_done()

        departure_notice = self.env['hr.employee.departure'].create({
            'employee_id': test_employee.id,
            'dismissal_date': dismissal_date,
            'departure_reason_id': departure_reason_id,
            'departure_description': 'foo',
        })
        departure_notice.action_register()

        payslip = self._generate_payslip(payslip_start, payslip_end, employee_id=test_employee.id, version_id=test_employee.version_id.id)
        payslip.compute_sheet()

        self.assertEqual(
            payslip._get_line_values(['EOSB'])['EOSB'][payslip.id]['total'],
            expected_eosb,
            "End of Service Benefit calculation is incorrect"
        )

        if expected_eospc is not None:
            self.assertEqual(
                payslip._get_line_values(['EOSPC'])['EOSPC'][payslip.id]['total'],
                expected_eospc,
                "End of Service Provision Correction calculation is incorrect"
            )

    def test_sick_leave_split_with_calendar_payslips_1(self):
        """
        - Sick leave deductions: 0% for the first 30 days, 25% for days 31-60, and 100% for any days beyond 60.
        - Sick leave counting year 01/Jan -> 31/Dec

        - Sick leaves table (All dates are inclusive)
        | Name | Date from   | Date to     | Duration | Start year | End Year |
        | ---- | ----------- | ----------- | -------- | ---------- | -------- |
        | 1st  | 01/Jan/2024 | 01/Jan/2024 | 1        |     Y1     |    Y1    |
        | 2nd  | 30/Dec/2024 | 08/Jan/2025 | 8        |     Y1     |    Y2    |
        | 3rd  | 01/Sep/2025 | 31/Oct/2025 | 45       |     Y1     |    Y1    |
        | 4th  | 01/Nov/2025 | 02/Jan/2026 | 45       |     Y1     |    Y2    |

        - Payslips table (Daily wage varies depending on working days in the month)
        - N/A means that the payslip doesn't lie in two different sick years
        | Period | Y1 up-to-date sick leaves | Y2 up-to-date sick leaves |   # of sick leaves   |          DEDSICKLEAVE payslip line         |
        | ------ | ------------------------- | ------------------------- | -------------------- | ------------------------------------------ |
        | Sep 25 |             28            |            N/A            |            22        | 22  * 0             * 13.7k / 23 = 0       |
        | Jan 25 |             6             |            N/A            |            6         | 6   * 0             * 13.7k / 22 = 0       |
        | Oct 25 |             51            |            N/A            |            23        | (2 * 0 + 21 * 0.25) * 13.7k / 23 = 3127.17 |
        | Nov 25 |             71            |            N/A            |            20        | 20  * 0.25          * 13.7k / 20 = 3425.0  |
        | Dec 25 |             94            |            N/A            |            23        | 19 * 0.25           * 13.7k / 23 = 2829.35 |
        """
        sick_time_off_type = self.env.ref("hr_work_entry.sa_work_entry_type_sick_leave")
        # take a sick leave in Jan 2023 so that the first counting date is 1 Jan 2023
        self.env["hr.leave"].create(
            {
                "name": "Sick Time Off Jan",
                "employee_id": self.saudi_employee.id,
                "work_entry_type_id": sick_time_off_type.id,
                "request_date_from": date(2024, 1, 1),
                "request_date_to": date(2024, 1, 1),
            }
        )
        self.env["hr.leave"].create(
            {
                "name": "Sick Time Off Dec & Jan",
                "employee_id": self.saudi_employee.id,
                "work_entry_type_id": sick_time_off_type.id,
                "request_date_from": date(2024, 12, 30),
                "request_date_to": date(2025, 1, 8),
            }
        )
        structure = self.env.ref(
            "l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure"
        )

        # January Payslip check
        payslip_jan = self._generate_payslip(
            date_from=date(2025, 1, 1),
            date_to=date(2025, 1, 31),
            struct_id=structure.id,
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
        )
        self.assertEqual(payslip_jan.worked_days_line_ids.filtered(lambda l: l.code == "013.00").number_of_days, 6)
        payslip_jan_results = {
            "NET": 12432.5,
        }
        self._validate_payslip(payslip_jan, payslip_jan_results, skip_lines=True)
        self.env["hr.leave"].create(
            {
                "name": "Sick Time Off Sep & Oct",
                "employee_id": self.saudi_employee.id,
                "work_entry_type_id": sick_time_off_type.id,
                "request_date_from": date(2025, 9, 1),
                "request_date_to": date(2025, 10, 31),
            }
        )
        self.env["hr.leave"].create(
            {
                "name": "Sick Time Off Nov till Jan",
                "employee_id": self.saudi_employee.id,
                "work_entry_type_id": sick_time_off_type.id,
                "request_date_from": date(2025, 11, 1),
                "request_date_to": date(2026, 1, 2),
            }
        )

        # September Payslip check
        payslip_sep = self._generate_payslip(
            date_from=date(2025, 9, 1),
            date_to=date(2025, 9, 30),
            struct_id=structure.id,
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
        )
        self.assertEqual(payslip_sep.worked_days_line_ids.filtered(lambda l: l.code == "013.00").number_of_days, 22)
        payslip_sep_result = {
            "NET": 12432.5,
        }
        self._validate_payslip(payslip_sep, payslip_sep_result, skip_lines=True)

        # October Payslip check
        payslip_oct = self._generate_payslip(
            date_from=date(2025, 10, 1),
            date_to=date(2025, 10, 31),
            struct_id=structure.id,
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
        )
        self.assertEqual(payslip_oct.worked_days_line_ids.filtered(lambda l: l.code == "013.00").number_of_days, 2)
        self.assertEqual(payslip_oct.worked_days_line_ids.filtered(lambda l: l.code == "SASICKLEAVE75").number_of_days, 21)
        payslip_oct_result = {
            "DEDSICKLEAVE": -3127.17,
            "NET": 9305.33,
        }
        self._validate_payslip(payslip_oct, payslip_oct_result, skip_lines=True)

        # November Payslip check
        payslip_nov = self._generate_payslip(
            date_from=date(2025, 11, 1),
            date_to=date(2025, 11, 30),
            struct_id=structure.id,
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
        )
        self.assertEqual(payslip_nov.worked_days_line_ids.filtered(lambda l: l.code == "SASICKLEAVE75").number_of_days, 20)
        payslip_nov_result = {
            "DEDSICKLEAVE": -3425.0,
            "NET": 9007.5,
        }
        self._validate_payslip(payslip_nov, payslip_nov_result, skip_lines=True)

        # December Payslip check
        payslip_dec = self._generate_payslip(
            date_from=date(2025, 12, 1),
            date_to=date(2025, 12, 31),
            struct_id=structure.id,
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
        )
        self.assertEqual(payslip_dec.worked_days_line_ids.filtered(lambda l: l.code == "SASICKLEAVE75").number_of_days, 19)
        self.assertEqual(payslip_dec.worked_days_line_ids.filtered(lambda l: l.code == "SASICKLEAVE0").number_of_days, 4)
        payslip_dec_result = {
            "UNPAID": -2382.61,
            "DEDSICKLEAVE": -2829.35,
            "NET": 7220.54,
        }
        self._validate_payslip(payslip_dec, payslip_dec_result, skip_lines=True)

    def test_sick_leave_split_with_calendar_payslips_2(self):
        """
        - Sick leave deductions: 0% for the first 30 days, 25% for days 31-60, and 100% for any days beyond 60.
        - Sick leave counting year 16/Nov -> 15/Nov

        - Sick leaves table (All dates are inclusive)
        | Name | Date from   | Date to     | Duration | Start year | End Year |
        | ---- | ----------- | ----------- | -------- | ---------- | -------- |
        | 1st  | 16/Nov/2023 | 16/Nov/2023 | 1        |     Y1     |    Y1    |
        | 2nd  | 15/Nov/2024 | 18/Nov/2024 | 2        |     Y1     |    Y2    |
        | 3rd  | 30/Dec/2024 | 10/Jan/2025 | 9        |     Y1     |    Y1    |
        | 4th  | 01/Sep/2025 | 31/Oct/2025 | 45       |     Y1     |    Y1    |
        | 5th  | 01/Nov/2025 | 02/Jan/2026 | 45       |     Y1     |    Y2    |

        - Payslips table (Daily wage varies depending on working days in the month)
        - N/A means that the payslip doesn't lie in two different sick years
        | Period | Y1 up-to-date sick leaves | Y2 up-to-date sick leaves |   # of sick leaves   |          DEDSICKLEAVE payslip line          |
        | ------ | ------------------------- | ------------------------- | -------------------- | ------------------------------------------- |
        | Jan 25 |             10            |            N/A            |            7         | 7   * 0              * 13.7k / 23 = 0       |
        | Sep 25 |             32            |            N/A            |            22        | (20 * 0 + 2 * 0.25)  * 13.7k / 22 = 311.36  |
        | Oct 25 |             55            |            N/A            |            23        | 23  * 0.25           * 13.7k / 23 = 3425.0  |
        | Nov 25 |             65            |            10             |            20        | (10 * 0.25 + 10 * 0) * 13.7k / 20 = 1712.5  |
        | Dec 25 |             33            |            N/A            |            23        | (20 * 0 + 3 * 0.25)  * 13.7k / 23 = 446.74  |
        """
        sick_time_off_type = self.env.ref("hr_work_entry.sa_work_entry_type_sick_leave")
        self.env["hr.leave"].create(
            {
                "name": "Sick Time Off Nov",
                "employee_id": self.saudi_employee.id,
                "work_entry_type_id": sick_time_off_type.id,
                "request_date_from": date(2023, 11, 16),
                "request_date_to": date(2023, 11, 16),
            }
        )
        self.env["hr.leave"].create(
            {
                "name": "Sick Time Off Nov",
                "employee_id": self.saudi_employee.id,
                "work_entry_type_id": sick_time_off_type.id,
                "request_date_from": date(2024, 11, 15),
                "request_date_to": date(2024, 11, 18),
            }
        )
        self.env["hr.leave"].create(
            {
                "name": "Sick Time Off Dec & Jan",
                "employee_id": self.saudi_employee.id,
                "work_entry_type_id": sick_time_off_type.id,
                "request_date_from": date(2024, 12, 30),
                "request_date_to": date(2025, 1, 9),
            }
        )
        structure = self.env.ref(
            "l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure"
        )

        # January Payslip check
        payslip_jan = self._generate_payslip(
            date_from=date(2025, 1, 1),
            date_to=date(2025, 1, 31),
            struct_id=structure.id,
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
        )
        self.assertEqual(payslip_jan.worked_days_line_ids.filtered(lambda l: l.code == "013.00").number_of_days, 7)
        payslip_jan_results = {
            "NET": 12432.5,
        }
        self._validate_payslip(payslip_jan, payslip_jan_results, skip_lines=True)
        self.env["hr.leave"].create(
            {
                "name": "Sick Time Off Sep & Oct",
                "employee_id": self.saudi_employee.id,
                "work_entry_type_id": sick_time_off_type.id,
                "request_date_from": date(2025, 9, 1),
                "request_date_to": date(2025, 10, 31),
            }
        )
        self.env["hr.leave"].create(
            {
                "name": "Sick Time Off Nov till Jan",
                "employee_id": self.saudi_employee.id,
                "work_entry_type_id": sick_time_off_type.id,
                "request_date_from": date(2025, 11, 1),
                "request_date_to": date(2026, 1, 2),
            }
        )

        # September Payslip check
        payslip_sep = self._generate_payslip(
            date_from=date(2025, 9, 1),
            date_to=date(2025, 9, 30),
            struct_id=structure.id,
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
        )
        self.assertEqual(payslip_sep.worked_days_line_ids.filtered(lambda l: l.code == "013.00").number_of_days, 20)
        self.assertEqual(payslip_sep.worked_days_line_ids.filtered(lambda l: l.code == "SASICKLEAVE75").number_of_days, 2)
        payslip_sep_result = {
            "DEDSICKLEAVE": -311.36,
            "NET": 12121.14,
        }
        self._validate_payslip(payslip_sep, payslip_sep_result, skip_lines=True)

        # October Payslip check
        payslip_oct = self._generate_payslip(
            date_from=date(2025, 10, 1),
            date_to=date(2025, 10, 31),
            struct_id=structure.id,
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
        )
        self.assertEqual(payslip_oct.worked_days_line_ids.filtered(lambda l: l.code == "SASICKLEAVE75").number_of_days, 23)
        payslip_oct_result = {
            "DEDSICKLEAVE": -3425.0,
            "NET": 9007.5,
        }
        self._validate_payslip(payslip_oct, payslip_oct_result, skip_lines=True)

        # November Payslip check
        payslip_nov = self._generate_payslip(
            date_from=date(2025, 11, 1),
            date_to=date(2025, 11, 30),
            struct_id=structure.id,
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
        )
        self.assertEqual(payslip_nov.worked_days_line_ids.filtered(lambda l: l.code == "013.00").number_of_days, 10)
        self.assertEqual(payslip_nov.worked_days_line_ids.filtered(lambda l: l.code == "SASICKLEAVE75").number_of_days, 10)
        payslip_nov_result = {
            "DEDSICKLEAVE": -1712.5,
            "NET": 10720.0,
        }
        self._validate_payslip(payslip_nov, payslip_nov_result, skip_lines=True)

        # December Payslip check
        payslip_dec = self._generate_payslip(
            date_from=date(2025, 12, 1),
            date_to=date(2025, 12, 31),
            struct_id=structure.id,
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
        )
        self.assertEqual(payslip_dec.worked_days_line_ids.filtered(lambda l: l.code == "013.00").number_of_days, 20)
        self.assertEqual(payslip_dec.worked_days_line_ids.filtered(lambda l: l.code == "SASICKLEAVE75").number_of_days, 3)
        payslip_dec_result = {
            "DEDSICKLEAVE": -446.74,
            "NET": 11985.76,
        }
        self._validate_payslip(payslip_dec, payslip_dec_result, skip_lines=True)

    def test_sick_leave_split_with_attendance_payslips(self):
        """
        - Sick leave allowance: 100% for the first 30 days, 75% for days 31-60, and 0% for any days beyond 60.
        - Sick leave counting year 16/Nov -> 15/Nov

        - Sick leaves table (All dates are inclusive)
        | Name | Date from   | Date to     | Duration | Start year | End Year |
        | ---- | ----------- | ----------- | -------- | ---------- | -------- |
        | 1st  | 16/Nov/2023 | 16/Nov/2023 | 1        |     Y1     |    Y1    |
        | 2nd  | 15/Nov/2024 | 18/Nov/2024 | 2        |     Y1     |    Y2    |
        | 3rd  | 30/Dec/2024 | 10/Jan/2025 | 9        |     Y1     |    Y1    |
        | 4th  | 01/Sep/2025 | 31/Oct/2025 | 45       |     Y1     |    Y1    |
        | 5th  | 01/Nov/2025 | 02/Jan/2026 | 45       |     Y1     |    Y2    |

        - Payslips table (allowances don't contribute to BASIC and are prorated in their own rules)
        - N/A means that the payslip doesn't lie in two different sick years
        | Period | Y1 up-to-date sick leaves | Y2 up-to-date sick leaves |   # of sick leaves   |     Amount contributed to the BASIC        |
        | ------ | ------------------------- | ------------------------- | -------------------- | ------------------------------------------ |
        | Jan 25 |             10            |            N/A            |            7         | 7                    * 12k / 23 = 3652.17  |
        | Sep 25 |             32            |            N/A            |            22        | (20 +  2 * 0.75)     * 12k / 22 = 11727.27 |
        | Oct 25 |             55            |            N/A            |            23        | 23  * 0.75           * 12k / 23 = 9000.0   |
        | Nov 25 |             65            |            10             |            20        | (10 * 0.75 + 10)     * 12k / 20 = 10500.0  |
        | Dec 25 |             33            |            N/A            |            23        | (20 + 3 * 0.75)      * 12k / 23 = 11608.69 |
        """
        if (
            self.env["ir.module.module"]._get("hr_payroll_attendance").state
            != "installed"
        ):
            self.skipTest(
                "The test was skipped because the 'hr_payroll_attendance' module isn’t installed; therefore, attendance-based entries are unavailable."
            )
        self.saudi_employee.attendance_based = True
        sick_time_off_type = self.env.ref("hr_work_entry.sa_work_entry_type_sick_leave")
        self.env["hr.leave"].create(
            {
                "name": "Sick Time Off Nov",
                "employee_id": self.saudi_employee.id,
                "work_entry_type_id": sick_time_off_type.id,
                "request_date_from": date(2023, 11, 16),
                "request_date_to": date(2023, 11, 16),
            }
        )
        self.env["hr.leave"].create(
            {
                "name": "Sick Time Off Nov",
                "employee_id": self.saudi_employee.id,
                "work_entry_type_id": sick_time_off_type.id,
                "request_date_from": date(2024, 11, 15),
                "request_date_to": date(2024, 11, 18),
            }
        )
        self.env["hr.leave"].create(
            {
                "name": "Sick Time Off Dec & Jan",
                "employee_id": self.saudi_employee.id,
                "work_entry_type_id": sick_time_off_type.id,
                "request_date_from": date(2024, 12, 30),
                "request_date_to": date(2025, 1, 9),
            }
        )
        structure = self.env.ref(
            "l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure"
        )
        # January Payslip check
        payslip_jan = self._generate_payslip(
            date_from=date(2025, 1, 1),
            date_to=date(2025, 1, 31),
            struct_id=structure.id,
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
        )
        sick_leave_days = payslip_jan.worked_days_line_ids.filtered(
            lambda l: l.code == "013.00"
        )
        self.assertEqual(sick_leave_days.number_of_days, 7)
        payslip_jan_results = {
            "BASIC": 3652.17,
        }
        self._validate_payslip(payslip_jan, payslip_jan_results, skip_lines=True)
        self.env["hr.leave"].create(
            {
                "name": "Sick Time Off Sep & Oct",
                "employee_id": self.saudi_employee.id,
                "work_entry_type_id": sick_time_off_type.id,
                "request_date_from": date(2025, 9, 1),
                "request_date_to": date(2025, 10, 31),
            }
        )
        self.env["hr.leave"].create(
            {
                "name": "Sick Time Off Nov till Jan",
                "employee_id": self.saudi_employee.id,
                "work_entry_type_id": sick_time_off_type.id,
                "request_date_from": date(2025, 11, 1),
                "request_date_to": date(2026, 1, 2),
            }
        )

        # September Payslip check
        payslip_sep = self._generate_payslip(
            date_from=date(2025, 9, 1),
            date_to=date(2025, 9, 30),
            struct_id=structure.id,
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
        )
        self.assertEqual(payslip_sep.worked_days_line_ids.filtered(lambda l: l.code == "013.00").number_of_days, 20)
        self.assertEqual(payslip_sep.worked_days_line_ids.filtered(lambda l: l.code == "SASICKLEAVE75").number_of_days, 2)
        payslip_sep_result = {
            "BASIC": 11727.27,
        }
        self._validate_payslip(payslip_sep, payslip_sep_result, skip_lines=True)

        # October Payslip check
        payslip_oct = self._generate_payslip(
            date_from=date(2025, 10, 1),
            date_to=date(2025, 10, 31),
            struct_id=structure.id,
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
        )
        self.assertEqual(payslip_oct.worked_days_line_ids.filtered(lambda l: l.code == "SASICKLEAVE75").number_of_days, 23)
        payslip_oct_result = {
            "BASIC": 9000.0,
        }
        self._validate_payslip(payslip_oct, payslip_oct_result, skip_lines=True)

        # November Payslip check
        payslip_nov = self._generate_payslip(
            date_from=date(2025, 11, 1),
            date_to=date(2025, 11, 30),
            struct_id=structure.id,
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
        )
        self.assertEqual(payslip_nov.worked_days_line_ids.filtered(lambda l: l.code == "013.00").number_of_days, 10)
        self.assertEqual(payslip_nov.worked_days_line_ids.filtered(lambda l: l.code == "SASICKLEAVE75").number_of_days, 10)
        payslip_nov_result = {
            "BASIC": 10500.0,
        }
        self._validate_payslip(payslip_nov, payslip_nov_result, skip_lines=True)

        # December Payslip check
        payslip_dec = self._generate_payslip(
            date_from=date(2025, 12, 1),
            date_to=date(2025, 12, 31),
            struct_id=structure.id,
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
        )
        self.assertEqual(payslip_dec.worked_days_line_ids.filtered(lambda l: l.code == "013.00").number_of_days, 20)
        self.assertEqual(payslip_dec.worked_days_line_ids.filtered(lambda l: l.code == "SASICKLEAVE75").number_of_days, 3)
        payslip_dec_result = {
            "BASIC": 11608.69,
        }
        self._validate_payslip(payslip_dec, payslip_dec_result, skip_lines=True)

    def test_sick_leave_split_half_days(self):
        sick_time_off_100_type = self.env.ref("hr_work_entry.sa_work_entry_type_sick_leave")
        sick_time_off_75_type = self.env.ref("hr_work_entry.l10n_sa_work_entry_type_sick_leave_75")
        self.env['hr.leave'].create(
            {
                'employee_id': self.saudi_employee.id,
                'work_entry_type_id': sick_time_off_75_type.id,
                'request_date_from': date(2026, 7, 1),
                'request_date_from_period': 'am',
                'request_date_to': date(2026, 7, 15),
                'request_date_to_period': 'am',
            }
        )
        self.env['hr.leave'].create(
            {
                'employee_id': self.saudi_employee.id,
                'work_entry_type_id': sick_time_off_100_type.id,
                'request_date_from': date(2026, 7, 16),
                'request_date_from_period': 'pm',
                'request_date_to': date(2026, 8, 19),
                'request_date_to_period': 'am',
            }
        )
        leaves = self.env['hr.leave'].search([('employee_id', '=', self.saudi_employee.id)]).sorted('date_from')
        expected_values = [
            {
                'work_entry_type_id': sick_time_off_100_type,
                'number_of_days': 10.5,
                'request_date_from': date(2026, 7, 1),
                'request_date_from_period': 'am',
                'request_date_to': date(2026, 7, 15),
                'request_date_to_period': 'am',
            }, {
                'work_entry_type_id': sick_time_off_100_type,
                'number_of_days': 19.5,
                'request_date_from': date(2026, 7, 16),
                'request_date_from_period': 'pm',
                'request_date_to': date(2026, 8, 12),
                'request_date_to_period': 'pm',
            }, {
                'work_entry_type_id': sick_time_off_75_type,
                'number_of_days': 4.5,
                'request_date_from': date(2026, 8, 13),
                'request_date_from_period': 'am',
                'request_date_to': date(2026, 8, 19),
                'request_date_to_period': 'am',
            },
        ]
        for i in range(len(leaves)):
            for field, value in expected_values[i].items():
                self.assertEqual(leaves[i][field], value)

    def test_eos_rule_fired(self):
        """fired employees receive no end of service benefit
        start_date = 2022-01-01
        departure_date = 2025-06-14 (3.5 years using 360-day convention)
        total_days = 1260 days = 3.5 * 360
        total_years = 3.5 years
        EOS Benefit = 0

        EOSP provisions accrued = 3 months * (16_800 / 12 / 2) = 2_100
        EOSPC = 0 - 2_100 = -2_100
        """
        self._test_eos_calculation(
            start_date=date(2022, 1, 1),
            end_date=date(2025, 6, 14),
            dismissal_date=date(2025, 6, 14),
            departure_reason_id=self.env.ref('hr.departure_fired').id,
            payslip_start=date(2025, 6, 1),
            payslip_end=date(2025, 6, 30),
            expected_eosb=0.0,
            expected_eospc=-2_100.0,
            prior_months=3,
        )

    def test_eos_rule_clause_77_indefinite_term(self):
        """Case: Employee worked 4 years and 3 months under an indefinite-term contract
        Expected: EOSP compensation based on the higher of:
                (a) 15-day wage per year of service, or
                (b) 2 months' salary

        start_date = 2021-01-01
        departure_date = 2025-04-01
        total_service = 4 years and 3 months = 4.308333... years

        monthly_compensation = wage + housing + transportation + other
        monthly_compensation = 15_000 + 1_000 + 500 + 300 = 16_800

        fifteen_day_wage = 16_800 / 2 = 8_400

        service_based_benefit = 4.308333... * 8_400 = 36_190
        minimum_benefit = 2 * 16_800 = 33_600

        EOS Benefit = max(36_190, 33_600) = 36_190

        EOSP provisions accrued = 3 months * (16_800 / 12 / 2) = 2_100

        EOSPC = 36_190 - 2_100 = 34_090
        """
        self._test_eos_calculation(
            start_date=date(2021, 1, 1),
            end_date=False,
            dismissal_date=date(2025, 4, 1),
            departure_reason_id=self.env.ref('l10n_sa_hr_payroll.saudi_departure_company_article_77').id,
            payslip_start=date(2025, 4, 1),
            payslip_end=date(2025, 4, 30),
            expected_eosb=33_600.0,
            expected_eospc=31_500.0,
            prior_months=3,
        )

    def test_eos_rule_resigned_less_than_2_years(self):
        """Case: Employee worked 1.5 years and resigned
        Expected: No EOS benefit (requires at least 2 years for resignation)

        start_date = 2023-07-01
        departure_date = 2024-12-22 (1.5 years using 360-day convention)
        total_days = 540 days = 1.5 * 360
        compensation = 15_000 + 1_000 + 500 + 300 = 16_800
        total_years = 1.5 years

        EOS Benefit = 0  (less than 2 years)
        EOSP provisions accrued = 3 months * (16_800 / 12 / 2) = 2_100
        EOSPC = 0 - 2_100 = -2_100
        """
        self._test_eos_calculation(
            start_date=date(2023, 7, 1),
            end_date=date(2024, 12, 22),
            dismissal_date=date(2024, 12, 22),
            departure_reason_id=self.env.ref('hr.departure_resigned').id,
            payslip_start=date(2024, 12, 1),
            payslip_end=date(2024, 12, 31),
            expected_eosb=0.0,
            expected_eospc=-2_100.0,
            prior_months=3
        )

    def test_eos_rule_resigned_between_2_10_years(self):
        """Case: Employee worked 5 years and resigned
        For 2 <= years < 10: EOS = (years * compensation / 2) / 3

        start_date = 2020-01-01
        departure_date = 2024-12-05 (5 years using 360-day convention)
        total_days = 1800 days = 5 * 360
        compensation = 15_000 + 1_000 + 500 + 300 = 16_800

        total_years = 5 years
        EOS = (5 * 16_800 / 2) / 3
        EOS = 14_000

        EOSP provisions accrued = 3 months * (16_800 / 12 / 2) = 2_100
        EOSPC = 14_000 - 2_100 = 11_900
        """
        self._test_eos_calculation(
            start_date=date(2020, 1, 1),
            end_date=date(2024, 12, 5),
            dismissal_date=date(2024, 12, 5),
            departure_reason_id=self.env.ref('hr.departure_resigned').id,
            payslip_start=date(2024, 12, 1),
            payslip_end=date(2024, 12, 31),
            expected_eosb=14_000.0,
            expected_eospc=11_900.0,
            prior_months=3
        )

    def test_eos_rule_resigned_more_than_10_years(self):
        """Case: Employee worked 12 years and resigned
        For years >= 10: EOS = (5 * compensation / 2) + ((years - 5) * compensation)

        start_date = 2013-01-01
        departure_date = 2024-10-30 (12 years using 360-day convention)
        total_days = 4320 days = 12 * 360
        compensation = 15_000 + 1_000 + 500 + 300 = 16_800

        total_years = 12 years
        EOS = (5 * 16_800 / 2) + ((12 - 5) * 16_800)
        EOS = 159_600

        EOSP provisions accrued = 3 months * (16_800 / 12) = 4_200
        EOSPC = 159_600 - 4_200 = 155_400
        """
        self._test_eos_calculation(
            start_date=date(2013, 1, 1),
            end_date=date(2024, 10, 30),
            dismissal_date=date(2024, 10, 30),
            departure_reason_id=self.env.ref('hr.departure_resigned').id,
            payslip_start=date(2024, 10, 1),
            payslip_end=date(2024, 10, 31),
            expected_eosb=159_600.0,
            expected_eospc=155_400.0,
            prior_months=3
        )

    def test_eos_rule_end_of_contract_less_than_1_year(self):
        """Case: Employee worked 9 months, end of contract
        For years < 1: EOS = 0 (no benefit for less than 1 year)

        start_date = 2024-04-01
        departure_date = 2024-12-16 (0.75 years = 9 months using 360-day convention)
        total_days = 270 days = 0.75 * 360
        compensation = 15_000 + 1_000 + 500 + 300 = 16_800

        total_years = 0.75 years
        EOS = 0  (less than 1 year)
        EOSP provisions accrued = 3 months * (16_800 / 12 / 2) = 2_100
        EOSPC = 0 - 2_100 = -2_100
        """
        self._test_eos_calculation(
            start_date=date(2024, 4, 1),
            end_date=date(2024, 12, 16),
            dismissal_date=date(2024, 12, 16),
            departure_reason_id=self.env.ref('l10n_sa_hr_payroll.saudi_departure_end_of_contract').id,
            payslip_start=date(2024, 12, 1),
            payslip_end=date(2024, 12, 31),
            expected_eosb=0.0,
            expected_eospc=-2_100.0,
            prior_months=3
        )

    def test_eos_rule_end_of_contract_between_1_5_years(self):
        """Case: Employee worked 3 years, end of contract
        For 1 <= years <= 5: EOS = years * compensation / 2

        start_date = 2022-01-01
        departure_date = 2024-12-16 (3 years using 360-day convention)
        total_days = 1080 days = 3 * 360
        compensation = 15_000 + 1_000 + 500 + 300 = 16_800

        total_years = 3 years
        EOS = 3 * 16_800 / 2
        EOS = 25_200

        EOSP provisions accrued = 3 months * (16_800 / 12 / 2) = 2_100
        EOSPC = 25_200 - 2_100 = 23_100
        """
        self._test_eos_calculation(
            start_date=date(2022, 1, 1),
            end_date=date(2024, 12, 16),
            dismissal_date=date(2024, 12, 16),
            departure_reason_id=self.env.ref('l10n_sa_hr_payroll.saudi_departure_end_of_contract').id,
            payslip_start=date(2024, 12, 1),
            payslip_end=date(2024, 12, 31),
            expected_eosb=25_200.0,
            expected_eospc=23_100.0,
            prior_months=3
        )

    def test_eos_rule_retired_more_than_5_years(self):
        """Case: Employee worked 8 years and retired
        For years > 5: EOS = (5 * compensation / 2) + ((years - 5) * compensation)

        start_date = 2017-01-01
        departure_date = 2024-11-20 (8 years using 360-day convention)
        total_days = 2880 days = 8 * 360
        compensation = 15_000 + 1_000 + 500 + 300 = 16_800

        total_years = 8 years
        EOS = (5 * 16_800 / 2) + ((8 - 5) * 16_800)
        EOS = 92_400

        EOSP provisions accrued = 3 months * (16_800 / 12) = 4_200
        EOSPC = 92_400 - 4_200 = 88_200
        """
        self._test_eos_calculation(
            start_date=date(2017, 1, 1),
            end_date=date(2024, 11, 20),
            dismissal_date=date(2024, 11, 20),
            departure_reason_id=self.env.ref('hr.departure_retired').id,
            payslip_start=date(2024, 11, 1),
            payslip_end=date(2024, 11, 30),
            expected_eosb=92_400.0,
            expected_eospc=88_200.0,
            prior_months=3
        )

    def test_net_cost_calculation(self):
        new_category = self.env['hr.salary.rule.category'].create({
            'name': 'new_category',
            'code': 'new_cat',
            'parent_id': self.env.ref('hr_payroll.COMP').id,
            'country_id': self.country.id
        })
        new_child = self.env['hr.salary.rule.category'].create({
            'name': 'new_child_category',
            'code': 'new_ch_cat',
            'parent_id': new_category.id,
            'country_id': self.country.id
        })
        simple_salary_rule = self.env['hr.salary.rule'].create({
            'name': 'new_rule',
            'code': 'new_ru',
            'category_ids': [(4, new_child.id)],
            'amount_fix': 100,
            'struct_ids': [(4, self.structure.id)]
        })
        double_cat_salary_rule = self.env['hr.salary.rule'].create({
            'name': 'new_rule_2',
            'code': 'new_ru2',
            'category_ids': [(4, new_category.id), (4, self.env.ref('hr_payroll.DED').id)],
            'amount_fix': 200,
            'struct_ids': [(4, self.structure.id)]
        })
        negative_salary_rule = self.env['hr.salary.rule'].create({
            'name': 'new_rule_3',
            'code': 'new_ru3',
            'category_ids': [(4, self.env.ref('hr_payroll.COMP').id)],
            'amount_fix': -50,
            'struct_ids': [(4, self.structure.id)]
        })
        _irrelevant_salary_rule = self.env['hr.salary.rule'].create({
            'name': 'new_rule_4',
            'code': 'new_ru4',
            'category_ids': [(4, self.env.ref('hr_payroll.DED').id)],
            'amount_fix': -500,
            'struct_ids': [(4, self.structure.id)]
        })

        test_payslip = self.env['hr.payslip'].create({
            'employee_id': self.saudi_employee.id,
            'date_from': date(2025, 1, 1),
            'date_to': date(2025, 1, 31),
            'struct_id': self.structure.id,
        }).with_company(self.sa_company)
        test_payslip.compute_sheet()
        company_contribution = abs(simple_salary_rule.amount_fix) \
                             + abs(double_cat_salary_rule.amount_fix) \
                             + abs(negative_salary_rule.amount_fix) \
                             + abs(test_payslip._get_line_values(['GOSI_COMP'])['GOSI_COMP'][test_payslip.id]['total']) \
                             + abs(test_payslip._get_line_values(['GOSI_EMP'])['GOSI_EMP'][test_payslip.id]['total']) \
                             + abs(test_payslip._get_line_values(['MEDICAL'])['MEDICAL'][test_payslip.id]['total']) \
                             + abs(test_payslip._get_line_values(['IQAMA'])['IQAMA'][test_payslip.id]['total']) \
                             + abs(test_payslip._get_line_values(['WORKPER'])['WORKPER'][test_payslip.id]['total'])
        expected_net_cost = test_payslip.net_wage + company_contribution
        calcuted_net_cost = test_payslip._get_line_values(['NETCOST'])['NETCOST'][test_payslip.id]['total']
        self.assertEqual(calcuted_net_cost, expected_net_cost, "Net Cost calculation is incorrect")
