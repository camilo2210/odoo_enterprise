# Part of Odoo. See LICENSE file for full copyright and licensing details.
from freezegun import freeze_time
from psycopg2.errors import UniqueViolation

from odoo import Command
from odoo.tests import tagged, mute_logger

from .common import L10nPayrollAccountCommon
from .tools import mock_skip_stp_api_calls
from odoo.exceptions import UserError


@tagged("post_install_l10n", "post_install", "-at_install")
class TestPayslipYTD(L10nPayrollAccountCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['l10n_au.stp'].search([]).unlink()
        cls.company.write({
            "l10n_au_bms_id": "TEST_BMS_ID",
            "vat": "83914571673",
            "email": "au_company@odoo.com",
            "phone": "123456789",
            "zip": "2000",
            "l10n_au_branch_code": "100"
        })
        cls.company2 = cls._create_company(
            name="other_company",
            l10n_au_bms_id="TEST_BMS_ID2",
            vat="83914571673",
            email="au_company2@odoo.com",
            phone="1234567890",
            zip="2001",
            l10n_au_branch_code="101"
        )
        cls.employee_3, cls.employee_4 = cls.env["hr.employee"].with_company(cls.company2).create([
            {
                "name": "Mel Gibson (Company 2)",
                "resource_calendar_id": cls.company2.resource_calendar_id.id,
                "company_id": cls.company2.id,
                "user_id": cls.employee_user_1.id,
                "work_contact_id": cls.employee_contact_1.id,
                "work_phone": "123456789",
                "work_email": "mel.company2@gmail.com",
                "private_phone": "123456789",
                "private_email": "mel.company2@odoo.com",
                "private_street": "1 Test Street",
                "private_city": "Sydney",
                "private_state_id": cls.env.ref("base.state_au_2").id,
                "private_zip": "2000",
                "private_country_id": cls.env.ref("base.au").id,
                "birthday": "2000-01-01",
                "l10n_au_tfn_declaration": "provided",
                "l10n_au_tfn": "999999661",
                "l10n_au_tax_free_threshold": True,
                "sex": "male",
                "date_version": "2023-01-01",
                "contract_date_start": "2023-01-01",
                "contract_date_end": False,
                "wage_type": "monthly",
                "wage": 5000.0,
                "structure_type_id": cls.env.ref("l10n_au_hr_payroll.structure_type_schedule_1").id,
                "schedule_pay": "monthly",
            }, {
                "name": "Harry Potter",
                "resource_calendar_id": cls.company2.resource_calendar_id.id,
                "company_id": cls.company2.id,
                'work_contact_id': cls.employee_contact_2.id,
                "work_phone": "123456789",
                "private_phone": "123456789",
                "private_email": "harry@odoo.com",
                "private_street": "1 Test Street",
                "private_city": "Sydney",
                "private_state_id": cls.env.ref("base.state_au_2").id,
                "private_zip": "2000",
                "private_country_id": cls.env.ref("base.au").id,
                "birthday": "2000-03-01",
                "l10n_au_tfn_declaration": "provided",
                "l10n_au_tfn": "999999661",
                "l10n_au_tax_free_threshold": True,
                "sex": "female",
                "date_version": "2023-01-01",
                "contract_date_start": "2023-01-01",
                "contract_date_end": False,
                "wage_type": "monthly",
                "wage": 7000.0,
                "structure_type_id": cls.env.ref("l10n_au_hr_payroll.structure_type_schedule_1").id,
                "schedule_pay": "monthly",
            }
        ])

        cls.company2.l10n_au_hr_super_responsible_id = cls.employee_3
        cls.company2.l10n_au_stp_responsible_id = cls.employee_3
        cls.company2.ytd_reset_month = "7"

        cls.PayslipYTD = cls.env["l10n_au.payslip.ytd"]
        cls.deduction_rule = cls.env.ref("hr_payroll.DED")

    def _switch_company(self, company):
        self.env = self.env(context=dict(self.env.context, allowed_company_ids=company.ids))
        self.PayslipYTD = self.env["l10n_au.payslip.ytd"]

    def _transfer_opening_balances(self, employees):
        transfer = self.env["l10n_au.previous.payroll.transfer"].create({
            "previous_bms_id": "TEST_BMS_ID",
            "fiscal_year_start_date": "2025-07-01",
            "l10n_au_previous_payroll_transfer_employee_ids": [
                (0, 0, {
                    "employee_id": employee.id,
                    "previous_payroll_id": f"previous_{employee.id}",
                    "l10n_au_income_stream_type": employee.l10n_au_income_stream_type,
                })
                for employee in employees
            ],
        })
        transfer.action_transfer()
        stp_update = self.env["l10n_au.stp"].search([("company_id", "=", self.env.company.id)])
        self._submit_stp(stp_update)

    @freeze_time("2025-09-01")
    @mock_skip_stp_api_calls()
    def test_create_salary_rule_adds_missing_opening_balances(self):

        expected_codes = [
            'BASIC', 'EXTRA', 'SALARY.SACRIFICE.OTHER', 'WORKPLACE.GIVING',
            'ALW', 'RTW', 'ALW.TAXFREE', 'BACKPAY', 'WITHHOLD.TOTAL',
            'CHILD.SUPPORT', 'SUPER', 'SUPER.CONTRIBUTION', 'RFBA', 'DED.POST'
        ]
        # Create opening balances for employees. 14 Base rules for each employee
        self._transfer_opening_balances(self.employee_1 + self.employee_2)
        balances = self.PayslipYTD._read_group([
            ("employee_id", "in", (self.employee_1 + self.employee_2).mapped("id")),
            ("start_date", "=", "2025-07-01"),
        ], groupby=["employee_id"], aggregates=["code:array_agg"])

        for employee, codes in balances:
            self.assertListEqual(
                sorted(codes),
                sorted(expected_codes),
                "Employee %s has unexpected opening balances: %s" % (employee.name, codes)
            )

        # Allow regeneration of YTD values for new rules after a payslip has been created
        self._prepare_payslip_run(self.employee_1 + self.employee_2, start_date="2025-09-01", end_date="2025-09-30")

        # Create new deduction rule
        self.env["hr.salary.rule"].create({
            "name": "Novated Lease",
            "code": "NOVATED.LEASE",
            "struct_ids": [Command.set(self.default_payroll_structure.ids)],
            "category_ids": [Command.set(self.deduction_rule.ids)],
            "amount_select": "fix",
            "amount_fix": 0.0,
        })

        self.PayslipYTD.action_regenerate_ytd_values()
        expected_codes.append("NOVATED.LEASE")
        balances = self.PayslipYTD._read_group([
            ("employee_id", "in", (self.employee_1 + self.employee_2).mapped("id")),
            ("start_date", "=", "2025-07-01"),
        ], groupby=["employee_id"], aggregates=["code:array_agg"])

        for employee, codes in balances:
            self.assertListEqual(
                sorted(codes),
                sorted(expected_codes),
                "Employee %s has unexpected opening balances: %s" % (employee.name, codes)
            )

        # Prevent a new imports and update of opening balances after a payslip has been created
        with self.assertRaises(UniqueViolation), mute_logger("odoo.sql_db"):
            self._transfer_opening_balances(self.employee_1 + self.employee_2)
        with self.assertRaises(UserError):
            self.PayslipYTD.search([("code", "=", "NOVATED.LEASE")]).write({"start_value": 100})

    @freeze_time("2025-09-01")
    @mock_skip_stp_api_calls()
    def test_regenerate_ytd_multi_company(self):
        """ Test that YTD values are regenerated for the correct company when multiple companies exist. """
        self.assertEqual(self.company, self.env.company, "The test should start with the first company as the current company")
        self._transfer_opening_balances(self.employee_1 + self.employee_2)
        balance_count = self.PayslipYTD.search_count([("start_date", "=", "2025-07-01"), ("company_id", "=", self.company.id)])
        self.assertEqual(balance_count, 28, "There should be 28 opening balances for the first company (14 for each employee)")

        self._switch_company(self.company2)
        self._transfer_opening_balances(self.employee_3 + self.employee_4)
        balance_count = self.PayslipYTD.search_count([("start_date", "=", "2025-07-01"), ("company_id", "=", self.company2.id)])
        self.assertEqual(balance_count, 28, "There should be 28 opening balances for the second company (14 for each employee)")

        # Create new deduction rule
        self.env["hr.salary.rule"].create({
            "name": "Novated Lease",
            "code": "NOVATED.LEASE",
            "struct_ids": [Command.set(self.default_payroll_structure.ids)],
            "category_ids": [Command.set(self.deduction_rule.ids)],
            "amount_select": "fix",
            "amount_fix": 0.0,
        })

        # Only generate for the current company (company2)
        self._switch_company(self.company2)
        self.PayslipYTD.action_regenerate_ytd_values()
        balance_count = self.PayslipYTD.search_count([("start_date", "=", "2025-07-01"), ("company_id", "=", self.company2.id)])
        self.assertEqual(balance_count, 30, "2 additional opening balances should have been created")

        self._switch_company(self.company)
        balance_count = self.PayslipYTD.search_count([("start_date", "=", "2025-07-01"), ("company_id", "=", self.company.id)])
        self.assertEqual(balance_count, 28, "No additional opening balances should have been created for the first company")
