from datetime import date

from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestHiddenSimulationOffer(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env['hr.employee'].create({
            'name': 'Simulation Test Employee',
            'contract_date_start': date(2026, 1, 1),
        })

    def test_hr_contract_salary_hidden_simulation_offer_tour(self):
        self.start_tour("/odoo", 'hr_contract_salary_hidden_simulation_offer_tour', login='admin', timeout=350)
