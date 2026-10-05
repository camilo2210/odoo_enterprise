# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.addons.hr_contract_salary.utils.hr_version import HR_VERSION_CTX_KEY
from odoo.tests import TransactionCase, tagged, Form
from datetime import date


@tagged('-at_install', 'post_install', 'salary')
class TestHrContractSalaryOffer(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.offer_calendar = cls.env['resource.calendar'].create({
            'name': 'Offer Calendar',
            'hours_per_week': 40,
        })
        cls.version_calendar = cls.env['resource.calendar'].create({
            'name': 'Version Calendar',
            'hours_per_day': 7.6,
            'hours_per_week': 38,  # if the version uses this calendar, version.work_time_rate will be 0.95 cause relative to company weekly working hours
            'full_time_required_hours': 38,
        })
        cls.part_time_calendar = cls.env['resource.calendar'].create({
            'name': 'Part Time Calendar',
            'hours_per_week': 20,
        })

        cls.struct_type = cls.env['hr.payroll.structure.type'].create({'name': 'Regular'})
        cls.structure = cls.env['hr.payroll.structure'].create({
            'name': 'Regular structure',
            'type_id': cls.struct_type.id,
        })
        cls.struct_type.default_struct_id = cls.structure

        cls.employee = cls.env['hr.employee'].create({
            'name': 'Tom Ato',
            'wage': 2000,
            'structure_type_id': cls.struct_type.id,
            'contract_date_start': date.today()
        })
        cls.version = cls.employee.version_ids[0]
        # Use this context override before calling methods marked with `@requires_hr_version_context`
        # Business code might depend on the context being set correctly, so we don't patch `@requires_hr_version_context`
        cls.version_ctx = {
            'salary_simulation': True,
            'tracking_disable': True,
            HR_VERSION_CTX_KEY: True,
        }

    def test_version_calendar_priority(self):
        offer = self.env['hr.contract.salary.offer'].create({
            'employee_id': self.employee.id,
            'structure_id': self.structure.id,
            'salary_amount': 2000,
            'budget_type': 'monthly_gross',
            'resource_calendar_id': self.offer_calendar.id,
        }).with_context(**self.version_ctx)

        # case 1: version has its own (different) calendar -> offer's own calendar still takes priority
        self.version.resource_calendar_id = self.part_time_calendar
        offer._compute_salary()
        version = offer._get_version()
        self.assertEqual(version.resource_calendar_id, self.offer_calendar)
        self.assertAlmostEqual(offer.gross_wage, 2000.0, places=2)  # check gross salary computed in Salary Simulation Preview

        # case 2: version calendar set -> it's prefilled to offer.
        self.version.resource_calendar_id = self.version_calendar
        offer = self.env['hr.contract.salary.offer'].create({
            'employee_id': self.employee.id,
            'structure_id': self.structure.id,
            'salary_amount': 2000,
            'budget_type': 'monthly_gross',
        }).with_context(**self.version_ctx)
        offer._compute_salary()
        version = offer._get_version()
        self.assertAlmostEqual(offer.gross_wage, 2000.0, places=2)
        self.assertEqual(version.resource_calendar_id, self.version_calendar)

    def test_gross_guess_based_on_net_calculation(self):
        offer = self.env['hr.contract.salary.offer'].create({
            'employee_id': self.employee.id,
            'structure_id': self.structure.id,
            'salary_amount': 2000,
            'budget_type': 'monthly_gross',
            'resource_calendar_id': self.version_calendar.id,
        })

        with Form(offer) as offer_form:
            offer_form.budget_type = 'monthly_net'
            offer_form.salary_amount = 1900
            self.assertAlmostEqual(offer_form.net_wage, 1900.0, places=2)
            self.assertAlmostEqual(offer_form.gross_wage, 1900.0, places=2)
            self.assertEqual(offer_form.salary_amount, 1900.0, "Value should not change")
            self.assertEqual(offer_form.budget_type, 'monthly_net', "Value should not change")

    def test_simulation_calendar_priority(self):
        offer = self.env['hr.contract.salary.offer'].create({
            'employee_id': self.employee.id,
            'structure_id': self.structure.id,
            'salary_amount': 2000,
            'budget_type': 'monthly_gross',
            'resource_calendar_id': self.part_time_calendar.id,
            'is_simulation_offer': True,
        })

        # case 1: Check that in case of simulation offer, priority is given to offer calendar over version calendar
        # testing with a part time calendar of 20 hrs/week, we expect gross wage to be half the offer monthly wage
        self.version.resource_calendar_id = self.version_calendar
        offer._compute_salary()
        self.assertAlmostEqual(offer.gross_wage, 1000.0, places=2)  # check gross salary computed in Salary Simulation Preview

    def test_gross_net_simulation_salary_calculation(self):
        offer_form = Form(
            self.env['hr.contract.salary.offer'],
            view="hr_contract_salary.hr_contract_salary_offer_view_form_calculator"
        )
        offer_form.salary_amount = self.employee.wage
        offer_form.budget_type = "monthly_gross"
        offer_form.employee_id = self.employee
        offer_form.structure_id = self.structure
        offer = offer_form.save()

        self.assertAlmostEqual(offer.salary_amount, 2000.0, places=2)
        self.assertAlmostEqual(offer.gross_wage, 2000.0, places=2)
        self.assertAlmostEqual(offer.yearly_employer_cost, 24000.0, places=2)

    def test_preserve_salary_amount_on_contract_date_change(self):
        self.employee.version_id.final_yearly_costs = 50000
        with Form(self.env['hr.contract.salary.offer'].with_context(default_employee_id=self.employee.id)) as offer_form:
            self.assertEqual(offer_form.contract_template_id, self.employee.version_id)
            self.assertEqual(offer_form.salary_amount, 50000)
            offer_form.salary_amount = 75000
            offer_form.contract_start_date = fields.Date.add(fields.Date.today(), days=15)
        offer = offer_form.save()
        self.assertEqual(offer.salary_amount, 75000)

    def test_simulation_offer_does_not_recompute_existing_draft_payslip(self):
        """
        Computing a salary simulation for an employee that already has a
        draft payslip in the simulated period should not recompute that payslip.
        """
        payslip = self.env['hr.payslip'].create({
            'name': 'Draft payslip',
            'employee_id': self.employee.id,
            'date_from': date.today().replace(day=1),
            'date_to': date.today(),
        })
        line_ids_before = payslip.line_ids.ids
        worked_days_before = payslip.worked_days_line_ids.ids

        offer = self.env['hr.contract.salary.offer'].create({
            'employee_id': self.employee.id,
            'structure_id': self.structure.id,
            'salary_amount': 2000,
            'budget_type': 'monthly_gross',
            'resource_calendar_id': self.offer_calendar.id,
            'is_simulation_offer': True,
        })
        offer._compute_salary()

        self.assertEqual(payslip.line_ids.ids, line_ids_before,
            "Existing draft payslip should not be recomputed by a salary simulation")
        self.assertEqual(payslip.worked_days_line_ids.ids, worked_days_before,
            "Existing draft payslip should not be recomputed by a salary simulation")

    def test_future_contract_offer_creation(self):
        """
        Ensure that creating a salary offer for a contract starting in the future
        does not raise a validation error when the employee has a running contract
        ending today.
        """
        today = fields.Date.today()
        start_of_year = today.replace(month=1, day=1)
        future_date = fields.Date.add(today, days=1)

        self.version.write({
            'contract_date_start': start_of_year,
            'contract_date_end': today,
            'date_start': start_of_year,
            'date_version': start_of_year,
        })

        future_version = self.env['hr.version'].create({
            'employee_id': self.employee.id,
            'contract_date_start': future_date,
            'date_start': future_date,
            'date_version': future_date,
            'wage': 2500,
            'structure_type_id': self.struct_type.id,
        })

        action = future_version.action_generate_offer()
        offer = self.env['hr.contract.salary.offer'].browse(action['res_id'])

        offer.with_context(**self.version_ctx)._compute_salary()

        self.assertEqual(self.version.contract_date_end, today)
        self.assertTrue(offer.exists())
