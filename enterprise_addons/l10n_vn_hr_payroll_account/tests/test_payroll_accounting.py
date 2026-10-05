# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.fields import Command
from odoo.tests import tagged

from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestL10nVnPayrollAccounting(TestPayslipValidationCommon):

    @classmethod
    @TestPayslipValidationCommon.setup_country('vn')
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_common(
            country=cls.env.ref('base.vn'),
            structure=cls.env.ref('l10n_vn_hr_payroll.hr_payroll_structure_vn_employee_salary'),
            structure_type=cls.env.ref('l10n_vn_hr_payroll.structure_type_employee_vn'),
            version_fields={
                'date_version': date(2025, 1, 1),
                'contract_date_start': date(2025, 1, 1),
                'wage': 30_000_000.0,
                'l10n_vn_dependants': 1,
                'l10n_vn_union_member': True,
            },
            tz='Asia/Ho_Chi_Minh',
        )

    def _amounts_by_account(self, move):
        amounts = {}
        for line in move.line_ids:
            debit, credit = amounts.get(line.account_id.code, (0.0, 0.0))
            amounts[line.account_id.code] = (debit + line.debit, credit + line.credit)
        return amounts

    def test_payroll_accounts_configuration(self):
        # The chart template loading configured the salary journal and the accounts of the rules.
        # The Vietnamese chart pads the account codes to four digits: 334 is stored as 3340.
        rule = self.env.ref
        self.assertEqual(self.structure.journal_id.code, 'SLR')
        self.assertEqual(self.structure.journal_id.default_account_id.code, '6421')
        self.assertEqual(rule('l10n_vn_hr_payroll.l10n_vn_rule_basic').account_debit.code, '6421')
        self.assertEqual(rule('l10n_vn_hr_payroll.l10n_vn_rule_net').account_credit.code, '3340')
        self.assertTrue(rule('l10n_vn_hr_payroll.l10n_vn_rule_net').employee_move_line)
        self.assertEqual(rule('l10n_vn_hr_payroll.l10n_vn_rule_social_insurance_employee').account_debit.code, '3383')
        self.assertEqual(rule('l10n_vn_hr_payroll.l10n_vn_rule_personal_income_tax').account_debit.code, '3335')
        employer = rule('l10n_vn_hr_payroll.l10n_vn_rule_social_insurance_retirement_employer')
        self.assertEqual((employer.account_debit.code, employer.account_credit.code), ('6421', '3383'))

    def test_payslip_journal_entry(self):
        # 30m wage and 2m position allowance in March 2026 (contribution wage 32m), union member, one dependant:
        #   staff costs   6421  32,000,000 + employer 17.5% + 3% + 1% + union fund 2% of 32m = 39,520,000
        #   SI            3383  8% + 17.5% of 32m = 8,160,000
        #   HI            3384  1.5% + 3% of 32m = 1,440,000
        #   UI            3386  1% + 1% of 32m = 640,000
        #   union fees    3382  dues capped at 234,000 + fund 640,000 = 874,000
        #   PIT           3335  5% of (32m - 3.36m - 15.5m - 6.2m) = 347,000
        #   employees     3340  net 32,000,000 - 3,360,000 - 234,000 - 347,000 = 28,059,000
        position_allowance = self.env.ref('l10n_vn_hr_payroll.l10n_vn_rule_position_allowance')
        payslip = self._generate_payslip(
            date(2026, 3, 1), date(2026, 3, 31),
            input_line_ids=[Command.create({'salary_rule_id': position_allowance.id, 'amount': 2_000_000})],
        )
        self._validate_payslip(payslip, {
            'BASIC': 30_000_000,
            'POSITION_ALW': 2_000_000,
            'SI_EMP': -2_560_000,
            'HI_EMP': -480_000,
            'UI_EMP': -320_000,
            'UNION_DUES': -234_000,
            'PIT': -347_000,
            'NET': 28_059_000,
        }, skip_lines=True)

        payslip.action_payslip_done()

        move = payslip.move_id
        self.assertTrue(move, "The validated payslip must generate a journal entry")
        self.assertEqual(move.journal_id, self.structure.journal_id)
        self.assertEqual(move.date, date(2026, 3, 31))
        self.assertEqual(self._amounts_by_account(move), {
            '6421': (39_520_000.0, 0.0),
            '3383': (0.0, 8_160_000.0),
            '3384': (0.0, 1_440_000.0),
            '3386': (0.0, 640_000.0),
            '3382': (0.0, 874_000.0),
            '3335': (0.0, 347_000.0),
            '3340': (0.0, 28_059_000.0),
        })
        self.assertFalse(move.line_ids.filtered(lambda line: line.name == 'Adjustment Entry'),
                         "Every payslip line reaching the net must have its accounts")
        net_line = move.line_ids.filtered(lambda line: line.account_id.code == '3340')
        self.assertEqual(net_line.partner_id, self.employee.work_contact_id)

    def test_deductions_and_advanced_benefits_journal_entry(self):
        # A recovered advance and a social insurance benefit advanced by the employer
        rule = self.env.ref
        payslip = self._generate_payslip(
            date(2026, 3, 1), date(2026, 3, 31),
            input_line_ids=[
                Command.create({'salary_rule_id': rule('l10n_vn_hr_payroll.l10n_vn_rule_advance_recovery').id, 'amount': 1_000_000}),
                Command.create({'salary_rule_id': rule('l10n_vn_hr_payroll.l10n_vn_rule_si_benefit_advance').id, 'amount': 3_000_000}),
            ],
        )
        payslip.action_payslip_done()
        amounts = self._amounts_by_account(payslip.move_id)
        self.assertEqual(amounts['1410'], (0.0, 1_000_000.0), "The recovered advance is credited to the advances account")
        # 8% + 17.5% of 30m credited, the 3m benefit advanced on behalf of the fund debited
        self.assertEqual(amounts['3383'], (3_000_000.0, 7_650_000.0))
        # net: 30m - 3.15m insurance - 234,000 dues - 5% x (30m - 3.15m - 21.7m) tax - 1m advance + 3m benefit
        self.assertEqual(amounts['3340'], (0.0, 28_358_500.0))
        self.assertEqual(sum(payslip.move_id.line_ids.mapped('debit')), sum(payslip.move_id.line_ids.mapped('credit')))
