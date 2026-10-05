# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from dateutil.relativedelta import relativedelta
from odoo.tests import tagged
from odoo.addons.hr_payroll.tests.common import TestPayslipContractBase
from odoo.exceptions import UserError


@tagged('payroll_properties')
@tagged('at_install', '-post_install')  # LEGACY at_install
class TestPayrollProperties(TestPayslipContractBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.structure_type_A = cls.env['hr.payroll.structure.type'].create({
            'name': 'Test - Developer A',
        })

        cls.structure_type_B = cls.env['hr.payroll.structure.type'].create({
            'name': 'Test - Developer B',
        })

        cls.structure_A = cls.env['hr.payroll.structure'].create({
            'name': 'Main Default Structure',
            'type_id': cls.structure_type_A.id,
        })

        cls.structure_B = cls.env['hr.payroll.structure'].create({
            'name': 'Secondary Structure',
            'type_id': cls.structure_type.id,
        })

        cls.structure_C = cls.env['hr.payroll.structure'].create({
            'name': 'Main Structure C',
            'type_id': cls.structure_type_B.id,
        })

        cls.structure_type_A.default_struct_id = cls.structure_A
        cls.structure_type_B.default_struct_id = cls.structure_C

        cls.category1 = cls.env['hr.salary.rule.section'].create({
            'name': 'Category 1'
        })

        cls.category2 = cls.env['hr.salary.rule.section'].create({
            'name': 'Category 2'
        })

        cls.category3 = cls.env['hr.salary.rule.section'].create({
            'name': 'Category 3'
        })

        cls.structure_type.default_struct_id = cls.structure_A

        cls.mr_property = cls.env['hr.employee'].create({
            'name': 'Mr. Property',
            'sex': 'male',
            'birthday': '1984-05-01',
            'country_id': cls.env.ref('base.us').id,
        })

        cls.Rule = cls.env['hr.salary.rule']

    def create_property_salary_rule(self, struct_id, code, section, default_value=0, suffix=False, input_selected_by_default=False, input_employee=True, input_payslip=True):
        return self.env['hr.salary.rule'].create({
            'name': 'Test Rule',
            'code': code,
            'category_ids': [(4, self.env.ref('hr_payroll.ALW').id)],
            'condition_select': 'property_input',
            'amount_select': 'property_input',
            'input_usage_employee': input_employee,
            'input_usage_payslip': input_payslip,
            'input_section': section.id,
            'input_selected_by_default': input_selected_by_default,
            'input_default_value': default_value,
            'input_suffix': suffix,
            'struct_ids': [(4, struct_id.id)],
        })

    def generate_payslip(self, struct, date, employee, version=None):
        test_payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id if employee else self.richard_emp.id,
            'version_id': version.id if version else employee.version_id.id,
            'company_id': employee.company_id.id,
            'struct_id': struct.id,
            'date_from': date,
            'date_to': date + relativedelta(months=1, days=-1),
        })

        test_payslip.compute_sheet()

        return test_payslip

    def test_add_property_to_version_definition(self):
        rule = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_test_1', section=self.category1, default_value=100, input_payslip=False)

        version_def = self.structure_A.version_properties_definition
        self.assertEqual(len(version_def), 2)  # Separator + property
        self.assertEqual(version_def[0]['type'], 'separator')
        self.assertEqual(version_def[0]['name'], f'separator_{self.category1.id}')
        self.assertEqual(version_def[1]['name'], f'{rule.code}')
        self.assertEqual(version_def[1]['type'], 'float')
        self.assertEqual(version_def[1]['default'], 100.0)

    # NOTE: payslip-side properties were removed in the input.type refactor.
    # Per-payslip values now live as hr.payslip.input rows, so the old
    # test_add_property_to_payslip_definition test has been deleted.

    def test_no_duplicate_property_in_version_definition(self):
        self.create_property_salary_rule(struct_id=self.structure_A, code='rule_test_dup', section=self.category1, default_value=200)
        version_def_initial = self.structure_A.version_properties_definition
        self.assertEqual(len(version_def_initial), 2)

        # Add again
        version_def_after = self.structure_A.version_properties_definition
        self.assertEqual(len(version_def_after), 2)
        self.assertEqual(version_def_initial, version_def_after)

    def test_selected_by_default_property_in_version_definition(self):
        self.create_property_salary_rule(
            struct_id=self.structure_A, code='rule_default', section=self.category1,
            input_selected_by_default=True, default_value=100,
        )

        version_def = self.structure_A.version_properties_definition
        self.assertEqual(version_def[1]['type'], 'float')
        self.assertEqual(version_def[1]['default'], 100)

    def test_property_suffix(self):
        self.create_property_salary_rule(struct_id=self.structure_A, code='rule_with_suffix', section=self.category1, suffix="Per month")
        self.create_property_salary_rule(struct_id=self.structure_A, code='rule_no_suffix', section=self.category1)

        version_def = self.structure_A.version_properties_definition
        self.assertEqual(version_def[1]['suffix'], 'Per month')
        self.assertFalse('suffix' in version_def[2])

    def test_compute_amount_select(self):
        # Test the default value and update to property_input
        rule = self.env["hr.salary.rule"].create({
            'name': 'Test Rule',
            'code': 'test_rule_1',
            'category_ids': [(4, self.env.ref('hr_payroll.ALW').id)],
            'condition_select': 'none',
            'input_usage_payslip': True,
            'input_section': self.category1.id,
            'input_default_value': 100,
            'struct_ids': [(4, self.structure_A.id)],
        })
        self.assertEqual(rule.amount_select, 'fix')
        rule.condition_select = 'property_input'
        self.assertEqual(rule.amount_select, 'property_input')
        # Test a rule set to property_input right away
        rule = self.env["hr.salary.rule"].create({
            'name': 'Test Rule',
            'code': 'test_rule_2',
            'category_ids': [(4, self.env.ref('hr_payroll.ALW').id)],
            'condition_select': 'property_input',
            'input_usage_payslip': True,
            'input_section': self.category1.id,
            'input_default_value': 100,
            'struct_ids': [(4, self.structure_A.id)],
        })
        self.assertEqual(rule.amount_select, 'property_input')

    def test_compute_input_used_in_definition(self):
        rule = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_monetary', section=self.category1)
        rule_percentage = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_percentage', section=self.category1)

        (rule + rule_percentage)._compute_input_used_in_definition()
        self.assertTrue(rule.input_used_in_definition)
        self.assertTrue(rule_percentage.input_used_in_definition)

    def test_update_property_suffix(self):
        rule = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_monetary', section=self.category1)

        version_def = self.structure_A.version_properties_definition
        self.assertFalse('suffix' in version_def[1])

        rule.input_suffix = 'Test Suffix'
        version_def = self.structure_A.version_properties_definition
        self.assertEqual(version_def[1]['suffix'], 'Test Suffix')

    def test_update_property_default_value(self):
        rule = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_monetary', section=self.category1, default_value=150)

        version_def = self.structure_A.version_properties_definition
        self.assertEqual(version_def[1]['default'], 150)

        rule.input_default_value = 400
        version_def = self.structure_A.version_properties_definition
        self.assertEqual(version_def[1]['default'], 400)

    def test_update_property_name(self):
        rule = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_monetary', section=self.category1, default_value=150)

        version_def = self.structure_A.version_properties_definition
        self.assertEqual(version_def[1]['string'], "Test Rule")

        rule.name = "Renamed rule"
        version_def = self.structure_A.version_properties_definition
        self.assertEqual(version_def[1]['string'], "Renamed rule")

    def test_multiple_rules_same_category_in_version_definition(self):
        rule1 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_multi1', section=self.category1, default_value=10)
        rule2 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_multi2', section=self.category1, default_value=20)

        version_def = self.structure_A.version_properties_definition
        self.assertEqual(len(version_def), 3)  # Separator + 2 properties
        self.assertEqual(version_def[0]['type'], 'separator')
        self.assertEqual(version_def[0]['name'], f'separator_{self.category1.id}')
        prop_names = [prop['name'] for prop in version_def[1:]]
        self.assertIn(rule1.code, prop_names)
        self.assertIn(rule2.code, prop_names)

    def test_multiple_categories_in_version_definition(self):
        rule1 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_cat1', section=self.category1, default_value=10)
        rule2 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_cat2', section=self.category2, default_value=20)

        version_def = self.structure_A.version_properties_definition
        self.assertEqual(len(version_def), 4)  # 2 separators + 2 properties
        self.assertEqual(version_def[0]['name'], f'separator_{self.category1.id}')
        self.assertEqual(version_def[1]['name'], rule1.code)
        self.assertEqual(version_def[2]['name'], f'separator_{self.category2.id}')
        self.assertEqual(version_def[3]['name'], rule2.code)

    def test_salary_rule_section_sequence_ordering(self):
        self.category1.sequence = 432
        self.category2.sequence = 99
        self.category3.sequence = 667

        rule1 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_cat1', section=self.category1, default_value=10)
        rule2 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_cat2', section=self.category2, default_value=20)
        rule3 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_cat3', section=self.category3, default_value=20)

        version_def = self.structure_A.version_properties_definition
        self.assertEqual(len(version_def), 6)  # 3 separators + 3 properties
        self.assertEqual(version_def[0]['name'], f'separator_{self.category2.id}')
        self.assertEqual(version_def[1]['name'], rule2.code)
        self.assertEqual(version_def[2]['name'], f'separator_{self.category1.id}')
        self.assertEqual(version_def[3]['name'], rule1.code)
        self.assertEqual(version_def[4]['name'], f'separator_{self.category3.id}')
        self.assertEqual(version_def[5]['name'], rule3.code)

    def test_property_inserted_in_right_section(self):
        self.category1.sequence = 432
        self.category2.sequence = 99

        rule1 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_cat1', section=self.category1, default_value=10)
        rule2 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_cat2', section=self.category2, default_value=20)

        version_def = self.structure_A.version_properties_definition
        self.assertEqual(len(version_def), 4)  # 2 separators + 2 properties
        self.assertEqual(version_def[0]['name'], f'separator_{self.category2.id}')
        self.assertEqual(version_def[1]['name'], rule2.code)
        self.assertEqual(version_def[2]['name'], f'separator_{self.category1.id}')
        self.assertEqual(version_def[3]['name'], rule1.code)

    def test_insert_position_existing_separator_in_version_definition(self):
        self.create_property_salary_rule(struct_id=self.structure_A, code='existing_prop', section=self.category1, default_value=0)
        self.create_property_salary_rule(struct_id=self.structure_A, code='existing_prop_2', section=self.category2, default_value=0)

        rule = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_insert', section=self.category1, default_value=50)

        version_def = self.structure_A.version_properties_definition
        self.assertEqual(len(version_def), 5)  # Original 3 + 1 new property
        self.assertEqual(version_def[0]['type'], 'separator')  # category1 separator
        self.assertEqual(version_def[0]['name'], f'separator_{self.category1.id}')
        self.assertEqual(version_def[1]['name'], 'existing_prop')
        self.assertEqual(version_def[2]['name'], rule.code)  # Inserted before category2 separator
        self.assertEqual(version_def[3]['type'], 'separator')  # category2 separator
        self.assertEqual(version_def[3]['name'], f'separator_{self.category2.id}')
        self.assertEqual(version_def[4]['name'], 'existing_prop_2')

    def test_two_rules_in_different_sections(self):
        rule_1 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_sec1', section=self.category1, default_value=100)
        rule_2 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_sec2', section=self.category2, default_value=200)

        version_def = self.structure_A.version_properties_definition
        self.assertEqual(len(version_def), 4)  # 2 separators + 2 properties
        prop_names = [p['name'] for p in version_def if p.get('type') != 'separator']
        self.assertIn(rule_1.code, prop_names)
        self.assertIn(rule_2.code, prop_names)

    def test_properties_set_with_structure_type(self):

        rule_1 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_1', section=self.category1, default_value=100)
        rule_2 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_2', section=self.category2, default_value=150)
        rule_3 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_3', section=self.category2, default_value=200)

        rule_4 = self.create_property_salary_rule(struct_id=self.structure_C, code='rule_c_1', section=self.category1, default_value=250)
        rule_5 = self.create_property_salary_rule(struct_id=self.structure_C, code='rule_c_2', section=self.category1, default_value=300)

        self.mr_property.version_id.structure_type_id = self.structure_type_A
        self.assertDictEqual(dict(self.mr_property.version_id.payroll_properties), {rule_1.code: 100.0, rule_2.code: 150.0, rule_3.code: 200.0})

        self.mr_property.version_id.structure_type_id = self.structure_type_B
        self.assertDictEqual(dict(self.mr_property.version_id.payroll_properties), {rule_4.code: 250.0, rule_5.code: 300.0})

    def test_property_get_operation_on_version(self):
        self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_1', section=self.category1, default_value=100)
        self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_2', section=self.category2, default_value=150)
        self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_3', section=self.category2, default_value=200)

        self.mr_property.version_id.structure_type_id = self.structure_type_A
        self.assertEqual(self.mr_property.version_id._get_property_input_value('rule_a_1'), 100)
        self.assertEqual(self.mr_property.version_id._get_property_input_value('rule_a_2'), 150)
        self.assertEqual(self.mr_property.version_id._get_property_input_value('rule_a_3'), 200)

    def test_property_set_operation_on_version(self):
        self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_1', section=self.category1, default_value=100)
        self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_2', section=self.category2, default_value=150)
        self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_3', section=self.category2, default_value=200)

        self.mr_property.version_id.structure_type_id = self.structure_type_A
        self.mr_property.version_id._set_property_input_value('rule_a_1', 999)
        self.assertEqual(self.mr_property.version_id._get_property_input_value('rule_a_1'), 999)
        self.assertEqual(self.mr_property.version_id._get_property_input_value('rule_a_2'), 150)
        self.assertEqual(self.mr_property.version_id._get_property_input_value('rule_a_3'), 200)

    def test_properties_copy_and_update_on_version(self):
        self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_1', section=self.category1, default_value=100)
        self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_2', section=self.category2, default_value=150)
        self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_3', section=self.category2, default_value=200)

        self.mr_property.version_id.structure_type_id = self.structure_type_A
        self.mr_property.version_id._set_property_input_value('rule_a_1', 999)
        self.mr_property.version_id._set_property_input_value('rule_a_2', 998)
        self.mr_property.version_id._set_property_input_value('rule_a_3', 997)

        self.mr_property.create_version({
            'date_version': date(2025, 1, 1)
        })

        self.assertEqual(self.mr_property.version_ids[0]._get_property_input_value('rule_a_1'), 999)
        self.assertEqual(self.mr_property.version_ids[0]._get_property_input_value('rule_a_2'), 998)
        self.assertEqual(self.mr_property.version_ids[0]._get_property_input_value('rule_a_3'), 997)

        self.assertEqual(self.mr_property.version_ids[1]._get_property_input_value('rule_a_1'), 999)
        self.assertEqual(self.mr_property.version_ids[1]._get_property_input_value('rule_a_2'), 998)
        self.assertEqual(self.mr_property.version_ids[1]._get_property_input_value('rule_a_3'), 997)

        self.mr_property.version_ids[1]._set_property_input_value('rule_a_1', 444)

        self.assertEqual(self.mr_property.version_ids[0]._get_property_input_value('rule_a_1'), 999)
        self.assertEqual(self.mr_property.version_ids[0]._get_property_input_value('rule_a_2'), 998)
        self.assertEqual(self.mr_property.version_ids[0]._get_property_input_value('rule_a_3'), 997)

        self.assertEqual(self.mr_property.version_ids[1]._get_property_input_value('rule_a_1'), 444)
        self.assertEqual(self.mr_property.version_ids[1]._get_property_input_value('rule_a_2'), 998)
        self.assertEqual(self.mr_property.version_ids[1]._get_property_input_value('rule_a_3'), 997)

    def test_properties_computed_on_payslip(self):
        """
        Property-input values from version.payroll_properties are materialised as
        hr.payslip.input rows when the payslip is computed, and produce payslip
        lines with the corresponding amounts.
        """

        rule_1 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_1', section=self.category1, default_value=100)
        rule_2 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_2', section=self.category2, default_value=150, input_payslip=False)
        rule_3 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_3', section=self.category2, default_value=200)

        self.mr_property.version_id.structure_type_id = self.structure_type_A
        self.mr_property.version_id.contract_date_start = date(2025, 1, 1)
        self.mr_property.version_id._set_property_input_value('rule_a_1', 123)
        self.mr_property.version_id._set_property_input_value('rule_a_3', 456)

        property_slip = self.generate_payslip(struct=self.structure_A, date=date(2025, 1, 1), employee=self.mr_property)

        # Property values are now materialised as input rows on the payslip.
        amounts_by_code = {line.code: line.amount for line in property_slip.input_line_ids}
        self.assertEqual(amounts_by_code.get(rule_1.code), 123.0)
        self.assertEqual(amounts_by_code.get(rule_3.code), 456.0)
        self.assertEqual(amounts_by_code.get(rule_2.code), 150.0)  # falls back to rule default

        # All three rules fire with the matching amounts.
        totals_by_code = {line.code: line.total for line in property_slip.line_ids}
        self.assertEqual(totals_by_code.get(rule_1.code), 123.0)
        self.assertEqual(totals_by_code.get(rule_3.code), 456.0)
        self.assertEqual(totals_by_code.get(rule_2.code), 150.0)

    def test_localdict_compute(self):
        rule_1 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_1', section=self.category1, default_value=100)
        rule_2 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_2', section=self.category2, default_value=150)
        rule_3 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_3', section=self.category2, default_value=200)

        self.mr_property.version_id.structure_type_id = self.structure_type_A
        self.mr_property.version_id.contract_date_start = date(2025, 1, 1)
        self.mr_property.version_id._set_property_input_value('rule_a_1', 123)
        self.mr_property.version_id._set_property_input_value('rule_a_3', 456)

        property_slip = self.generate_payslip(struct=self.structure_A, date=date(2025, 1, 1), employee=self.mr_property)
        # All input rows for property rules carry the resolved amount on .amount.
        amounts_by_code = {line.code: line.amount for line in property_slip._get_localdict()['inputs'].values()}
        self.assertEqual(amounts_by_code.get(rule_1.code), 123.0)
        self.assertEqual(amounts_by_code.get(rule_2.code), 150.0)  # falls back to rule default
        self.assertEqual(amounts_by_code.get(rule_3.code), 456.0)

    def test_properties_payslip_lines(self):

        self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_1', section=self.category1, default_value=100)
        self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_2', section=self.category2, default_value=150)
        self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_3', section=self.category2, default_value=200)

        self.mr_property.version_id.structure_type_id = self.structure_type_A
        self.mr_property.version_id.contract_date_start = date(2025, 1, 1)
        self.mr_property.version_id._set_property_input_value('rule_a_1', 123)
        self.mr_property.version_id._set_property_input_value('rule_a_3', 456)

        property_slip = self.generate_payslip(struct=self.structure_A, date=date(2025, 1, 1), employee=self.mr_property)
        line_values = property_slip._get_line_values(self.structure_A.rule_ids.mapped('code'), compute_sum=True)
        self.assertEqual(line_values['rule_a_1']['sum']['total'], 123)
        self.assertEqual(line_values['rule_a_2']['sum']['total'], 150)
        self.assertEqual(line_values['rule_a_3']['sum']['total'], 456)

    def test_localdict_compute_with_folded_separator(self):
        """Check payslip computation when a separator has a value (it has been folded/unfolded in the UI)."""
        rule = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_1', section=self.category1, default_value=100)

        version_def = self.structure_A.version_properties_definition
        self.assertTrue(version_def[0]['type'], 'separator')
        version_def[0]['value'] = False
        version_def[1]['value'] = 123

        self.mr_property.version_id.structure_type_id = self.structure_type_A
        self.mr_property.version_id.contract_date_start = date(2025, 1, 1)
        self.mr_property.version_id.write({'payroll_properties': version_def})

        property_slip = self.generate_payslip(struct=self.structure_A, date=date(2025, 1, 1), employee=self.mr_property)
        inputs = property_slip._get_localdict()['inputs']
        self.assertIn(rule.code, inputs)
        self.assertEqual(inputs[rule.code].amount, 123.0)

    def test_property_rule_duplicate(self):
        rule = self.create_property_salary_rule(struct_id=self.structure_A, code='ORIG_PROP', section=self.category1, default_value=50)

        copied_rule = rule.copy()
        self.assertEqual(copied_rule.condition_select, 'property_input')
        self.assertEqual(copied_rule.input_default_value, 50)
        self.assertEqual(copied_rule.input_section, rule.input_section)

    def test_unlink_section_constraints(self):
        """
        Test deletion constraints for Salary Rule Sections:
        1. Linked to an Input Rule -> Blocked
        2. Linked to an unused Rule -> Allowed
        3. Not linked to anything -> Allowed
        """
        active_input_section, unused_rule_section, unused_section = self.env['hr.salary.rule.section'].create([
            {'name': 'Active Input Section', 'sequence': 1},
            {'name': 'Unused Rule Section', 'sequence': 2},
            {'name': 'Unused Section', 'sequence': 3},
        ])
        hra_rule = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_1', section=active_input_section, default_value=100)
        unused_rule = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_2', section=unused_section, default_value=100)
        unused_rule.write({'active': False})

        with self.assertRaises(UserError):
            active_input_section.unlink()

        hra_rule.write({
            'input_section': unused_rule_section.id,
        })

        active_input_section.unlink()
        self.assertFalse(active_input_section.exists())

        unused_section.unlink()
        self.assertFalse(unused_section.exists())
