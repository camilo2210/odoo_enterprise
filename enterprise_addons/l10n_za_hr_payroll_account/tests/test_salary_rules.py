# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests.common import tagged
from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestPayslipValidationZA(TestPayslipValidationCommon):
    _test_user_groups = None

    @classmethod
    @TestPayslipValidationCommon.setup_country('za')
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_common(
            country=cls.env.ref('base.za'),
            structure=cls.env.ref('l10n_za_hr_payroll.hr_payroll_structure_za_employee_salary'),
            structure_type=cls.env.ref('l10n_za_hr_payroll.structure_type_employee_za'),
            version_fields={
                'wage': 25000.0,
            },
            employee_fields={
                'birthday': date(1995, 1, 1),
            },
        )

    # ------------------------------------------------------------
    # Baseline payslip
    # ------------------------------------------------------------

    def test_basic_payslip(self):
        payslip = self._generate_payslip(date(2026, 3, 1), date(2026, 3, 31))
        self._validate_payslip(payslip)

    def test_income_tax_below_threshold(self):
        payslip = self._generate_payslip(date(2026, 3, 1), date(2026, 3, 31))
        payslip.version_id.wage = 8000.0
        payslip.compute_sheet()
        self._validate_payslip(payslip)

    def test_primary_tax_rebate(self):
        payslip = self._generate_payslip(date(2026, 3, 1), date(2026, 3, 31))
        payslip.employee_id.birthday = date(1990, 1, 1)
        payslip.compute_sheet()
        self._validate_payslip(payslip)

    def test_secondary_tax_rebate(self):
        payslip = self._generate_payslip(date(2026, 3, 1), date(2026, 3, 31))
        payslip.employee_id.birthday = date(1960, 1, 1)
        payslip.compute_sheet()
        self._validate_payslip(payslip)

    def test_tertiary_tax_rebate(self):
        payslip = self._generate_payslip(date(2026, 3, 1), date(2026, 3, 31))
        payslip.employee_id.birthday = date(1945, 1, 1)
        payslip.compute_sheet()
        self._validate_payslip(payslip)

    def test_overtime_ordinary(self):
        employee = self.env['hr.employee'].create({
            'name': 'Test Employee',
            'structure_type_id': self.env.ref(
                'l10n_za_hr_payroll.structure_type_employee_za'
            ).id,
            'country_id': self.env.ref('base.za').id,
            'date_version': date(2026, 3, 1),
            'contract_date_start': date(2026, 3, 1),
            'wage': 25000.0,
            'birthday': date(1995, 1, 1),
        })
        overtime_work_entry_type = self.env.ref('hr_work_entry.za_work_entry_type_overtime_work_days')
        overtime_work_entry_type.sudo().write({'requires_allocation': False, 'request_unit': 'hour'})
        if 'overtime_deductible' in overtime_work_entry_type:
            overtime_work_entry_type.overtime_deductible = False
        self.env['hr.leave'].create({
            'name': 'Overtime',
            'employee_id': employee.id,
            'work_entry_type_id': overtime_work_entry_type.id,
            'request_date_from': date(2026, 3, 10),
            'request_date_to': date(2026, 3, 10),
            'request_hour_from': 18,
            'request_hour_to': 23,
        })
        payslip = self._generate_payslip(
            date(2026, 3, 1),
            date(2026, 3, 31),
            employee_id=employee.id,
            version_id=employee.version_id.id,
        )
        payslip.compute_sheet()
        self._validate_payslip(payslip)

    def test_overtime_public_holiday(self):
        employee = self.env['hr.employee'].create({
            'name': 'Test Employee',
            'structure_type_id': self.env.ref(
                'l10n_za_hr_payroll.structure_type_employee_za'
            ).id,
            'country_id': self.env.ref('base.za').id,
            'date_version': date(2026, 3, 1),
            'contract_date_start': date(2026, 3, 1),
            'wage': 25000.0,
            'birthday': date(1995, 1, 1),
        })
        overtime_work_entry_type = self.env.ref(
            'hr_work_entry.za_work_entry_type_overtime_public_holidays'
        )
        overtime_work_entry_type.sudo().write({
            'requires_allocation': False,
            'request_unit': 'hour',
        })
        if 'overtime_deductible' in overtime_work_entry_type:
            overtime_work_entry_type.overtime_deductible = False
        self.env['hr.leave'].create({
            'name': 'Overtime Public Holiday',
            'employee_id': employee.id,
            'work_entry_type_id': overtime_work_entry_type.id,
            'request_date_from': date(2026, 3, 21),
            'request_date_to': date(2026, 3, 21),
            'request_hour_from': 9,
            'request_hour_to': 17,
        })
        payslip = self._generate_payslip(
            date(2026, 3, 1),
            date(2026, 3, 31),
            employee_id=employee.id,
            version_id=employee.version_id.id,
        )
        payslip.compute_sheet()
        self._validate_payslip(payslip)

    def test_medical_tax_credit_member_only(self):
        """Contributing member with no dependants receives taxpayer credit only."""
        payslip = self._generate_payslip(date(2026, 3, 1), date(2026, 3, 31))
        payslip.version_id.write({
            'l10n_za_employee_medical_scheme_contribution': 2200.0,
            'l10n_za_dependant_medical_scheme_contribution': 0.0,
            'l10n_za_employee_dependant_count': 0,
        })
        payslip.compute_sheet()
        self._validate_payslip(payslip)

    def test_medical_tax_credit_one_dependant(self):
        """Member with one dependant receives taxpayer + first dependant credit."""
        payslip = self._generate_payslip(date(2026, 3, 1), date(2026, 3, 31))
        payslip.version_id.write({
            'l10n_za_employee_medical_scheme_contribution': 2200.0,
            'l10n_za_dependant_medical_scheme_contribution': 500.0,
            'l10n_za_employee_dependant_count': 1,
        })
        payslip.compute_sheet()
        self._validate_payslip(payslip)

    def test_medical_tax_credit_two_dependants(self):
        """Member with two dependants receives taxpayer + first + second dependant credit."""
        payslip = self._generate_payslip(date(2026, 3, 1), date(2026, 3, 31))
        payslip.version_id.write({
            'l10n_za_employee_medical_scheme_contribution': 2200.0,
            'l10n_za_dependant_medical_scheme_contribution': 500.0,
            'l10n_za_employee_dependant_count': 2,
        })
        payslip.compute_sheet()
        self._validate_payslip(payslip)

    def test_medical_tax_credit_more_than_two_dependants(self):
        payslip = self._generate_payslip(
            date(2026, 3, 1),
            date(2026, 3, 31),
        )
        payslip.version_id.write({
            'l10n_za_employee_medical_scheme_contribution': 2200.0,
            'l10n_za_dependant_medical_scheme_contribution': 500.0,
            'l10n_za_employee_dependant_count': 5,
        })
        payslip.compute_sheet()
        self._validate_payslip(payslip)

    def test_sdl_eligible(self):
        """Company is eligible for SDL (the default), AMOUNT_SDL is
        charged on gross at the rule-parameter rate."""
        payslip = self._generate_payslip(date(2026, 3, 1), date(2026, 3, 31))
        self._validate_payslip(payslip)

    def test_sdl_not_eligible(self):
        """Company explicitly flagged not eligible for SDL, AMOUNT_SDL is
        0 regardless of gross."""
        payslip = self._generate_payslip(date(2026, 3, 1), date(2026, 3, 31))
        payslip.company_id.l10n_za_eligible_for_sdl = False
        payslip.compute_sheet()
        self._validate_payslip(payslip)
