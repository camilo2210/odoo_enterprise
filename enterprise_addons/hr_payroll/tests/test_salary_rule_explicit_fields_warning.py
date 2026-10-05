# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo.tests import tagged, TransactionCase


@tagged('-at_install', 'post_install', 'salary_rule_explicit_fields_warning')
class TestSalaryRuleExplicitFieldsWarning(TransactionCase):

    def setUp(self):
        super().setUp()
        self.structure = self.env.ref('hr_payroll.default_structure')
        self.basic_category = self.env.ref('hr_payroll.BASIC')

    def _get_salary_rule_model(self):
        return self.env['hr.salary.rule'].with_context(
            install_mode=True,
            install_module='hr_payroll',
            install_filename='test_salary_rule_explicit_fields_warning.xml',
        )

    def test_warning_missing_base_fields(self):
        SalaryRule = self._get_salary_rule_model()

        with self.assertLogs(logging.getLogger('odoo.addons.hr_payroll.models.hr_salary_rule'), level='WARNING') as capture:
            SalaryRule.create({
                'name': 'Test Salary Rule Missing Base Fields',
                'code': 'TEST_RULE_EXPLICIT_1',
                'sequence': 10,
                'struct_ids': [(4, self.structure.id)],
                'category_ids': [(4, self.basic_category.id)],
            })

        self.assertTrue(
            any('condition_select' in msg and 'amount_select' in msg for msg in capture.output),
            'Expected a warning about missing condition_select and amount_select',
        )

    def test_warning_missing_conditional_fields(self):
        SalaryRule = self._get_salary_rule_model()

        with self.assertLogs(logging.getLogger('odoo.addons.hr_payroll.models.hr_salary_rule'), level='WARNING') as capture:
            SalaryRule.create({
                'name': 'Test Salary Rule Missing Conditional Fields',
                'code': 'TEST_RULE_EXPLICIT_2',
                'sequence': 11,
                'struct_ids': [(4, self.structure.id)],
                'category_ids': [(4, self.basic_category.id)],
                'condition_select': 'python',
                'amount_select': 'code',
            })

        self.assertTrue(
            any('condition_python' in msg for msg in capture.output),
            'Expected a warning about missing condition_python',
        )
        self.assertTrue(
            any('amount_python_compute' in msg for msg in capture.output),
            'Expected a warning about missing amount_python_compute',
        )

    def test_warning_missing_quantity_for_fixed_amount(self):
        SalaryRule = self._get_salary_rule_model()

        with self.assertLogs(logging.getLogger('odoo.addons.hr_payroll.models.hr_salary_rule'), level='WARNING') as capture:
            SalaryRule.create({
                'name': 'Test Salary Rule Missing Quantity',
                'code': 'TEST_RULE_EXPLICIT_3',
                'sequence': 12,
                'struct_ids': [(4, self.structure.id)],
                'category_ids': [(4, self.basic_category.id)],
                'condition_select': 'none',
                'amount_select': 'fix',
                'amount_fix': 100.0,
            })

        self.assertTrue(
            any('quantity' in msg for msg in capture.output),
            'Expected a warning about missing quantity',
        )

    def test_warning_missing_property_input_metadata_fields(self):
        SalaryRule = self._get_salary_rule_model()

        with self.assertLogs(logging.getLogger('odoo.addons.hr_payroll.models.hr_salary_rule'), level='WARNING') as capture:
            SalaryRule.create({
                'name': 'Test Salary Rule Missing Property Input Metadata',
                'code': 'TEST_RULE_EXPLICIT_4',
                'sequence': 13,
                'struct_ids': [(4, self.structure.id)],
                'category_ids': [(4, self.basic_category.id)],
                'condition_select': 'property_input',
                'input_usage_payslip': True,
            })

        for field_name in (
            'input_usage_employee',
        ):
            self.assertTrue(
                any(field_name in msg for msg in capture.output),
                f'Expected a warning about missing {field_name}',
            )

        for field_name in (
            'input_name',
            'input_suffix',
            'input_section',
            'input_default_value',
            'input_selected_by_default',
        ):
            self.assertFalse(
                any(field_name in msg for msg in capture.output),
                f'Did not expect a warning about missing {field_name}',
            )
