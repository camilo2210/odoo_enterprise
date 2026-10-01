# Part of Odoo. See LICENSE file for full copyright and licensing details.

import odoo.tests

from datetime import date, datetime

from odoo import Command
from odoo.tools import is_html_empty
from odoo.addons.base.tests.common import BaseCommon


@odoo.tests.tagged('post_install', '-at_install')
class TestAnonymizedPayruns(BaseCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.credit_account_full, cls.credit_account_half, cls.debit_account_full, cls.debit_account_half = cls.env['account.account'].create([
            {
                'name': 'Credit Account Full',
                'account_type': 'asset_cash',
                'code': 0
            },
            {
                'name': 'Credit Account Half',
                'account_type': 'asset_cash',
                'code': 1
            },
            {
                'name': 'Debit Account',
                'account_type': 'asset_cash',
                'code': 2
            },
            {
                'name': 'Debit Account Half',
                'account_type': 'asset_cash',
                'code': 3
            },
        ])

        cls.test_journal = cls.env['account.journal'].create({
            'name': 'Test Journal',
            'type': 'credit',
            'code': 'TEST',
            'default_account_id': cls.credit_account_full.id,
            'currency_id': cls.env.ref('base.USD').id,
            'company_id': cls.company.id,
        })

        cls.test_structure_type_id = cls.env['hr.payroll.structure.type'].create({
            'name': 'Nordic Warrior',
            'country_id': False,
        })

        cls.plan = cls.env['account.analytic.plan'].create({'name': 'Plan'})

        cls.aa_1, cls.aa_2 = cls.env['account.analytic.account'].create([
            {
                'name': 'Analytic Account 1',
                'plan_id': cls.plan.id,
            },
            {
                'name': 'Analytic Account 2',
                'plan_id': cls.plan.id,
            }
        ])

        cls.nordic_warrior_structure = cls.env['hr.payroll.structure'].create({
            'name': 'Salary Structure for Nordic Warriors',
            'rule_ids': [
                (0, 0, {
                    'name': 'Basic Salary',
                    'amount_select': 'percentage',
                    'amount_percentage': 100,
                    'amount_percentage_base': 'version.wage',
                    'code': 'BASIC',
                    'category_ids': [cls.env.ref('hr_payroll.BASIC').id],
                    'sequence': 1,
                    'account_credit': cls.credit_account_full.id,
                    'account_debit': cls.debit_account_full.id,
                    'analytic_distribution': {str(cls.aa_1.id) + ',' + str(cls.aa_2.id): 100}
                }), (0, 0, {
                    'name': 'Additional Basic Salary',
                    'amount_select': 'percentage',
                    'amount_percentage': 50,
                    'amount_percentage_base': 'version.wage',
                    'code': 'BASICADD',
                    'category_ids': [cls.env.ref('hr_payroll.BASIC').id],
                    'sequence': 2,
                    'account_credit': cls.credit_account_half.id,
                    'account_debit': cls.debit_account_half.id
                }),
            ],
            'type_id': cls.test_structure_type_id.id,
            'journal_id': cls.test_journal.id
        })

        cls.test_structure_type_id['default_struct_id'] = cls.nordic_warrior_structure.id

        cls.emp_thorfinn, cls.emp_einar, cls.emp_canute = cls.env['hr.employee'].create([
            {
                'name': 'Thorfinn',
                'company_id': cls.company.id,
                'version_ids': [
                    (0, 0, {
                        'name': 'Thorfinn Version',
                        'company_id': cls.company.id,
                        'contract_date_start': datetime(2026, 3, 1),
                        'contract_date_end': datetime(2026, 3, 31),
                        'wage': 3000,
                        'date_version': datetime(2026, 3, 1).date(),
                        'structure_id': cls.nordic_warrior_structure.id,
                        'structure_type_id': cls.nordic_warrior_structure.type_id.id,
                    })]
            },
            {
                'name': 'Einar',
                'company_id': cls.company.id,
                'version_ids': [
                    (0, 0, {
                        'name': 'Einar Version',
                        'company_id': cls.company.id,
                        'contract_date_start': datetime(2026, 3, 1),
                        'contract_date_end': datetime(2026, 3, 31),
                        'wage': 3000,
                        'date_version': datetime(2026, 3, 1).date(),
                        'structure_id': cls.nordic_warrior_structure.id,
                        'structure_type_id': cls.nordic_warrior_structure.type_id.id,
                    })]
            },
            {
                'name': 'Canute',
                'company_id': cls.company.id,
                'version_ids': [
                    (0, 0, {
                        'name': 'Canute Version',
                        'company_id': cls.company.id,
                        'contract_date_start': datetime(2026, 3, 1),
                        'contract_date_end': datetime(2026, 3, 31),
                        'wage': 3000,
                        'date_version': datetime(2026, 3, 1).date(),
                        'structure_id': cls.nordic_warrior_structure.id,
                        'structure_type_id': cls.nordic_warrior_structure.type_id.id,
                    })]
            },
        ])

        for emp in [cls.emp_thorfinn, cls.emp_einar, cls.emp_canute]:
            emp.version_ids = emp.version_ids.filtered('name')  # Remove unnamed versions created by default

    def test_check_correct_anonymization_with_analytic_distribution(self):
        self.company.batch_payroll_move_lines = True
        payrun = self.env['hr.payslip.run'].create({
            'name': 'Test Payrun',
            'date_start': date(2026, 3, 1),
            'date_end': date(2026, 3, 31),
            'structure_id': self.nordic_warrior_structure.id,
        })
        payrun._generate_payslips()
        payrun.action_validate()

        expected_result = [
            ('Basic Salary', {str(self.aa_1.id) + ',' + str(self.aa_2.id): 100}, 0.0, 9000.0),
            ('Basic Salary', {str(self.aa_1.id) + ',' + str(self.aa_2.id): 100}, 9000.0, 0.0),
            ('Additional Basic Salary', False, 0.0, 4500.0),
            ('Additional Basic Salary', False, 4500.0, 0.0),
        ]

        real_result = [(line.name, line.analytic_distribution, line.credit, line.debit) for line in payrun.move_id.line_ids]

        self.assertEqual(real_result, expected_result)

    def test_batch_move_lines_keeps_distinct_analytic_percentages(self):
        """ With batch_payroll_move_lines, employees sharing the same analytic
        account but with different percentages must not be merged into a single
        move line — each distribution must keep its own line.
        """
        self.company.batch_payroll_move_lines = True
        self.nordic_warrior_structure.rule_ids.analytic_distribution = False
        self.emp_thorfinn.version_id.analytic_distribution = {str(self.aa_1.id): 50}
        self.emp_einar.version_id.analytic_distribution = {str(self.aa_1.id): 70}
        self.emp_canute.version_id.analytic_distribution = {str(self.aa_1.id): 50}

        payrun = self.env['hr.payslip.run'].create({
            'name': 'Test Payrun Distinct Distributions',
            'date_start': date(2026, 3, 1),
            'date_end': date(2026, 3, 31),
            'structure_id': self.nordic_warrior_structure.id,
        })
        payrun._generate_payslips()
        payrun.action_validate()

        expected_result = [
            ('Basic Salary', {str(self.aa_1.id): 50}, 0.0, 6000.0),
            ('Basic Salary', {str(self.aa_1.id): 50}, 6000.0, 0.0),
            ('Additional Basic Salary', {str(self.aa_1.id): 50}, 0.0, 3000.0),
            ('Additional Basic Salary', {str(self.aa_1.id): 50}, 3000.0, 0.0),
            ('Basic Salary', {str(self.aa_1.id): 70}, 0.0, 3000.0),
            ('Basic Salary', {str(self.aa_1.id): 70}, 3000.0, 0.0),
            ('Additional Basic Salary', {str(self.aa_1.id): 70}, 0.0, 1500.0),
            ('Additional Basic Salary', {str(self.aa_1.id): 70}, 1500.0, 0.0),
        ]
        real_result = [(line.name, line.analytic_distribution, line.credit, line.debit) for line in payrun.move_id.line_ids]
        self.assertEqual(real_result, expected_result)

    def test_batch_move_lines_merges_identical_version_distributions(self):
        """ With batch_payroll_move_lines, employees sharing the exact same
        version-level analytic distribution must be merged into a single line.
        """
        self.company.batch_payroll_move_lines = True
        self.nordic_warrior_structure.rule_ids.analytic_distribution = False
        distribution = {str(self.aa_1.id): 60}
        (self.emp_thorfinn + self.emp_einar + self.emp_canute).version_id.analytic_distribution = distribution

        payrun = self.env['hr.payslip.run'].create({
            'name': 'Test Payrun Identical Distributions',
            'date_start': date(2026, 3, 1),
            'date_end': date(2026, 3, 31),
            'structure_id': self.nordic_warrior_structure.id,
        })
        payrun._generate_payslips()
        payrun.action_validate()

        expected_result = [
            ('Basic Salary', distribution, 0.0, 9000.0),
            ('Basic Salary', distribution, 9000.0, 0.0),
            ('Additional Basic Salary', distribution, 0.0, 4500.0),
            ('Additional Basic Salary', distribution, 4500.0, 0.0),
        ]
        real_result = [(line.name, line.analytic_distribution, line.credit, line.debit) for line in payrun.move_id.line_ids]
        self.assertEqual(real_result, expected_result)

    def test_non_batch_move_lines_index_non_mergeable_lines(self):
        """A line that cannot merge with preceding lines can still be the
        merge target of a later salary rule.
        """
        self.company.batch_payroll_move_lines = False
        first_rule, second_rule = self.nordic_warrior_structure.rule_ids.sorted('sequence')
        distribution = {str(self.aa_1.id): 100}
        first_rule.write({
            'name': 'Salary',
            'account_debit': self.debit_account_full.id,
            'account_credit': self.credit_account_full.id,
            'analytic_distribution': distribution,
            'employee_move_line': True,
        })
        second_rule.write({
            'name': 'Salary',
            'account_debit': self.debit_account_full.id,
            'account_credit': self.credit_account_full.id,
            'analytic_distribution': distribution,
            'employee_move_line': False,
        })

        payrun = self.env['hr.payslip.run'].create({
            'name': 'Test Payrun Non-Batch Move Lines',
            'date_start': date(2026, 3, 1),
            'date_end': date(2026, 3, 31),
            'structure_id': self.nordic_warrior_structure.id,
        })
        payrun._generate_payslips()
        payrun.action_validate()

        moves = payrun.slip_ids.move_id
        self.assertEqual(len(moves), 3)
        expected_result = [
            ('Salary', 0.0, 4500.0),
            ('Salary', 4500.0, 0.0),
        ]
        for move in moves:
            real_result = [
                (line.name, line.credit, line.debit)
                for line in move.line_ids
            ]
            self.assertEqual(real_result, expected_result)

    def test_batch_move_lines_keeps_distinct_tax_tags(self):
        self.company.batch_payroll_move_lines = True
        first_tag, second_tag = self.env['account.account.tag'].create([
            {'name': 'First Payroll Tag', 'applicability': 'taxes'},
            {'name': 'Second Payroll Tag', 'applicability': 'taxes'},
        ])
        first_rule, second_rule = self.nordic_warrior_structure.rule_ids.sorted('sequence')
        distribution = {str(self.aa_1.id): 100}
        first_rule.write({
            'name': 'Salary',
            'account_debit': self.debit_account_full.id,
            'account_credit': self.credit_account_full.id,
            'analytic_distribution': distribution,
            'debit_tag_ids': [Command.set(first_tag.ids)],
            'credit_tag_ids': [Command.set(first_tag.ids)],
        })
        second_rule.write({
            'name': 'Salary',
            'account_debit': self.debit_account_full.id,
            'account_credit': self.credit_account_full.id,
            'analytic_distribution': distribution,
            'debit_tag_ids': [Command.set(second_tag.ids)],
            'credit_tag_ids': [Command.set(second_tag.ids)],
        })

        payrun = self.env['hr.payslip.run'].create({
            'name': 'Test Payrun Distinct Tax Tags',
            'date_start': date(2026, 3, 1),
            'date_end': date(2026, 3, 31),
            'structure_id': self.nordic_warrior_structure.id,
        })
        payrun._generate_payslips()
        payrun.action_validate()

        expected_result = [
            ('Salary', first_tag, 0.0, 9000.0),
            ('Salary', first_tag, 9000.0, 0.0),
            ('Salary', second_tag, 0.0, 4500.0),
            ('Salary', second_tag, 4500.0, 0.0),
        ]
        real_result = [
            (line.name, line.tax_tag_ids, line.credit, line.debit)
            for line in payrun.move_id.line_ids
        ]
        self.assertEqual(real_result, expected_result)

    def test_validate_payrun_with_anonymized_journal_entries(self):
        """
        Checks that when we validate a payslip and the option 'Anonymize journal entries' has been set, narration on the
        journal entry stays empty.
        """
        self.company.batch_payroll_move_lines = True

        payrun = self.env['hr.payslip.run'].create({
            'name': 'Test Payrun Distinct Distributions',
            'date_start': date(2026, 3, 1),
            'date_end': date(2026, 3, 31),
            'structure_id': self.nordic_warrior_structure.id,
        })
        payrun._generate_payslips()
        payrun.action_validate()
        self.assertTrue(is_html_empty(payrun.slip_ids.move_id.narration))
