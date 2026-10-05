from datetime import date
from odoo.tests import tagged, Form
from .common import TestPayrollCommon
from freezegun import freeze_time


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestHrPayrollEmployeeDepartureNotice(TestPayrollCommon):

    @classmethod
    def setUpClass(self):
        super().setUpClass()
        self.leaving_type_fired = self.env['hr.departure.reason'].create({
            'name': 'Fired',
            'l10n_be_reason_code': 342,
        })
        self.leaving_type_resigned = self.env['hr.departure.reason'].create({
            'name': 'Resigned',
            'l10n_be_reason_code': 343,
        })

        self.eco_unemployment_calendar_full = self.resource_calendar.copy({
            'name': 'Calendar Economic Unemployment 5 days',
            'full_time_required_hours': 38,
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12, 'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_economic_unemployment').id}),
                (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 16.6, 'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_economic_unemployment').id}),
                (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12, 'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_economic_unemployment').id}),
                (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 16.6, 'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_economic_unemployment').id}),
                (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12, 'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_economic_unemployment').id}),
                (0, 0, {'dayofweek': '2', 'hour_from': 13, 'hour_to': 16.6, 'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_economic_unemployment').id}),
                (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12, 'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_economic_unemployment').id}),
                (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 16.6, 'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_economic_unemployment').id}),
                (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 12, 'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_economic_unemployment').id}),
                (0, 0, {'dayofweek': '4', 'hour_from': 13, 'hour_to': 16.6, 'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_economic_unemployment').id})
            ]
        })

        self.employee_eco_unemployment = self.create_employee({
            'name': 'Employee Economic Unemployment',
            'date_version': date(2025, 1, 1),
            'contract_date_start': date(2025, 1, 1),
            'contract_date_end': date(2025, 8, 30),
            'resource_calendar_id': self.eco_unemployment_calendar_full.id,
        })

    @freeze_time("2025-07-21")
    def test_notice_period_calculation_economic_unemployment_resigned(self):
        departure_eco = self.env['hr.employee.departure'].create({
            'employee_id': self.employee_eco_unemployment.id,
            'dismissal_date': '2025-07-21',
            'departure_reason_id': self.leaving_type_resigned.id,
            'departure_description': 'Resigned',
        })

        self.assertEqual(departure_eco.l10n_be_notice_duration_week_after_2014, 0)

    @freeze_time("2025-07-21")
    def test_notice_period_calculation_economic_unemployment_fired(self):
        departure_eco = self.env['hr.employee.departure'].create({
            'employee_id': self.employee_eco_unemployment.id,
            'dismissal_date': '2025-07-21',
            'departure_reason_id': self.leaving_type_fired.id,
            'departure_description': 'Fired',
        })

        self.assertTrue(departure_eco.l10n_be_notice_period_start > date(2025, 8, 30), "Notice period should start after last day of economic unemployment")
        self.assertEqual(departure_eco.l10n_be_notice_duration_week_after_2014, 6)

    def test_reference_salary_termination_fees_rule(self):
        """
        Checks that the rule Reference Salary is well computed when generating a termination payslip.
        """
        brand = self.env['fleet.vehicle.model.brand'].create({'name': 'Audi'})
        model = self.env['fleet.vehicle.model'].create({'name': 'TT RS', 'brand_id': brand.id})
        car = self.env['fleet.vehicle'].create({'model_id': model.id, 'company_id': self.belgian_company.id, 'atn': 2000, 'driver_employee_id': self.employee_a.id})

        self.employee_a.version_id.write({
            'transport_mode_car': True,
            'car_id': car.id})

        departure = self.env['hr.employee.departure'].create({
            'employee_id': self.employee_a.id,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'dismissal_date': '2025-07-20',
            'l10n_be_notice_respect': 'without',
            'departure_description': "Oh no you're fired",
        })
        # self.env.flush_all()
        departure.action_register()
        departure_payslips = departure._generate_termination_payslip()
        departure_payslips = self.env['hr.payslip'].search([('id', 'in', departure_payslips.ids)])
        struct_id = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_termination_fees')
        termination_fees = departure_payslips.filtered(lambda dep: dep.struct_id == struct_id)
        termination_fees.compute_sheet()
        rules = ['YEAREND_BONUS', 'VARIABLE_SALARY', 'RESIDENCE', 'EXPATRIATE', 'BASIC2', 'PAY_VARIABLE_SALARY', 'ATN_CAR_TERM']
        self.assertEqual(sum(termination_fees.line_ids.filtered(lambda l: l.code in rules).mapped('total')),
            termination_fees.line_ids.filtered(lambda l: l.code == 'TERM_REF_SALARY').total)

    def test_withholding_taxes_termination_fees_rule(self):
        """
        Checks that the rule withholding tax is well computed when generating a termination payslip for an employee
        without children.
        Reference salary = (Gross yearly salary + year-end bonus + annual variable salary + residence allowance
        + expatriation allowance + Pay on variable salary + benefit in kind).
        In our case, Reference salary = Gross yearly salary + year-end bonus = 32300 + 2500 = 34800
        Taxable reference salary = Reference Salary - ONSS_TERM_REF (13.07 %) = 34800 - 4548.36 = 30251,64
        Withholding tax on taxable salary (30251,64) has rate of 24,92
        (source: https://www.securex.be/getattachment/eeaf8a4e-0c87-47e9-8af2-1cf41db24148/Annexe-III-AR-CIR-2026.pdf)
        Base of withholding salary is TERM_GROSS - children exoneration = TERM_GROSS - 0 = 7988.06
        24.92% of 7988.06 = 1990.6245
        """
        departure = self.env['hr.employee.departure'].create({
            'employee_id': self.employee_a.id,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'dismissal_date': '2025-07-20',
            'l10n_be_notice_respect': 'without',
            'departure_description': "Oh no you're fired",
        })
        departure.action_register()
        departure_payslips = departure._generate_termination_payslip()
        departure_payslips = self.env['hr.payslip'].search([('id', 'in', departure_payslips.ids)])
        struct_id = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_termination_fees')
        termination_fees = departure_payslips.filtered(lambda dep: dep.struct_id == struct_id)
        termination_fees.compute_sheet()
        taxable_salary = termination_fees.line_ids.filtered(lambda l: l.code == 'TERM_GROSS').total
        withholding_tax = termination_fees.line_ids.filtered(lambda l: l.code == 'TERM_PP').total
        self.assertAlmostEqual(round(- (taxable_salary / 100) * 24.92, 2), withholding_tax)

    @freeze_time("2025-07-21")
    def test_notice_period_calculation_employer_fired_reasons(self):
        employer_reasons = [
            self.env.ref('l10n_be_hr_payroll.departure_fired_notice_employer'),
            self.env.ref('l10n_be_hr_payroll.departure_fired_termination_employer'),
        ]
        for reason in employer_reasons:
            departure = self.env['hr.employee.departure'].create({
                'employee_id': self.employee_test.id,
                'dismissal_date': '2025-07-21',
                'departure_reason_id': reason.id,
            })

            self.assertGreater(
                departure.l10n_be_notice_duration_week_after_2014, 0,
                f"Reason {reason.name} should calculate notice duration as Fired"
            )

    @freeze_time("2025-07-21")
    def test_notice_period_calculation_without_notice_reasons(self):
        zero_notice_reasons = [
            self.env.ref('l10n_be_hr_payroll.departure_resigned_medical_force_majeure'),
            self.env.ref('l10n_be_hr_payroll.departure_contract_end_fixed_term'),
            self.env.ref('l10n_be_hr_payroll.departure_contract_end_specific_work'),
        ]
        for reason in zero_notice_reasons:
            departure = self.env['hr.employee.departure'].create({
                'employee_id': self.employee_test.id,
                'dismissal_date': '2025-07-21',
                'departure_reason_id': reason.id,
            })

            self.assertEqual(
                departure.l10n_be_notice_duration_week_after_2014, 0,
                f"Reason {reason.name} must have 0 weeks notice duration"
            )

    @freeze_time("2025-07-21")
    def test_fixed_term_contract_updated_on_departure_create(self):
        """ Test that ending collaboration with Fixed Term reason automatically sets fixed_term = True
            on the employee version when the notice period is fully worked.
        """
        fixed_term_reason = self.env.ref('l10n_be_hr_payroll.departure_contract_end_fixed_term')

        # Ensure fixed_term is initially False
        version = self.employee_test._get_version(date(2025, 7, 21))
        self.assertFalse(version.fixed_term)

        wizard_form = Form(self.env['hr.employee.departure'].with_context(
            allowed_company_ids=self.belgian_company.ids,
            active_id=self.employee_test.id,
        ))
        wizard_form.dismissal_date = date(2025, 7, 21)
        wizard_form.departure_reason_id = fixed_term_reason
        wizard_form.save()

        # Verify fixed_term is updated to True on the version
        self.assertTrue(version.fixed_term)

    @freeze_time("2025-07-21")
    def test_fixed_term_contract_updated_on_action_register(self):
        """ Test that registering an end of collaboration with a Fixed Term reason ensures the
            employee version is flagged as fixed term.
        """
        fixed_term_reason = self.env.ref('l10n_be_hr_payroll.departure_contract_end_fixed_term')

        departure = self.env['hr.employee.departure'].create({
            'employee_id': self.employee_test.id,
            'dismissal_date': '2025-07-21',
            'departure_reason_id': fixed_term_reason.id,
        })

        version = self.employee_test._get_version(date(2025, 7, 21))
        # Reset value to False to test explicit execution of action_register
        version.sudo().write({'fixed_term': False})

        departure.action_register()

        self.assertTrue(version.fixed_term)
