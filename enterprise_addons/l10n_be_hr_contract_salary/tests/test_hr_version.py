from freezegun import freeze_time

from odoo.tests import tagged, Form

from odoo.addons.l10n_be_hr_payroll.tests.test_hr_version import TestPayrollHrVersion


@tagged('-at_install', 'post_install', 'post_install_l10n', 'salary')
class TestHrVersion(TestPayrollHrVersion):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employment_sign_template = cls.env['sign.template'].create({
            'name': 'Test Employment Contract',
            'tag_ids': [cls.env.ref('sign.sign_template_tag_1').id]
        })

    @freeze_time('2025-12-01')
    def test_no_dimona_version_write_salary_simulation(self):
        """ Assert no dimona action is triggered when writing on a version while we are in a `hr_version_context` """
        self.test_company.l10n_be_dimona_environment = 'sandbox'
        self.student_emp.niss = '19082624244'

        # Assert no dimona has been created for that employee
        self.assertFalse(self.student_emp.l10n_be_last_dimona_declaration_id)
        self.assertEqual(len(self.student_emp.version_ids), 1)
        student_version = self.student_emp.version_ids[0].with_company(self.test_company)

        # Simulate a `hr_version_context` by setting 'salary_simulation' in the context
        # Assert writing on the employee with 'salary_simulation' set doesn't trigger a dimona action
        student_version.with_context(salary_simulation=True).write({
            'private_zip': 1367,
            'l10n_be_dimona_next_action': 'in',
            'l10n_be_dimona_planned_hours': 1,
            'contract_date_start': "2026-01-01",
            'contract_date_end': "2026-01-02",
        })
        self.assertFalse(self.student_emp.l10n_be_last_dimona_declaration_id, 'No dimona action should be triggered here!')

        # Assert creating a new offer doesn't trigger a dimona action
        with freeze_time('2026-01-02'):
            action_generate_offer = self.student_emp.action_generate_offer()
            with Form.from_action(self.student_emp.env, action_generate_offer) as offer_form:
                offer_form.sign_template_id = self.employment_sign_template
                offer_form.contract_end_date = '2026-01-03'
                offer_form.contract_end_date = '2026-01-03'

        self.assertFalse(self.student_emp.l10n_be_last_dimona_declaration_id, 'No dimona action should be triggered here!')

        # Assert writing on the version without 'salary_simulation' triggers a dimona action
        student_version.write({
            'contract_date_start': "2026-01-02",
        })
        self.assertTrue(self.student_emp.l10n_be_last_dimona_declaration_id, 'A dimona action should\'ve been triggered!')
