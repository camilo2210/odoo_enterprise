# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestEmployerCostsWithSaFields(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company_sa = self.env['res.company'].create({
            'name': 'SA Co',
            'country_id': self.env.ref('base.sa').id,
        })
        self.employee_sa_with_visa = self.env['hr.employee'].create({
            'name': 'SA Employee with Visa',
            'company_id': self.company_sa.id,
            'country_code': 'BE',
        })

    def test_employer_costs_with_sa_fields(self):
        """
        Test that employer costs include SA-specific fields for visa holders.
        Basic: 1k, Housing: 1k, Other: 1k, Iqama: 6k, Medical: 5k
        Monthly cost should be 3.91K (Yearly: 47k)
        """
        Version = self.env['hr.version'].with_company(self.company_sa)

        template = Version.create({
            'name': 'Visa Holder Template',
            'wage': 1000.0,  # Basic wage
            'l10n_sa_housing_allowance': 1000.0,
            'l10n_sa_other_allowances': 1000.0,
            'l10n_sa_iqama_annual_amount': 6000.0,
            'l10n_sa_medical_insurance_annual_amount': 5000.0,
        })

        contract = self.employee_sa_with_visa.version_id

        self.employee_sa_with_visa.contract_template_id = template
        self.employee_sa_with_visa._onchange_contract_template_id()

        contract._compute_final_yearly_costs()

        expected_final_yearly_costs = 47000.0

        self.assertEqual(
            contract.final_yearly_costs,
            expected_final_yearly_costs,
            msg=f"Yearly costs for visa holder did not compute correctly. {contract.final_yearly_costs}"
        )
