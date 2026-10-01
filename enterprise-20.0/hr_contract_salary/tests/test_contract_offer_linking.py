from odoo.tests import TransactionCase, tagged
from datetime import date


@tagged('-at_install', 'post_install', 'offer_version')
class TestContractOfferLinking(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.structure_type = cls.env.ref('hr.structure_type_employee')
        cls.job = cls.env['hr.job'].create({
            'name': 'Senior Developer',
            'company_id': cls.env.company.id,
        })
        cls.default_contract_template, cls.template_high, cls.template_low = cls.env['hr.version'].create([
            {
            'name': 'Developer Template',
            'job_id': cls.job.id,
            'structure_type_id': cls.structure_type.id,
            'wage': 3000,
            'company_id': cls.env.company.id,
            'hr_responsible_id': cls.env.ref('base.user_admin').id,
            },
            {
            'name': 'High Wage Template',
            'job_id': cls.job.id,
            'structure_type_id': cls.structure_type.id,
            'wage': 5000,
            'final_yearly_costs': 70000,
            'company_id': cls.env.company.id,
            'hr_responsible_id': cls.env.ref('base.user_admin').id,
            },
            {
            'name': 'Low Wage Template',
            'job_id': cls.job.id,
            'structure_type_id': cls.structure_type.id,
            'wage': 2500,
            'final_yearly_costs': 35000,
            'company_id': cls.env.company.id,
            'hr_responsible_id': cls.env.ref('base.user_admin').id,
            }
        ])
        cls.applicant1, cls.applicant2 = cls.env['hr.applicant'].create([
            {'partner_name': 'John Doe', 'job_id': cls.job.id},
            {'partner_name': 'Bob Low', 'job_id': cls.job.id},
        ])
        cls.offer1 = cls.env['hr.contract.salary.offer'].create({
            'applicant_id': cls.applicant1.id,
            'contract_template_id': cls.default_contract_template.id,
            'state': 'open',
        })
        cls.employee1 = cls.env['hr.employee'].create({
            'name': 'John Doe',
            'job_id': cls.job.id,
            'company_id': cls.env.company.id,
            'date_version': date(2024, 1, 1),
            'work_email': 'john.doe@test.com',
        })

    def test_offers_appear_in_recruitment_after_signing(self):
        """
        Offers that originated from applicants should still be visible or trackable
        in the recruitment system even after the applicant becomes an employee.
        """

        self.applicant1.write({'employee_id': self.employee1.id})
        self.offer1.write({'state': 'full_signed'})

        # manager completes the accepted applicant offer
        self.employee1.version_id.write({'originated_offer_id': self.offer1.id})
        recruitment_origin_offers = self.env['hr.contract.salary.offer'].search([
            ('employee_version_id.originated_offer_id', '!=', False)
        ])
        self.assertIn(
            self.offer1, recruitment_origin_offers,
            "Offer from recruitment should still be trackable after hiring"
        )
        self.assertTrue(self.offer1.employee_version_id,
            "employee_version_id should be set after full signature"
        )
        self.assertEqual(
            self.offer1.employee_version_id.originated_offer_id,
            self.offer1,
            "Version should maintain link to originating offer",
        )

    def test_filter_offers_by_employee_version_benefits(self):
        """
        Should be able to filter offers based on the employee_version_id
        attributes (like wage, benefits, etc.) to find what employees signed for.
        """
        offer2 = self.env['hr.contract.salary.offer'].create(
            {
                'applicant_id': self.applicant2.id,
                'contract_template_id': self.template_low.id,
                'state': 'open'
            }
        )
        employee2 = self.env['hr.employee'].create(
            {
                'name': 'Bob Low',
                'job_id': self.job.id,
                'company_id': self.env.company.id,
                'date_version': date(2024, 1, 2),
                'work_email': 'bob@test.com'
            }
        )
        self.env['hr.version'].create([
            {
                'applicant_id': self.applicant1.id,
                'employee_id': self.employee1.id,
                'originated_offer_id': self.offer1.id,
                'job_id': self.job.id,
                'structure_type_id': self.structure_type.id,
                'wage': 5000,
                'final_yearly_costs': 70000,
                'company_id': self.env.company.id,
            },
            {
                'applicant_id': self.applicant2.id,
                'employee_id': employee2.id,
                'originated_offer_id': offer2.id,
                'job_id': self.job.id,
                'structure_type_id': self.structure_type.id,
                'wage': 2500,
                'final_yearly_costs': 35000,
                'company_id': self.env.company.id,
            }
        ])
        self.applicant1.write({'employee_id': self.employee1.id})
        self.offer1.write({
            'state': 'full_signed',
        })
        self.applicant2.write({'employee_id': employee2.id})
        offer2.write({
            'state': 'full_signed',
        })

        test_offer_ids = [self.offer1.id, offer2.id]

        high_wage_offers = self.env['hr.contract.salary.offer'].search([
            ('id', 'in', test_offer_ids),
            ('state', '=', 'full_signed'),
            ('employee_version_id.wage', '>=', 4000)
        ])
        self.assertEqual(len(high_wage_offers), 1, "Should find exactly 1 offer with wage >= 4000")
        self.assertIn(self.offer1, high_wage_offers, "John's offer should be in high wage filter")
        self.assertNotIn(offer2, high_wage_offers, "Bob's offer should NOT be in high wage filter")
        low_wage_offers = self.env['hr.contract.salary.offer'].search([
            ('id', 'in', test_offer_ids),
            ('state', '=', 'full_signed'),
            ('employee_version_id.wage', '<', 4000)
        ])
        self.assertEqual(len(low_wage_offers), 1, "Should find exactly 1 offer with wage < 4000")
        self.assertIn(offer2, low_wage_offers, "Bob's offer should be in low wage filter")
        high_cost_offers = self.env['hr.contract.salary.offer'].search([
            ('state', '=', 'full_signed'),
            ('employee_version_id.final_yearly_costs', '>=', 60000)
        ])
        self.assertEqual(len(high_cost_offers), 1, "Should filter by yearly costs correctly")
        self.assertEqual(high_cost_offers, self.offer1, "Only John's offer has high yearly cost")
