# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.fields import Domain
from odoo.tests import tagged
from odoo.tests.common import HttpCase


@tagged("-at_install", "post_install", "salary")
class TestEmployeeOffer(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        employee_start_date = fields.Datetime.today() + relativedelta(
            years=-3,
            month=1,
            day=1,
        )
        cls.employee = cls.env["hr.employee"].create(
            {
                "name": "Ash Ketchum",
                "work_phone": "999-231-3324",
                "work_email": "ash@example.com",
                "wage_type": "monthly",
                "wage": 8700,
                "date_version": employee_start_date,
                "contract_date_start": employee_start_date,
                "employee_type_id": cls.env.ref("hr.contract_type_employee").id,
            },
        )
        job_trainer = cls.env["hr.job"].create(
            {
                "name": "Pokémon Trainer",
                "employee_type_id": cls.env.ref(
                    "hr.contract_type_employee",
                ).id,
                "description": """
We are looking for an experienced Pokémon Trainer to join our elite team.
Someone who can snap out of battle strategy, perform in-depth analysis of
Pokémon stats and moves, and meet with clients (Gym Leaders) to explain how
their Pokémon can meet any challenge.
            """,
            },
        )
        cls.contract_template_trainer = cls.env["hr.version"].create(
            {
                "name": job_trainer.name,
                "structure_type_id": cls.env.ref(
                    "hr.structure_type_employee",
                ).id,
                "job_id": job_trainer.id,
                "wage": 2650,
            },
        )
        job_trainer.contract_template_id = cls.contract_template_trainer

    def test_change_contract_template_with_work_entries(self):
        """
        Check if generating work entries for the next month on an employee
        prevents us from changing contract templates on new offers for this
        employee.
        """
        # The tour will also save the offer after the change
        self.start_tour(
            f"/odoo/employees/{self.employee.id}",
            "change_contract_template_on_offer_tour",
            login="admin",
        )

        employee_id_domain = Domain('employee_id', '=', self.employee.id)
        salary_offers_of_employee = self.env['hr.contract.salary.offer'].search(
            employee_id_domain,
        )

        self.assertEqual(
            1,
            len(salary_offers_of_employee),
            f"One offer for employee {self.employee.name} should have been created",
        )

        new_contract_template = salary_offers_of_employee[
            0
        ].contract_template_id
        wanted_contract_template = self.contract_template_trainer
        self.assertEqual(
            wanted_contract_template.id,
            new_contract_template.id,
            f'''
{self.employee.name}'s offer should have a contract template set to: "{wanted_contract_template.name}"
But is instead set to: "{new_contract_template.name or new_contract_template.display_name}"
            ''',
        )

    def test_employee_offer_salary_amount(self):
        # Check that salary_amount is shown on the offer form after clicking on the Offers smart button.
        # Check that the salary amount is shown on the Simulation pop up after clicking on the Simulate button on the employee form.
        self.start_tour(
            f"/odoo/employees/{self.employee.id}",
            "hr_contract_salary_payroll_employee_offers_button_tour",
            login="admin",
        )
