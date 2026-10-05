# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from odoo.tests import TransactionCase, tagged


@tagged("post_install_l10n", "post_install", "-at_install")
class TestMobilityBudget(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids += cls.env.ref("hr_payroll.group_hr_payroll_user")

        cls.company = cls.env["res.company"].create(
            {
                "name": "Test BE Company",
                "country_id": cls.env.ref("base.be").id,
                "currency_id": cls.env.ref("base.EUR").id,
            }
        )
        cls.company.current_payroll_config_id.write({
            'l10n_be_employer_category_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_employer_category_00010').id,
        })
        cls.env.user.company_ids |= cls.company
        cls.env = cls.env(
            context=dict(cls.env.context, allowed_company_ids=cls.company.ids)
        )
        # Create 2 accounts since approving expenses will create moves and lines will need accounts
        account, _trash = cls.env['account.account'].create([
            {
                'name': 'Expenses Account',
                'code': '600010',
                'account_type': 'expense',
                'company_ids': cls.company.ids,
            },
            {
                'name': 'Liability payable account',
                'code': '654323',
                'account_type': 'liability_payable',
            },
        ])
        cls.env['account.journal'].create({
            'name': 'Test Purchases',
            'type': 'purchase',
            'default_account_id': account.id,
            'company_id': cls.company.id,
        })

        cls.resource_calendar = cls.env["resource.calendar"].create(
            {
                "name": "Standard 40h/week",
                "company_id": cls.company.id,
            }
        )

        cls.mobility_product = cls.env["product.product"].create(
            {
                "name": "Mobility Expense",
                "can_be_expensed": True,
                "standard_price": 0.0,
            }
        )

        cls.other_product = cls.env["product.product"].create(
            {
                "name": "Other Expense",
                "can_be_expensed": True,
                "standard_price": 0.0,
            }
        )

        cls.company.l10n_be_mobility_expense_category_ids = [
            (6, 0, [cls.mobility_product.id])
        ]

        cls.employee = cls.env["hr.employee"].create(
            {
                "name": "Test Employee",
                "company_id": cls.company.id,
                "resource_calendar_id": cls.resource_calendar.id,
                "structure_type_id": cls.env.ref("hr.structure_type_employee_cp200").id,
                "date_version": date(2024, 1, 1),
                "contract_date_start": date(2024, 1, 1),
                "contract_date_end": False,
                "wage": 3000.0,
            }
        )
        cls.structure_monthly = cls.env.ref(
            "l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary"
        )
        cls.version = cls.employee.current_version_id
        cls.version.write(
            {
                "l10n_be_mobility_budget": True,
                "l10n_be_mobility_budget_amount": 1200.0,
            }
        )

        # Activate the JC200 & JC302 & JC999
        jcs_to_activate = cls.env['l10n.be.joint.committee'].with_context(active_test=False).search([('egov3_code', 'in', ('200', '302', '999'))])
        jcs_to_activate.write({'active': True})

    def _create_expense(self, product, amount, date_val, state="draft"):
        expense = self.env["hr.expense"].create(
            {
                "name": "Test Expense",
                "employee_id": self.employee.id,
                "product_id": product.id,
                "total_amount_currency": amount,
                "date": date_val,
                "company_id": self.company.id,
            }
        )
        if state != "draft":
            expense.action_submit()
            expense.action_approve()
            if state in ("posted", "paid"):
                expense.account_move_id.action_post()
        return expense

    def _create_payslip(self, date_from, date_to):
        payslip = self.env["hr.payslip"].create(
            {
                "name": f"Payslip {date_from.strftime('%B %Y')}",
                "version_id": self.version.id,
                "date_from": date_from,
                "date_to": date_to,
                "employee_id": self.employee.id,
                "struct_id": self.structure_monthly.id,
                "company_id": self.company.id,
            }
        )
        payslip.compute_sheet()
        return payslip

    def _get_mobility_payment_amount(self, payslip):
        value = payslip._get_input_line_amount("MOBILITY_PAYMENT")
        return value or 0.0

    def test_compute_mobility_budget_no_expenses(self):
        expense = self.env["hr.expense"].create(
            {
                "name": "Test Mobility Expense",
                "employee_id": self.employee.id,
                "product_id": self.mobility_product.id,
                "total_amount_currency": 100.0,
                "date": date(2024, 3, 15),
                "company_id": self.company.id,
            }
        )

        self.assertTrue(expense.l10n_be_is_mobility_expense)
        self.assertEqual(expense.l10n_be_mobility_budget_remaining_month, 100.0)
        self.assertEqual(expense.l10n_be_mobility_budget_remaining_year, 1200.0)

    def test_compute_mobility_budget_with_approved_expenses(self):
        self._create_expense(
            self.mobility_product, 50.0, date(2024, 3, 5), state="approved"
        )
        self._create_expense(
            self.mobility_product, 30.0, date(2024, 3, 10), state="approved"
        )

        expense = self.env["hr.expense"].create(
            {
                "name": "Test Mobility Expense",
                "employee_id": self.employee.id,
                "product_id": self.mobility_product.id,
                "total_amount_currency": 20.0,
                "date": date(2024, 3, 15),
                "company_id": self.company.id,
            }
        )

        self.assertEqual(expense.l10n_be_mobility_budget_remaining_month, 20.0)
        self.assertEqual(expense.l10n_be_mobility_budget_remaining_year, 1120.0)

    def test_compute_mobility_budget_different_months(self):
        self._create_expense(
            self.mobility_product, 100.0, date(2024, 2, 15), state="approved"
        )
        self._create_expense(
            self.mobility_product, 50.0, date(2024, 3, 10), state="approved"
        )

        expense = self.env["hr.expense"].create(
            {
                "name": "Test Mobility Expense",
                "employee_id": self.employee.id,
                "product_id": self.mobility_product.id,
                "total_amount_currency": 20.0,
                "date": date(2024, 3, 20),
                "company_id": self.company.id,
            }
        )

        self.assertEqual(expense.l10n_be_mobility_budget_remaining_month, 50.0)
        self.assertEqual(expense.l10n_be_mobility_budget_remaining_year, 1050.0)

    def test_compute_mobility_budget_non_mobility_product(self):
        self._create_expense(self.mobility_product, 100.0, date(2024, 3, 10), state="approved")

        expense = self.env["hr.expense"].create(
            {
                "name": "Test Non-Mobility Expense",
                "employee_id": self.employee.id,
                "product_id": self.other_product.id,
                "total_amount_currency": 50.0,
                "date": date(2024, 3, 15),
                "company_id": self.company.id,
            }
        )

        self.assertFalse(expense.l10n_be_is_mobility_expense)
        self.assertEqual(expense.l10n_be_mobility_budget_remaining_month, 0.0)
        self.assertEqual(expense.l10n_be_mobility_budget_remaining_year, 0.0)

    def test_compute_mobility_budget_draft_expenses_not_counted(self):
        self._create_expense(self.mobility_product, 100.0, date(2024, 3, 10), state="draft")
        self._create_expense(self.mobility_product, 50.0, date(2024, 3, 11), state="submitted")

        expense = self.env["hr.expense"].create(
            {
                "name": "Test Mobility Expense",
                "employee_id": self.employee.id,
                "product_id": self.mobility_product.id,
                "total_amount_currency": 20.0,
                "date": date(2024, 3, 15),
                "company_id": self.company.id,
            }
        )

        self.assertEqual(expense.l10n_be_mobility_budget_remaining_month, 50.0)
        self.assertEqual(expense.l10n_be_mobility_budget_remaining_year, 1150.0)

    def test_compute_mobility_budget_yearly_period(self):
        self._create_expense(self.mobility_product, 200.0, date(2024, 1, 15), state="approved")
        self._create_expense(self.mobility_product, 150.0, date(2024, 6, 15), state="approved")

        expense = self.env["hr.expense"].create(
            {
                "name": "Test Mobility Expense",
                "employee_id": self.employee.id,
                "product_id": self.mobility_product.id,
                "total_amount_currency": 50.0,
                "date": date(2024, 9, 15),
                "company_id": self.company.id,
            }
        )

        self.assertEqual(expense.l10n_be_mobility_budget_remaining_year, 850.0)

    def test_compute_mobility_budget_no_mobility_budget_on_version(self):
        self.version.l10n_be_mobility_budget = False

        expense = self.env["hr.expense"].create(
            {
                "name": "Test Mobility Expense",
                "employee_id": self.employee.id,
                "product_id": self.mobility_product.id,
                "total_amount_currency": 100.0,
                "date": date(2024, 3, 15),
                "company_id": self.company.id,
            }
        )

        self.assertTrue(expense.l10n_be_is_mobility_expense)
        self.assertEqual(expense.l10n_be_mobility_budget_remaining_month, 0.0)
        self.assertEqual(expense.l10n_be_mobility_budget_remaining_year, 0.0)

    def test_compute_mobility_budget_multiple_employees(self):
        employee2 = self.env["hr.employee"].create(
            {
                "name": "Test Employee 2",
                "company_id": self.company.id,
                "resource_calendar_id": self.resource_calendar.id,
                "structure_type_id": self.env.ref(
                    "hr.structure_type_employee_cp200"
                ).id,
                "date_version": date(2024, 1, 1),
                "contract_date_start": date(2024, 1, 1),
                "wage": 3000.0,
            }
        )
        employee2.current_version_id.write(
            {
                "l10n_be_mobility_budget": True,
                "l10n_be_mobility_budget_amount": 2400.0,
            }
        )

        self._create_expense(self.mobility_product, 100.0, date(2024, 3, 10), state="approved")
        expense2 = self.env["hr.expense"].create(
            {
                "name": "Test Mobility Expense 2",
                "employee_id": employee2.id,
                "product_id": self.mobility_product.id,
                "total_amount_currency": 50.0,
                "date": date(2024, 3, 15),
                "company_id": self.company.id,
            }
        )

        self.assertEqual(expense2.l10n_be_mobility_budget_remaining_month, 200.0)
        self.assertEqual(expense2.l10n_be_mobility_budget_remaining_year, 2400.0)

    def test_compute_mobility_budget_negative_remaining(self):
        self._create_expense(self.mobility_product, 150.0, date(2024, 3, 10), state="approved")

        expense = self.env["hr.expense"].create(
            {
                "name": "Test Mobility Expense",
                "employee_id": self.employee.id,
                "product_id": self.mobility_product.id,
                "total_amount_currency": 20.0,
                "date": date(2024, 3, 15),
                "company_id": self.company.id,
            }
        )

        self.assertEqual(expense.l10n_be_mobility_budget_remaining_month, -50.0)

    def test_payment_at_the_end_of_first_year(self):
        self._create_expense(
            self.mobility_product, 200.0, date(2024, 6, 15), state="approved"
        )

        payslip_dec_2024 = self._create_payslip(date(2024, 12, 1), date(2024, 12, 31))
        mobility_payment = self._get_mobility_payment_amount(payslip_dec_2024)
        self.assertEqual(mobility_payment, 1000.0)

        # The previous logic paid the mobility payment in January (the anniversary month). Check that it's now 0
        payslip_jan_2025 = self._create_payslip(date(2025, 1, 1), date(2025, 1, 31))
        mobility_payment = self._get_mobility_payment_amount(payslip_jan_2025)
        self.assertEqual(mobility_payment, 0.0)

    def test_no_payment_during_the_year(self):
        self._create_expense(
            self.mobility_product, 200.0, date(2024, 6, 15), state="approved"
        )

        payslip_feb_2025 = self._create_payslip(date(2025, 2, 1), date(2025, 2, 28))

        mobility_payment = self._get_mobility_payment_amount(payslip_feb_2025)
        self.assertEqual(mobility_payment, 0.0)

    def test_payment_after_second_year(self):
        self._create_expense(
            self.mobility_product, 200.0, date(2024, 6, 15), state="approved"
        )
        self._create_expense(
            self.mobility_product, 300.0, date(2025, 6, 15), state="approved"
        )

        payslip_dec_2025 = self._create_payslip(date(2025, 12, 1), date(2025, 12, 31))

        mobility_payment = self._get_mobility_payment_amount(payslip_dec_2025)
        self.assertEqual(mobility_payment, 900.0)

    def test_no_payment_when_budget_exceeded(self):
        for i in range(13):
            self._create_expense(
                self.mobility_product,
                100.0,
                date(2024, 1 + i, 15) if i < 12 else date(2025, 1, 15),
                state="approved",
            )

        payslip_dec_2024 = self._create_payslip(date(2024, 12, 1), date(2024, 12, 31))

        mobility_payment = self._get_mobility_payment_amount(payslip_dec_2024)
        self.assertEqual(mobility_payment, 0.0)

    def test_payment_partial_budget_used(self):
        self._create_expense(
            self.mobility_product, 800.0, date(2024, 3, 15), state="approved"
        )

        payslip_dec_2024 = self._create_payslip(date(2024, 12, 1), date(2024, 12, 31))

        mobility_payment = self._get_mobility_payment_amount(payslip_dec_2024)
        self.assertEqual(mobility_payment, 400.0)

    def test_payment_with_different_period_month(self):
        self.employee.write({
            "date_version": date(2024, 6, 1),
            "contract_date_start": date(2024, 6, 1),
        })

        self._create_expense(
            self.mobility_product, 300.0, date(2024, 9, 15), state="approved"
        )

        payslip_jun_2024 = self._create_payslip(date(2024, 6, 1), date(2024, 6, 30))
        mobility_payment = self._get_mobility_payment_amount(payslip_jun_2024)
        self.assertEqual(mobility_payment, 0.0)

        payslip_dec_2024 = self._create_payslip(date(2024, 12, 1), date(2024, 12, 31))
        mobility_payment = self._get_mobility_payment_amount(payslip_dec_2024)
        self.assertAlmostEqual(mobility_payment, 401.64, places=2)

        payslip_jun_2025 = self._create_payslip(date(2025, 6, 1), date(2025, 6, 30))
        mobility_payment = self._get_mobility_payment_amount(payslip_jun_2025)
        self.assertEqual(mobility_payment, 0.0)

        payslip_dec_2025 = self._create_payslip(date(2025, 12, 1), date(2025, 12, 31))
        mobility_payment = self._get_mobility_payment_amount(payslip_dec_2025)
        self.assertEqual(mobility_payment, 1200.0)

    def test_no_payment_without_mobility_budget_enabled(self):
        self.version.l10n_be_mobility_budget = False

        self._create_expense(
            self.mobility_product, 200.0, date(2024, 6, 15), state="approved"
        )

        payslip_dec_2024 = self._create_payslip(date(2024, 12, 1), date(2024, 12, 31))

        mobility_payment = self._get_mobility_payment_amount(payslip_dec_2024)
        self.assertEqual(mobility_payment, 0.0)

    def test_no_payment_without_mobility_budget(self):
        self.version.l10n_be_mobility_budget = False

        self._create_expense(
            self.mobility_product, 200.0, date(2024, 6, 15), state="approved"
        )

        payslip_dec_2024 = self._create_payslip(date(2024, 12, 1), date(2024, 12, 31))

        mobility_payment = self._get_mobility_payment_amount(payslip_dec_2024)
        self.assertEqual(mobility_payment, 0.0)

    def test_expense_in_wrong_year_not_counted(self):
        self._create_expense(
            self.mobility_product, 200.0, date(2025, 6, 15), state="approved"
        )

        payslip_dec_2024 = self._create_payslip(date(2024, 12, 1), date(2024, 12, 31))

        mobility_payment = self._get_mobility_payment_amount(payslip_dec_2024)
        self.assertEqual(mobility_payment, 1200.0)

    def test_draft_expenses_not_counted(self):
        self._create_expense(
            self.mobility_product, 500.0, date(2024, 6, 15), state="draft"
        )

        payslip_dec_2024 = self._create_payslip(date(2024, 12, 1), date(2024, 12, 31))

        mobility_payment = self._get_mobility_payment_amount(payslip_dec_2024)
        self.assertEqual(mobility_payment, 1200.0)

    def test_multiple_employees_independent_balances(self):
        employee2 = self.env["hr.employee"].create(
            {
                "name": "Test Employee 2",
                "company_id": self.company.id,
                "resource_calendar_id": self.resource_calendar.id,
                "structure_type_id": self.env.ref(
                    "hr.structure_type_employee_cp200"
                ).id,
                "date_version": date(2024, 1, 1),
                "contract_date_start": date(2024, 1, 1),
                "wage": 3000.0,
            }
        )
        version2 = employee2.current_version_id
        version2.write(
            {
                "l10n_be_mobility_budget": True,
                "l10n_be_mobility_budget_amount": 2400.0,
            }
        )

        self._create_expense(
            self.mobility_product, 400.0, date(2024, 6, 15), state="approved"
        )

        expense2 = self.env["hr.expense"].create(
            {
                "name": "Test Expense 2",
                "employee_id": employee2.id,
                "product_id": self.mobility_product.id,
                "total_amount_currency": 100.0,
                "date": date(2024, 6, 15),
                "company_id": self.company.id,
            }
        )
        expense2.action_submit()
        expense2.action_approve()

        payslip1 = self._create_payslip(date(2024, 12, 1), date(2024, 12, 31))
        payslip1.employee_id = self.employee
        mobility_payment1 = self._get_mobility_payment_amount(payslip1)
        self.assertEqual(mobility_payment1, 800.0)

        payslip2 = self.env["hr.payslip"].create(
            {
                "name": "Payslip Jan 2025 - Employee 2",
                "version_id": version2.id,
                "date_from": date(2024, 12, 1),
                "date_to": date(2024, 12, 31),
                "employee_id": employee2.id,
                "struct_id": self.structure_monthly.id,
                "company_id": self.company.id,
            }
        )
        payslip2.compute_sheet()
        mobility_payment2 = self._get_mobility_payment_amount(payslip2)
        self.assertEqual(mobility_payment2, 2300.0)

    def test_mobility_payment_end_of_collaboration_without_notice_respect(self):
        departure_notice = self.env['hr.employee.departure'].create({
            'employee_id': self.employee.id,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'dismissal_date': date(2025, 2, 1),
            'l10n_be_notice_respect': 'without',
        })

        payslips_feb_2025 = self._create_payslip(date(2025, 2, 1), date(2025, 2, 28))
        mobility_payment = self._get_mobility_payment_amount(payslips_feb_2025)
        #  1200.0 / 365 days * 32 days = 105.20547945205479
        self.assertAlmostEqual(mobility_payment, 105.21, places=2)

        departure_notice._compute_payslip_history()
        termination_fees_payslip = departure_notice._generate_termination_payslip()
        termination_fee_mobility_payment_line = termination_fees_payslip.line_ids.filtered(lambda l: l.code == "MOBILITY_PAYMENT_TERM")

        # 100.0 * 8 weeks * 3 / 13 = 184.62
        self.assertEqual(termination_fee_mobility_payment_line.total, 184.62)
        self.assertEqual(termination_fee_mobility_payment_line.quantity, 1.85)
        self.assertEqual(termination_fee_mobility_payment_line.amount, 100.00)

    def test_mobility_payment_end_of_collaboration_partial_notice_respect(self):
        departure_notice = self.env['hr.employee.departure'].create({
            'employee_id': self.employee.id,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'dismissal_date': date(2025, 2, 1),
            'l10n_be_notice_respect': 'partial',
            'departure_date': date(2025, 3, 1),
        })

        payslips_mar_2025 = self._create_payslip(date(2025, 3, 1), date(2025, 3, 31))
        mobility_payment = self._get_mobility_payment_amount(payslips_mar_2025)
        #  1200.0 / 365 days * 60 days = 197.26
        self.assertEqual(round(mobility_payment, 2), 197.26)

        departure_notice._compute_payslip_history()
        termination_fees_payslip = departure_notice._generate_termination_payslip()
        termination_fee_mobility_payment_line = termination_fees_payslip.line_ids.filtered(lambda l: l.code == "MOBILITY_PAYMENT_TERM")

        # 100.0 * 5 weeks * 3 / 13 = 184.62
        self.assertEqual(termination_fee_mobility_payment_line.total, 115.38)
        self.assertEqual(termination_fee_mobility_payment_line.quantity, 1.15)
        self.assertEqual(termination_fee_mobility_payment_line.amount, 100.00)

    def test_mobility_payment_end_of_collaboration_with_notice_respect(self):
        self.env['hr.employee.departure'].create({
            'employee_id': self.employee.id,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'dismissal_date': date(2025, 2, 1),
            'l10n_be_notice_respect': 'with',
        })

        payslips_apr_2025 = self._create_payslip(date(2025, 4, 1), date(2025, 4, 30))
        mobility_payment = self._get_mobility_payment_amount(payslips_apr_2025)
        #  1200.0 / 365 days * 96 days = 315.6164383561644
        self.assertAlmostEqual(mobility_payment, 315.62, places=2)

    def test_mobility_budget_full_flow(self):
        self.employee.write({
            'wage': 3000.0,
            'date_version': date(2025, 4, 1),
            'l10n_be_mobility_budget': True,
            'l10n_be_mobility_budget_amount': 6000.0,
            })

        prorated_mb_amount = self.employee._get_l10n_be_mobility_budget_amount_prorated(
            reference_date=date(2025, 12, 31), year=2025
        ).get(self.employee.id, 0.0)
        # Expected amount: 4520.55 = 6000 * 275 / 365
        self.assertAlmostEqual(prorated_mb_amount, 4520.55, places=2)

        # First expense, check monthly & yearly remaining
        expense_1 = self._create_expense(self.mobility_product, 200.0, date(2025, 5, 15), state="posted")
        self.assertAlmostEqual(expense_1.l10n_be_mobility_budget_remaining_month, 300.0, 2)
        self.assertAlmostEqual(expense_1.l10n_be_mobility_budget_remaining_year, 4320.55, 2)

        # Payslip: check MOBILITY_PAID_MONTH / set MOBILITY_TO_PAY inputs
        payslip = self._create_payslip(date(2025, 5, 1), date(2025, 5, 31))
        mobility_paid_input = payslip.line_ids.filtered(lambda l: l.code == "MOBILITY_PAID_MONTH").total
        self.assertAlmostEqual(mobility_paid_input, 200.0, places=2)

        payslip._set_input_value("MOBILITY_TO_PAY", 50.0)
        payslip.compute_sheet()
        payslip.action_payslip_done()

        # Second expense, after validation of the payslip (to check if "MOBILITY_TO_PAY" from payslip will affect the remaining amounts)
        expense_2 = self._create_expense(self.mobility_product, 100.0, date(2025, 5, 28), state="posted")
        self.assertAlmostEqual(expense_2.l10n_be_mobility_budget_remaining_month, 150.0, 2)
        self.assertAlmostEqual(expense_2.l10n_be_mobility_budget_remaining_year, 4170.55, 2)

        # Third expense, next month
        expense_3 = self._create_expense(self.mobility_product, 150.0, date(2025, 6, 10), state="posted")
        self.assertAlmostEqual(expense_3.l10n_be_mobility_budget_remaining_month, 350.0, 2)
        self.assertAlmostEqual(expense_3.l10n_be_mobility_budget_remaining_year, 4020.55, 2)
