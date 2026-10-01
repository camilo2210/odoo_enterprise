# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from freezegun import freeze_time

from odoo.tests import tagged
from odoo.tools import format_amount

from odoo.addons.l10n_be_hr_payroll.models.hr_version import BIK_RULE_PARAMETERS

from .common import TestPayrollCommon


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestPayrollBIK(TestPayrollCommon):

    def _assert_number_bik_lines(self, slip, expected_amount):
        bik_lines = slip.line_ids.filtered(lambda l: l.name and 'benefit in kind' in l.name.lower() and not 'car' in l.name.lower())
        self.assertEqual(len(bik_lines), expected_amount, f"Expected {expected_amount} payslip lines for BIK, but got:\n"
            + "\n".join(f"{l.code} | {l.name} | total={l.total}" for l in bik_lines))

    def _check_bik_line_in_payslip(self, payslip, code_rule, code_parameter):
        line = payslip.line_ids.filtered(lambda l: l.code == code_rule)
        self.assertTrue(line)
        parameter_value = self.env['hr.rule.parameter']._get_parameter_from_code(code_parameter, payslip.date_to)
        self.assertEqual(parameter_value, line[0].total)

    def test_bik_amount_in_field_help(self):
        # The version stores the real cost of the benefit for the employer, while
        # the amount taxed on the employee is a flat monthly amount coming from a
        # rule parameter: it is appended to the tooltip of those fields.
        with freeze_time('2026-01-20'):
            for model in ('hr.version', 'hr.employee'):
                for field_name, parameter_code in BIK_RULE_PARAMETERS.items():
                    with self.subTest(model=model, field_name=field_name):
                        field_help = self.env[model].fields_get([field_name], ['help'])[field_name]['help']
                        description, _separator, benefit_in_kind = field_help.partition('\n')
                        self.assertTrue(description, "The original description should be kept")
                        amount = self.env['hr.rule.parameter']._get_parameter_from_code(parameter_code)
                        self.assertIn(
                            format_amount(self.env, amount, self.env.ref('base.EUR')),
                            benefit_in_kind,
                            "The taxed benefit in kind should be appended to the description")

    def test_bik_lines_in_payslip(self):
        with freeze_time('2026-01-20'):
            date_from = date(2026, 1, 1)
            date_to = date(2026, 1, 31)

            employee = self.create_employee({
                'name': 'BIK-check employee',
                'date_version': date(2025, 1, 1),
                'contract_date_start': date(2025, 1, 1),
                'contract_date_end': False,
                'mobile': 0.0,
                'internet': 0.0,
                'laptop': 0.0,
                'tablet': 0.0,
                'mobile_amount': 0.0,
                'electricity_amount': 0.0,
                'heating_amount': 0.0,
                'housing_onss_amount': 0.0,
                'housing_fiscal_amount': 0.0,
                'rent_amount': 0.0,
                'pension_amount': 0.0,
            })
            version = employee.version_id
            self.assertFalse(version.mobile, "Expected version.mobile to be falsy at start")
            self.assertFalse(version.internet, "Expected version.internet to be falsy at start")
            self.assertFalse(version.laptop, "Expected version.laptop to be falsy at start")
            self.assertFalse(version.tablet, "Expected version.tablet to be falsy at start")
            self.assertFalse(version.mobile_amount, "Expected version.mobile_amount to be falsy at start")

            slip = self.env['hr.payslip'].create({
                'employee_id': employee.id,
                'company_id': employee.company_id.id,
                'version_id': version.id,
                'date_from': date_from,
                'date_to': date_to,
            })
            slip.compute_sheet()
            employer_cost_0 = slip.employer_cost
            self._assert_number_bik_lines(slip, 0)

            employee.write({'laptop': 100.0})
            self._assert_number_bik_lines(slip, 1)
            self._check_bik_line_in_payslip(slip, 'ATN.LAP', 'bik_laptop_amount')
            employer_cost_1 = slip.employer_cost
            self.assertNotEqual(employer_cost_1, employer_cost_0, "Employer cost haven't changed")

            employee.write({'internet': 40.0})
            self._assert_number_bik_lines(slip, 2)
            self._check_bik_line_in_payslip(slip, 'ATN.INT', 'bik_internet_amount')
            employer_cost_2 = slip.employer_cost
            self.assertNotEqual(employer_cost_2, employer_cost_1, "Employer cost haven't changed")

            employee.write({'mobile': 20.0})
            self._assert_number_bik_lines(slip, 3)
            self._check_bik_line_in_payslip(slip, 'ATN.MOB', 'bik_phone_sub_amount')
            employer_cost_3 = slip.employer_cost
            self.assertNotEqual(employer_cost_3, employer_cost_2, "Employer cost haven't changed")

            employee.write({'mobile_amount': 50.0})
            self._assert_number_bik_lines(slip, 4)
            self._check_bik_line_in_payslip(slip, 'ATN.PHONE_AMT', 'bik_phone_amount')
            employer_cost_4 = slip.employer_cost
            self.assertNotEqual(employer_cost_4, employer_cost_3, "Employer cost haven't changed")

            employee.write({'tablet': 100.0})
            self._assert_number_bik_lines(slip, 5)
            self._check_bik_line_in_payslip(slip, 'ATN.TAB', 'bik_tablet_amount')
            employer_cost_5 = slip.employer_cost
            self.assertNotEqual(employer_cost_5, employer_cost_4, "Employer cost haven't changed")

            employee.write({'electricity_amount': 120.0})
            slip.compute_sheet()
            self._assert_number_bik_lines(slip, 6)
            line_elec = slip.line_ids.filtered(lambda l: l.code == 'ATN_ELEC')
            self.assertTrue(line_elec)
            self.assertEqual(line_elec['total'], 120.0)
            employer_cost_6 = slip.employer_cost
            self.assertNotEqual(employer_cost_6, employer_cost_5, "Employer cost haven't changed")

            employee.write({'heating_amount': 85.0})
            slip.compute_sheet()
            self._assert_number_bik_lines(slip, 7)
            line_heating = slip.line_ids.filtered(lambda l: l.code == 'ATN_HEATING')
            self.assertTrue(line_heating)
            self.assertEqual(line_heating['total'], 85.0)
            employer_cost_7 = slip.employer_cost
            self.assertNotEqual(employer_cost_7, employer_cost_6, "Employer cost haven't changed")

            # the housing benefit has one value for the social contributions and one for the taxes
            employee.write({'housing_onss_amount': 600.0, 'housing_fiscal_amount': 350.0})
            slip.compute_sheet()
            self._assert_number_bik_lines(slip, 11)
            line_housing_onss = slip.line_ids.filtered(lambda l: l.code == 'ATN_HOUSING_ONSS')
            self.assertTrue(line_housing_onss)
            self.assertEqual(line_housing_onss['total'], 600.0)
            line_housing_fiscal = slip.line_ids.filtered(lambda l: l.code == 'ATN_HOUSING_FISCAL')
            self.assertTrue(line_housing_fiscal)
            self.assertEqual(line_housing_fiscal['total'], 350.0)
            employer_cost_8 = slip.employer_cost
            self.assertNotEqual(employer_cost_8, employer_cost_7, "Employer cost haven't changed")

            version.write({'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_999').id})
            slip.compute_sheet()
            employer_cost_baseline_cp999 = slip.employer_cost

            employee.write({'rent_amount': 450.0})
            slip.compute_sheet()
            self._assert_number_bik_lines(slip, 12)
            line_rent = slip.line_ids.filtered(lambda l: l.code == 'ATN_RENT')
            self.assertTrue(line_rent)
            self.assertEqual(line_rent.total, 450.0)
            self.assertEqual(slip.employer_cost, employer_cost_baseline_cp999, "Employer cost should not change for CP999")

            employee.write({'pension_amount': 150.0})
            slip.compute_sheet()
            self._assert_number_bik_lines(slip, 13)
            line_pension = slip.line_ids.filtered(lambda l: l.code == 'ATN_PENSION')
            self.assertTrue(line_pension)
            self.assertEqual(line_pension.total, 150.0)
            self.assertEqual(slip.employer_cost, employer_cost_baseline_cp999, "Employer cost should not change for CP999")

            slip._set_input_value('ATN_MISC', 20)
            slip.compute_sheet()

            line1 = slip.line_ids.filtered(lambda l: l.code == 'ATN_MISC')
            self.assertTrue(line1)
            self.assertEqual(line1[0]['total'], 20)
