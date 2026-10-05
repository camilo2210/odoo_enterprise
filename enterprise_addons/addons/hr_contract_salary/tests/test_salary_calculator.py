# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import HttpCase, tagged, Form
from datetime import date


@tagged('-at_install', 'post_install', 'salary')
class TestSalarySimulation(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.calendar_38h = cls.env['resource.calendar'].create({
            'name': 'Standard 38 hours/week',
            'company_id': False,
            'hours_per_day': 7.6,
            'attendance_ids': [(5, 0, 0),
                               (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                               (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 16.6}),
                               (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                               (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 16.6}),
                               (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
                               (0, 0, {'dayofweek': '2', 'hour_from': 13, 'hour_to': 16.6}),
                               (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                               (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 16.6}),
                               (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
                               (0, 0, {'dayofweek': '4', 'hour_from': 13, 'hour_to': 16.6})
                               ],
        })
        cls.struct_type = cls.env['hr.payroll.structure.type'].create({'name': 'Regular'})
        cls.structure = cls.env['hr.payroll.structure'].create({
            'name': 'Regular structure',
            'type_id': cls.struct_type.id,
        })
        cls.struct_type.default_struct_id = cls.structure
        cls.employee = cls.env["hr.employee"].create(
            {
                "tz": 'Europe/Brussels',
                "name": "Moul Rayeb",
                "work_phone": "999-231-3324",
                "work_email": "ash@example.com",
                "wage_type": "monthly",
                "wage": 8700,
                "resource_calendar_id": cls.calendar_38h.id,
                'structure_type_id': cls.struct_type.id,
                'contract_date_start': date.today()
            },
        )

    def test_salary_calculator_logic(self):
        self.start_tour(
            "/odoo/payroll",
            "hr_salary_calculator_tour",
            login="admin",
        )

    def test_employee_salary_configurator_switch_budget_type(self):
        offer = self.env['hr.contract.salary.offer'].create({
            'employee_id': self.employee.id,
            'structure_id': self.structure.id,
            'final_yearly_costs': 54000.0,
            'salary_amount': 54000.0,
            'budget_type': 'yearly_employer',
            'resource_calendar_id': self.calendar_38h.id,
            'is_simulation_offer': True,
        })
        with Form(offer) as offer_form:
            offer_form.budget_type = 'monthly_net'
            self.assertEqual(offer_form.salary_amount, 4275.0)
            offer_form.budget_type = 'yearly_employer'
            self.assertEqual(offer_form.salary_amount, 51300.0)
            offer_form.budget_type = 'monthly_gross'
            self.assertEqual(offer_form.salary_amount, 4275.0)
