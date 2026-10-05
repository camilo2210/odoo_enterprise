from .common import TestSACommon
from odoo.tests.common import tagged
from odoo.addons.mail.tests.common import mail_new_test_user
from datetime import date
from odoo.exceptions import AccessError, UserError


@tagged("post_install", "post_install_l10n", "-at_install", "payslips_validation")
class TestLeaveAdvancePay(TestSACommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.user_base = mail_new_test_user(
            cls.env, login="SA Base User", groups="base.group_user"
        )
        cls.user_holidays_officer = mail_new_test_user(
            cls.env,
            login="SA Holidays Officer",
            groups="base.group_user,hr_holidays.group_hr_holidays_user",
        )
        cls.user_payroll_assistant = mail_new_test_user(
            cls.env,
            login="SA Payroll Assistant",
            groups="base.group_user,hr_payroll.group_hr_payroll_user",
        )

        cls.sick_work_entry_type = cls.env.ref("hr_work_entry.sa_work_entry_type_sick_leave")
        cls.paid_time_off_type = cls.env.ref("hr_work_entry.sa_work_entry_type_legal_leave")

        cls.env.company.l10n_sa_annual_work_entry_type_id = cls.paid_time_off_type
        cls.sa_employee_struct_id = cls.env.ref(
            "l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure"
        )
        cls.saudi_employee.version_id.schedule_pay = '30_monthly'

        cls.env["hr.leave.allocation"].create(
            {
                "name": "Saudi Employee Paid Time Off Allocation",
                "employee_id": cls.saudi_employee.id,
                "work_entry_type_id": cls.paid_time_off_type.id,
                "number_of_days": 30,
                "date_from": date(2024, 1, 1),
            }
        ).action_approve()

    def test_leave_advance_access(self):
        """
        - Users that are not at least a Payroll Assistant should not be able to create an advance leave pay.
        - Being a Payroll Assistant implies being a Time Off Officer.
        """
        paid_leave = self.env["hr.leave"].create(
            {
                "name": "Paid Time Off Jan",
                "employee_id": self.saudi_employee.id,
                "work_entry_type_id": self.paid_time_off_type.id,
                "request_date_from": date(2024, 1, 1),
                "request_date_to": date(2024, 1, 5),
            }
        )
        with self.assertRaises(AccessError):
            paid_leave.with_user(self.user_base).action_create_sa_leave_advance_pay()
        with self.assertRaises(AccessError):
            paid_leave.with_user(
                self.user_holidays_officer
            ).action_create_sa_leave_advance_pay()
        paid_leave.with_user(
            self.user_payroll_assistant
        ).action_create_sa_leave_advance_pay()

    def test_leave_advance_validation(self):
        """
        Validate advance leave pay creation rules.

        An advance leave pay can only be created when:
            - The user is logged into a Saudi Arabian company.
            - The leave type matches the company Annual Leave Time-off Type.
            - The leave is validated.
            - The selected salary structure includes a salary rule with code "LEAVEADVPAY".
            - At most one payslip exists for the same period, employee, structure, and version.
            - No validated payslip exists for the same period, employee, structure, and version.
        """

        # Validation: user must be logged into a Saudi Arabian company
        us_company = self.env["res.company"].create(
            {
                "name": "United States Company",
                "country_id": self.env.ref("base.us").id,
            }
        )
        self.env = self.env(
            context=dict(
                self.env.context,
                allowed_company_ids=(us_company.ids + self.sa_company.ids),
            )
        )

        paid_leave = self.env["hr.leave"].create(
            {
                "name": "Paid Time Off Jan",
                "employee_id": self.saudi_employee.id,
                "work_entry_type_id": self.paid_time_off_type.id,
                "request_date_from": date(2024, 1, 1),
                "request_date_to": date(2024, 1, 5),
            }
        )

        with self.assertRaises(
            UserError,
            msg="You must log in to a Saudi Arabian company to use this action.",
        ):
            paid_leave.action_create_sa_leave_advance_pay()

        self.env = self.env(
            context=dict(self.env.context, allowed_company_ids=self.sa_company.ids)
        )

        # Validation: leave type must match the company Annual Leave Time-off Type
        sick_leave = self.env["hr.leave"].create(
            {
                "name": "Paid Time Off Jan",
                "employee_id": self.saudi_employee.id,
                "work_entry_type_id": self.sick_work_entry_type.id,
                "request_date_from": date(2024, 1, 6),
                "request_date_to": date(2024, 1, 10),
            }
        )

        with self.assertRaises(
            UserError,
            msg="The leave type in the leave request must match the company's Annual Leave Time-off Type.",
        ):
            sick_leave.action_create_sa_leave_advance_pay()

        # Validation: leave must be validated before creating advance leave pay
        paid_leave = self.env["hr.leave"].with_context(leave_fast_create=True).create(
            {
                "name": "Paid Time Off Jan",
                "employee_id": self.saudi_employee.id,
                "work_entry_type_id": self.paid_time_off_type.id,
                "request_date_from": date(2024, 1, 12),
                "request_date_to": date(2024, 1, 16),
            }
        )

        with self.assertRaises(
            UserError,
            msg="The leave must be validated to perform this action.",
        ):
            paid_leave.action_create_sa_leave_advance_pay()

        # Validation: salary structure must include LEAVEADVPAY salary rule
        paid_leave.action_approve()
        leave_advance_pay_wizard = (
            self.env["hr.leave.advance.pay"]
            .with_context(hr_leave_id=paid_leave.id)
            .create(
                {
                    "struct_id": self.env.ref(
                        "l10n_sa_hr_payroll.l10n_sa_salary_advance_and_loan"
                    ).id,
                }
            )
        )

        with self.assertRaises(
            UserError,
            msg=(
                "The selected salary structure does not have a dedicated salary rule "
                "for the leave advance pay. Please create a salary rule using the "
                "following code: LEAVEADVPAY"
            ),
        ):
            leave_advance_pay_wizard.action_populate_payslip()

        # Validation: only one payslip may exist for the same period, structure, and version
        leave_advance_pay_wizard.struct_id = self.sa_employee_struct_id.id

        payslip_jan_1 = self._generate_payslip(
            date_from=date(2024, 1, 1),
            date_to=date(2024, 1, 31),
            struct_id=self.sa_employee_struct_id.id,
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
        )
        payslip_jan_2 = self._generate_payslip(
            date_from=date(2024, 1, 1),
            date_to=date(2024, 1, 31),
            struct_id=self.sa_employee_struct_id.id,
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
        )

        with self.assertRaises(
            UserError,
            msg=(
                "There are duplicated payslips having the same version and salary "
                "structure. The action can only be used if there is at most one "
                "payslip created for the same period."
            ),
        ):
            leave_advance_pay_wizard.action_populate_payslip()

        # Validation: no validated payslip may already exist for the same period
        payslip_jan_2.unlink()
        payslip_jan_1.action_payslip_done()

        with self.assertRaises(
            UserError,
            msg="A validated payslip already exists for the current period: %(payslip)s",
        ):
            leave_advance_pay_wizard.action_populate_payslip()

        # Success case: all validation rules are satisfied
        payslip_jan_1.action_payslip_draft()
        leave_advance_pay_wizard.action_populate_payslip()

    def test_one_leave_advance_overlapping_one_month(self):
        """
        A leave is created and approved for January. An advance leave pay is created for this leave.
        Since the leave ends in the same month it starts, no advance pay should be given to the
        employee and the payslip input "LEAVEADVPAY" should be 0.

        - Paid leaves table (All dates are inclusive)
        | Name | Date from   | Date to     |        Duration      |
        | ---- | ----------- | ----------- | -------------------- |
        | 1st  | 01/Jan/2024 | 05/Jan/2024 |           5          |

        - Payslips table (Daily wage is 13700 / 30 ~= 456,666667)
        | Period | # of leaves paid in advance | # of leaves recovered |  LEAVEADVPAY payslip line |  LEAVERECPAY payslip line |
        | ------ | --------------------------- | --------------------- | ------------------------- | ------------------------- |
        | Jan 24 |              0              |            0          | 0     *   456,67 = 0      | 0     *   456,67 = 0      |
        """
        paid_leave = self.env["hr.leave"].create(
            {
                "name": "Paid Time Off Jan",
                "employee_id": self.saudi_employee.id,
                "work_entry_type_id": self.paid_time_off_type.id,
                "request_date_from": date(2024, 1, 1),
                "request_date_to": date(2024, 1, 5),
            }
        )
        leave_advance_pay_wizard = (
            self.env["hr.leave.advance.pay"]
            .with_context(hr_leave_id=paid_leave.id)
            .create(
                {
                    "struct_id": self.sa_employee_struct_id.id,
                }
            )
        )
        act_dict = leave_advance_pay_wizard.action_populate_payslip()
        payslip = self.env["hr.payslip"].browse(act_dict["res_id"])
        self.assertEqual(payslip._get_input_line_amount("LEAVEADVPAY"), 0)
        self.assertEqual(payslip._get_input_line_amount("LEAVERECPAY"), 0)
        payslip.compute_sheet()
        line_values = payslip._get_line_values(["LEAVEADVPAY", "LEAVERECPAY"])
        self.assertEqual(line_values["LEAVEADVPAY"][payslip.id]["total"], 0)
        self.assertEqual(line_values["LEAVERECPAY"][payslip.id]["total"], 0)

    def test_one_leave_advance_overlapping_two_months(self):
        """
        A leave that overlaps between two months is created and approved for January and February.
        An advance leave pay is created for this leave.

        - Paid leaves table (All dates are inclusive)
        | Name | Date from   | Date to     |        Duration      |
        | ---- | ----------- | ----------- | -------------------- |
        | 1st  | 01/Jan/2024 | 13/Feb/2024 | 5 Jan + 9 Feb  =  14 |

        - Payslips table (Daily wage is 13700 / 30 ~= 456,666667)
        | Period | # of leaves paid in advance | # of leaves recovered |  LEAVEADVPAY payslip line |  LEAVERECPAY payslip line |
        | ------ | --------------------------- | --------------------- | ------------------------- | ------------------------- |
        | Jan 24 |              9              |            0          | 9     *   456,67 = 4110.0 | 0     *   456,67 = 0      |
        | Feb 24 |              0              |            9          | 0     *   456,67 = 0      | 9     *   456,67 = 4110.0 |
        """
        paid_leave = self.env["hr.leave"].create(
            {
                "name": "Paid Time Off Jan -> Feb",
                "employee_id": self.saudi_employee.id,
                "work_entry_type_id": self.paid_time_off_type.id,
                "request_date_from": date(2024, 1, 25),
                "request_date_to": date(2024, 2, 13),
            }
        )
        leave_advance_pay_wizard = (
            self.env["hr.leave.advance.pay"]
            .with_context(hr_leave_id=paid_leave.id)
            .create(
                {
                    "struct_id": self.sa_employee_struct_id.id,
                }
            )
        )
        act_dict = leave_advance_pay_wizard.action_populate_payslip()
        payslip_jan = self.env["hr.payslip"].browse(act_dict["res_id"])
        self.assertEqual(payslip_jan._get_input_line_amount("LEAVEADVPAY"), 9)
        self.assertEqual(payslip_jan._get_input_line_amount("LEAVERECPAY"), 0)
        payslip_jan.compute_sheet()
        payslip_jan_results = {
            "LEAVEADVPAY": 4110.0,
        }
        self._validate_payslip(payslip_jan, payslip_jan_results, skip_lines=True)
        payslip_jan.action_payslip_done()

        payslip_feb = self._generate_payslip(
            date_from=date(2024, 2, 1),
            date_to=date(2024, 2, 29),
            struct_id=self.sa_employee_struct_id.id,
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
        )
        payslip_feb._compute_input_line_ids()
        self.assertEqual(payslip_feb._get_input_line_amount("LEAVEADVPAY"), 0)
        self.assertEqual(payslip_feb._get_input_line_amount("LEAVERECPAY"), 9)
        payslip_feb_results = {
            "LEAVERECPAY": -4110.0,
        }
        payslip_feb.compute_sheet()
        self._validate_payslip(payslip_feb, payslip_feb_results, skip_lines=True)

    def test_one_leave_advance_overlapping_three_months(self):
        """
        A leave that overlaps three months is created and approved for January, February and March.
        An advance leave pay is created for this leave.

        - Paid leaves table (All dates are inclusive)
        | Name | Date from   | Date to     |            Duration           |
        | ---- | ----------- | ----------- | ----------------------------- |
        | 1st  | 29/Jan/2024 | 05/Mar/2024 | 3 Jan + 21 Feb + 3 Mar  =  26 |

        - Payslips table (Daily wage is 13700 / 30 ~= 456,666667)
        | Period | # of leaves paid in advance | # of leaves recovered |  LEAVEADVPAY payslip line  |  LEAVERECPAY payslip line |
        | ------ | --------------------------- | --------------------- | -------------------------- | ------------------------- |
        | Jan 24 |              24             |            0          | 24    *   456,67 = 10960.0 | 0     *   456,67 = 0      |
        | Feb 24 |              0              |            21         | 0     *   456,67 = 0       | 21    *   456,67 = 9590.0 |
        | Mar 24 |              0              |            3          | 0     *   456,67 = 0       | 3     *   456,67 = 1370.0 |
        """
        paid_leave = self.env["hr.leave"].create(
            {
                "name": "Paid Time Off Jan -> Mar",
                "employee_id": self.saudi_employee.id,
                "work_entry_type_id": self.paid_time_off_type.id,
                "request_date_from": date(2024, 1, 25),
                "request_date_to": date(2024, 3, 5),
            }
        )
        leave_advance_pay_wizard = (
            self.env["hr.leave.advance.pay"]
            .with_context(hr_leave_id=paid_leave.id)
            .create(
                {
                    "struct_id": self.sa_employee_struct_id.id,
                }
            )
        )
        act_dict = leave_advance_pay_wizard.action_populate_payslip()
        payslip_jan = self.env["hr.payslip"].browse(act_dict["res_id"])
        self.assertEqual(payslip_jan._get_input_line_amount("LEAVEADVPAY"), 24)
        self.assertEqual(payslip_jan._get_input_line_amount("LEAVERECPAY"), 0)
        payslip_jan.compute_sheet()
        payslip_jan_results = {
            "LEAVEADVPAY": 10960.0,
        }
        self._validate_payslip(payslip_jan, payslip_jan_results, skip_lines=True)
        payslip_jan.action_payslip_done()

        payslip_feb = self._generate_payslip(
            date_from=date(2024, 2, 1),
            date_to=date(2024, 2, 29),
            struct_id=self.sa_employee_struct_id.id,
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
        )
        payslip_feb._compute_input_line_ids()
        self.assertEqual(payslip_feb._get_input_line_amount("LEAVEADVPAY"), 0)
        self.assertEqual(payslip_feb._get_input_line_amount("LEAVERECPAY"), 21)
        payslip_feb_results = {
            "LEAVERECPAY": -9590.0,
        }
        payslip_feb.compute_sheet()
        self._validate_payslip(payslip_feb, payslip_feb_results, skip_lines=True)
        payslip_feb.action_payslip_done()

        payslip_mar = self._generate_payslip(
            date_from=date(2024, 3, 1),
            date_to=date(2024, 3, 31),
            struct_id=self.sa_employee_struct_id.id,
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
        )
        payslip_mar._compute_input_line_ids()
        self.assertEqual(payslip_mar._get_input_line_amount("LEAVEADVPAY"), 0)
        self.assertEqual(payslip_mar._get_input_line_amount("LEAVERECPAY"), 3)
        payslip_mar_results = {
            "LEAVERECPAY": -1370.0,
        }
        payslip_mar.compute_sheet()
        self._validate_payslip(payslip_mar, payslip_mar_results, skip_lines=True)

    def test_two_leave_advance_overlapping_three_months(self):
        """
        Two leaves overlapping three months is created and approved for January, February and March.
        An advance leave pay is created for this leave.

        - Paid leaves table (All dates are inclusive)
        | Name | Date from   | Date to     |            Duration           |
        | ---- | ----------- | ----------- | ----------------------------- |
        | 1st  | 29/Jan/2024 | 07/Feb/2024 | 5 Jan + 5 Feb           =  10 |
        | 1st  | 23/Feb/2024 | 11/Mar/2024 | 5 Feb + 7 Feb           =  12 |

        - Payslips table (Daily wage is 13700 / 30 ~= 456,666667)
        | Period | # of leaves paid in advance | # of leaves recovered |  LEAVEADVPAY payslip line  |  LEAVERECPAY payslip line  |
        | ------ | --------------------------- | --------------------- | -------------------------- | -------------------------- |
        | Jan 24 |              5              |            0          | 5     *   456,67 = 2283.33 | 0     *   456,67 = 0       |
        | Feb 24 |              7              |            5          | 7     *   456,67 = 3196.67 | 5     *   456,67 = 2283.33 |
        | Mar 24 |              0              |            7          | 0     *   456,67 = 0       | 7     *   456,67 = 3196.67 |
        """
        paid_leaves = self.env["hr.leave"].create(
            [
                {
                    "name": "Paid Time Off Jan -> Feb",
                    "employee_id": self.saudi_employee.id,
                    "work_entry_type_id": self.paid_time_off_type.id,
                    "request_date_from": date(2024, 1, 29),
                    "request_date_to": date(2024, 2, 7),
                },
                {
                    "name": "Paid Time Off Feb -> Mar",
                    "employee_id": self.saudi_employee.id,
                    "work_entry_type_id": self.paid_time_off_type.id,
                    "request_date_from": date(2024, 2, 23),
                    "request_date_to": date(2024, 3, 11),
                },
            ]
        )
        leave_advance_pay_wizard = (
            self.env["hr.leave.advance.pay"]
            .with_context(hr_leave_id=paid_leaves[0].id)
            .create(
                {
                    "struct_id": self.sa_employee_struct_id.id,
                }
            )
        )
        act_dict = leave_advance_pay_wizard.action_populate_payslip()
        payslip_jan = self.env["hr.payslip"].browse(act_dict["res_id"])
        self.assertEqual(payslip_jan._get_input_line_amount("LEAVEADVPAY"), 5)
        self.assertEqual(payslip_jan._get_input_line_amount("LEAVERECPAY"), 0)
        payslip_jan.compute_sheet()
        payslip_jan_results = {
            "LEAVEADVPAY": 2283.33,
        }
        self._validate_payslip(payslip_jan, payslip_jan_results, skip_lines=True)
        payslip_jan.action_payslip_done()

        leave_advance_pay_wizard = (
            self.env["hr.leave.advance.pay"]
            .with_context(hr_leave_id=paid_leaves[1].id)
            .create(
                {
                    "struct_id": self.sa_employee_struct_id.id,
                }
            )
        )
        act_dict = leave_advance_pay_wizard.action_populate_payslip()
        payslip_feb = self.env["hr.payslip"].browse(act_dict["res_id"])
        payslip_feb._compute_input_line_ids()
        self.assertEqual(payslip_feb._get_input_line_amount("LEAVEADVPAY"), 7)
        self.assertEqual(payslip_feb._get_input_line_amount("LEAVERECPAY"), 5)
        payslip_feb_results = {
            "LEAVEADVPAY": 3196.67,
            "LEAVERECPAY": -2283.33,
        }
        payslip_feb.compute_sheet()
        self._validate_payslip(payslip_feb, payslip_feb_results, skip_lines=True)
        payslip_feb.action_payslip_done()

        payslip_mar = self._generate_payslip(
            date_from=date(2024, 3, 1),
            date_to=date(2024, 3, 31),
            struct_id=self.sa_employee_struct_id.id,
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
        )
        payslip_mar._compute_input_line_ids()
        self.assertEqual(payslip_mar._get_input_line_amount("LEAVEADVPAY"), 0)
        self.assertEqual(payslip_mar._get_input_line_amount("LEAVERECPAY"), 7)
        payslip_mar_results = {
            "LEAVERECPAY": -3196.67,
        }
        payslip_mar.compute_sheet()
        self._validate_payslip(payslip_mar, payslip_mar_results, skip_lines=True)
