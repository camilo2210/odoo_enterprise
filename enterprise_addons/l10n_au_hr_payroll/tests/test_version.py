from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import Form, tagged

from .common import TestPayrollCommon


@tagged("post_install_l10n", "post_install", "-at_install", "l10n_au_hr_payroll")
class TestVersion(TestPayrollCommon):

    def test_version_creation_with_zero_working_hours(self):
        self.env.company.resource_calendar_id.attendance_ids = [Command.clear()]
        with Form(self.env['hr.employee']) as employee_form:
            employee_form.name = "Au Employee"
            employee_form.company_id = self.australian_company
            employee_form.wage = 100
            employee_form.l10n_au_yearly_wage = 1200
        employee = employee_form.save()

        self.assertTrue(employee)
        self.assertTrue(employee.version_ids)
        self.assertEqual(employee.version_ids[0].hourly_wage, 0.0)

    def test_schedule_pay_required_for_au_employee(self):
        '''Test that creating an Australian employee with a wage but no schedule pay raises a UserError.'''
        employee_form = Form(self.env['hr.employee'])

        employee_form.name = "Test Au Employee"
        employee_form.company_id = self.australian_company
        employee_form.wage = 100
        with self.assertRaises(UserError):
            employee_form.schedule_pay = False
            employee_form.save()

    def test_remove_tax_treatment_category_from_employee(self):
        """Test that removing the employee's tax treatment category updates the tax treatment code."""
        employee_form = Form(self.employee_id)
        employee_form.l10n_au_tax_treatment_category = False

        self.assertFalse(employee_form.l10n_au_tax_treatment_code)
