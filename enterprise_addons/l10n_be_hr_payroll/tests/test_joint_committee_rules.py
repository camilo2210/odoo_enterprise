from datetime import date
from odoo.tests import tagged

from .common import TestPayrollCommon


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestJointCommitteeFiltering(TestPayrollCommon):
    """
    Tests salary rule filtering based on Employee Joint Committee.

    Scenario:
        Rule A  -> no joint committee   → applies to all employees
        Rule B  -> JC1 only
        Rule C  -> JC2 only

        Emp0 -> no JC assigned
        Emp1 -> JC1
        Emp2 -> JC2
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Joint Committees
        jcs = [
            {
                'name': 'JC1',
                'egov3_code': '001',
            },
            {
                'name': 'JC2',
                'egov3_code': '002',
            },
            {
                'name': 'JC3',
                'egov3_code': '003',
            },
            {
                'name': 'Top JC',
                'egov3_code': '305',
            },
            {
                'name': 'Child 1',
                'egov3_code': '305.01',
            },
            {
                'name': 'Child 2',
                'egov3_code': '305.02',
            },
            {
                'name': 'Grandchild',
                'egov3_code': '305.02.01',
            },
        ]

        created_jcs = cls.env['l10n.be.joint.committee'].create(jcs)

        (
            cls.JC1,
            cls.JC2,
            cls.JC3,
            cls.JC_TOP,
            cls.JC_CHILD_1,
            cls.JC_CHILD_2,
            cls.JC_GRANDCHILD,
        ) = created_jcs

        # Assign parents to build the hierarchy
        cls.JC_CHILD_1.parent_id = cls.JC_TOP
        cls.JC_CHILD_2.parent_id = cls.JC_TOP
        cls.JC_GRANDCHILD.parent_id = cls.JC_CHILD_2

        # Payroll Structure
        cls.structure = cls.env['hr.payroll.structure'].create({
            'name': 'JC Test Structure',
            'type_id': cls.env.ref('hr.structure_type_employee_cp200').id
        })

        # Salary Rules
        rules = [
            {
                'name': 'Rule A (ALL)',
                'code': 'A',
                'sequence': 1,
                'amount_select': 'fix',
                'amount_fix': 100,
                'struct_ids': [(4, cls.structure.id)],
            },
            {
                'name': 'Rule B (JC1)',
                'code': 'B',
                'sequence': 2,
                'amount_select': 'fix',
                'amount_fix': 200,
                'struct_ids': [(4, cls.structure.id)],
                'l10n_be_joint_committee_ids': [(6, 0, [cls.JC1.id])],
            },
            {
                'name': 'Rule C (JC2)',
                'code': 'C',
                'sequence': 3,
                'amount_select': 'fix',
                'amount_fix': 300,
                'struct_ids': [(4, cls.structure.id)],
                'l10n_be_joint_committee_ids': [(6, 0, [cls.JC2.id])],
            },
            {
                'name': 'Rule F (JC1 + JC3)',
                'code': 'D',
                'sequence': 6,
                'amount_select': 'fix',
                'amount_fix': 600,
                'struct_ids': [(4, cls.structure.id)],
                'l10n_be_joint_committee_ids': [(6, 0, [cls.JC1.id, cls.JC3.id])],
            },
            # Hierarchical tests
            {
                'name': 'Rule Top JC',
                'code': 'TOP',
                'sequence': 10,
                'amount_select': 'fix',
                'amount_fix': 1000,
                'struct_ids': [(4, cls.structure.id)],
                'l10n_be_joint_committee_ids': [(6, 0, [cls.JC_TOP.id])],
            },
            {
                'name': 'Rule Child JC',
                'code': 'CHILD',
                'sequence': 11,
                'amount_select': 'fix',
                'amount_fix': 1100,
                'struct_ids': [(4, cls.structure.id)],
                'l10n_be_joint_committee_ids': [(6, 0, [cls.JC_CHILD_2.id])],
            },
            {
                'name': 'Rule GRANDCHILD',
                'code': 'ABC',
                'sequence': 12,
                'amount_select': 'fix',
                'amount_fix': 1200,
                'struct_ids': [(4, cls.structure.id)],
                'l10n_be_joint_committee_ids': [(6, 0, [cls.JC_GRANDCHILD.id])],
            },
        ]

        created_rules = cls.env['hr.salary.rule'].create(rules)

        (
            cls.rule_A,
            cls.rule_B,
            cls.rule_C,
            cls.rule_D,
            cls.rule_TOP,
            cls.rule_CHILD,
            cls.rule_GRANDCHILD,
        ) = created_rules

        # Create employees
        cls.emp0 = cls.create_employee({
            'name': 'Emp0 - No JC',
            'contract_date_start': date(2023, 1, 1),
        })

        cls.emp1 = cls.create_employee({
            'name': 'Emp1 - JC1',
            'l10n_be_joint_committee_id': cls.JC1.id,
            'contract_date_start': date(2023, 1, 1),
        })

        cls.emp2 = cls.create_employee({
            'name': 'Emp2 - JC2',
            'l10n_be_joint_committee_id': cls.JC2.id,
            'contract_date_start': date(2023, 1, 1),
        })

        # Hierarchy employees
        cls.emp_child_1 = cls.create_employee({'name': 'Emp Child 1', 'l10n_be_joint_committee_id': cls.JC_CHILD_1.id, 'contract_date_start': date(2023, 1, 1)})
        cls.emp_child_2 = cls.create_employee({'name': 'Emp Child 2', 'l10n_be_joint_committee_id': cls.JC_CHILD_2.id, 'contract_date_start': date(2023, 1, 1)})
        cls.emp_grandchild = cls.create_employee({'name': 'Emp Grandchild', 'l10n_be_joint_committee_id': cls.JC_GRANDCHILD.id, 'contract_date_start': date(2023, 1, 1)})

    def _make_payslip(self, employee):
        version = employee.version_id

        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': version.id,
            'company_id': self.belgian_company.id,
            'struct_id': self.structure.id,
            'date_from': date(2023, 1, 1),
            'date_to': date(2023, 1, 31),
        })

        payslip.compute_sheet()
        return payslip

    def test_emp0_no_jc(self):
        """Employee with no JC → only Rule A must apply."""
        payslip = self._make_payslip(self.emp0)
        codes = set(payslip.line_ids.mapped('code'))
        self.assertIn('A', codes)
        self.assertNotIn('B', codes)
        self.assertNotIn('C', codes)

    def test_emp1_jc1(self):
        """Employee with JC1 → Rule A + Rule B."""
        payslip = self._make_payslip(self.emp1)
        codes = set(payslip.line_ids.mapped('code'))
        self.assertIn('A', codes)
        self.assertIn('B', codes)
        self.assertNotIn('C', codes)

    def test_emp2_jc2(self):
        """Employee with JC2 → Rule A + Rule C."""
        payslip = self._make_payslip(self.emp2)
        codes = set(payslip.line_ids.mapped('code'))
        self.assertIn('A', codes)
        self.assertIn('C', codes)
        self.assertNotIn('B', codes)

    def test_multiple_rules_multiple_jcs(self):
        """Employee with JC1 should get all matching rules"""
        payslip = self._make_payslip(self.emp1)  # JC1
        codes = set(payslip.line_ids.mapped('code'))
        self.assertIn('A', codes)
        self.assertIn('B', codes)
        self.assertIn('D', codes)
        self.assertNotIn('C', codes)

    # --- Hierarchy tests ---
    def test_top_rule_applies_to_all_descendants(self):
        """Rule on top JC should apply to all descendants"""
        for emp in [self.emp_child_1, self.emp_child_2, self.emp_grandchild]:
            payslip = self._make_payslip(emp)
            codes = set(payslip.line_ids.mapped('code'))
            self.assertIn('TOP', codes, f"TOP rule missing for {emp.name}")
            self.assertIn('A', codes)

    def test_child_rule_applies_to_child_and_grandchild(self):
        """Rule on child JC applies to child and grandchild but not siblings"""
        # JC_CHILD_2
        payslip_child = self._make_payslip(self.emp_child_2)
        codes_child = set(payslip_child.line_ids.mapped('code'))
        self.assertIn('CHILD', codes_child)
        self.assertIn('TOP', codes_child)

        # JC_GRANDCHILD
        payslip_grandchild = self._make_payslip(self.emp_grandchild)
        codes_grandchild = set(payslip_grandchild.line_ids.mapped('code'))
        self.assertIn('CHILD', codes_grandchild)
        self.assertIn('TOP', codes_grandchild)
        self.assertIn('ABC', codes_grandchild)  # GRANDCHILD rule itself

        # JC_CHILD_1 (sibling of CHILD_2)
        payslip_sibling = self._make_payslip(self.emp_child_1)
        codes_sibling = set(payslip_sibling.line_ids.mapped('code'))
        self.assertNotIn('CHILD', codes_sibling)
        self.assertIn('TOP', codes_sibling)

    def test_grandchild_rule_applies_only_to_grandchild(self):
        """Leaf rule applies only to the specific grandchild, not upwards"""
        # Grandchild
        payslip_grandchild = self._make_payslip(self.emp_grandchild)
        codes_grandchild = set(payslip_grandchild.line_ids.mapped('code'))
        self.assertIn('ABC', codes_grandchild)
        self.assertIn('TOP', codes_grandchild)
        self.assertIn('CHILD', codes_grandchild)

        # Parent (child_2)
        payslip_child = self._make_payslip(self.emp_child_2)
        codes_child = set(payslip_child.line_ids.mapped('code'))
        self.assertNotIn('ABC', codes_child)  # should NOT get grandchild rule
        self.assertIn('CHILD', codes_child)
        self.assertIn('TOP', codes_child)

        # Sibling (child_1)
        payslip_sibling = self._make_payslip(self.emp_child_1)
        codes_sibling = set(payslip_sibling.line_ids.mapped('code'))
        self.assertNotIn('ABC', codes_sibling)
        self.assertNotIn('CHILD', codes_sibling)
        self.assertIn('TOP', codes_sibling)
