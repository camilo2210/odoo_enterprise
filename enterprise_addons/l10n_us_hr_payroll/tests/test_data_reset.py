# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import SUPERUSER_ID, Command
from odoo.exceptions import UserError
from odoo.tests import tagged, TransactionCase


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestDataReset(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.rule = cls.env.ref('l10n_us_hr_payroll.l10n_us_hr_payroll_structure_us_employee_salary_basic_salary_rule')
        cls.parameter = cls.env.ref('l10n_us_hr_payroll.rule_parameter_il_income_tax_rate')
        cls.value = cls.env.ref('l10n_us_hr_payroll.rule_parameter_il_income_tax_rate_2025')

        cls.env.company.country_id = cls.env.ref('base.us')
        cls.payroll_manager = cls.env['res.users'].create({
            'name': 'Payroll Manager',
            'login': 'payroll_manager',
            'group_ids': [(6, 0, [cls.env.ref('hr_payroll.group_hr_payroll_manager').id])]
        })

    def test_rule_modified_by_superuser(self):
        """
        When a rule is modified by the superuser (system), it is not considered as modified by the user.
        The update payroll data cron should override the record with the data from the files.
        """
        self.assertFalse(self.rule.modified_by_user)
        self.rule.with_user(SUPERUSER_ID).amount_python_compute = 'test'
        self.assertFalse(self.rule.modified_by_user)

        # The cron should reset the data
        self.env['hr.payslip']._update_payroll_data(country_code="US")
        self.assertFalse(self.rule.modified_by_user)
        self.assertNotEqual(self.rule.amount_python_compute, 'test')

    def test_rule_modified_by_payroll_manager(self):
        """
        When a rule is modified by a payroll manager, it is considered as modified by the user.
        Until the user chooses to reset the rule manually,
        the update payroll data cron should NOT override the record with the data from the files.
        Resetting the rule should override the record with the data from the files.
        """
        self.assertFalse(self.rule.modified_by_user)
        self.rule.with_user(self.payroll_manager).amount_python_compute = 'test'
        self.assertTrue(self.rule.modified_by_user)

        # The cron should not reset the data
        self.env['hr.payslip']._update_payroll_data(country_code="US")
        self.assertTrue(self.rule.modified_by_user)
        self.assertEqual(self.rule.amount_python_compute, 'test')

    def test_rule_modified_by_payroll_manager_not_critical(self):
        """
        If the rule is modified on a non-critical field, it should not be considered as modified by the user.
        """
        self.assertFalse(self.rule.modified_by_user)
        self.rule.with_user(self.payroll_manager).bold = True
        self.assertFalse(self.rule.modified_by_user)

        # The cron should not reset non-critical data
        self.env['hr.payslip']._update_payroll_data(country_code="US")
        self.assertFalse(self.rule.modified_by_user)
        self.assertTrue(self.rule.bold)

    def test_system_rule_deleted_by_payroll_manager(self):
        """
        The payroll manager should not be able to delete a rule created by the system.
        """
        with self.assertRaises(UserError):
            self.rule.with_user(self.payroll_manager).unlink()

    def test_user_rule_deleted_by_payroll_manager(self):
        """
        The payroll manager should be able to delete a rule created by a user.
        """
        user_rule = self.rule.with_user(self.payroll_manager).copy()
        self.assertTrue(user_rule.created_by_user)
        user_rule.with_user(self.payroll_manager).unlink()
        self.assertFalse(user_rule.exists())

    def test_parameter_modified_by_superuser(self):
        """
        When a parameter is modified by the superuser (system), it is not considered as modified by the user.
        The update payroll data cron should override the record with the data from the files.
        """
        self.assertFalse(self.parameter.modified_by_user)
        self.parameter.with_user(SUPERUSER_ID).code = 'test'
        self.assertFalse(self.parameter.modified_by_user)

        # The cron should reset the data
        self.env['hr.payslip']._update_payroll_data(country_code="US")
        self.assertFalse(self.parameter.modified_by_user)
        self.assertNotEqual(self.parameter.code, 'test')

    def test_parameter_modified_by_payroll_manager(self):
        """
        When a parameter is modified by a payroll manager, it is considered as modified by the user.
        Until the user chooses to reset the parameter manually,
        the update payroll data cron should NOT override the record with the data from the files.
        Resetting the parameter should override the record with the data from the files.
        """
        self.assertFalse(self.parameter.modified_by_user)
        self.parameter.with_user(self.payroll_manager).code = 'test'
        self.assertTrue(self.parameter.modified_by_user)

        # The cron should not reset the data
        self.env['hr.payslip']._update_payroll_data(country_code="US")
        self.assertTrue(self.parameter.modified_by_user)
        self.assertEqual(self.parameter.code, 'test')

        # Manual reset should reset the data
        self.parameter.with_user(self.payroll_manager).action_reset_rule_parameter()
        self.assertFalse(self.parameter.modified_by_user)
        self.assertNotEqual(self.parameter.code, 'test')

    def test_system_parameter_deleted_by_payroll_manager(self):
        """
        The payroll manager should not be able to delete a parameter created by the system.
        """
        with self.assertRaises(UserError):
            self.parameter.with_user(self.payroll_manager).unlink()

    def test_user_parameter_deleted_by_payroll_manager(self):
        """
        The payroll manager should be able to delete a parameter created by a user.
        """
        user_parameter = self.parameter.with_user(self.payroll_manager).copy()
        self.assertTrue(user_parameter.created_by_user)
        user_parameter.with_user(self.payroll_manager).unlink()
        self.assertFalse(user_parameter.exists())

    def test_parameter_value_modified_by_superuser(self):
        """
        When a parameter value is modified by the superuser (system),
        the parameter is not considered as modified by the user.
        The update payroll data cron should override the parameter and values with the data from the files.
        """
        self.assertFalse(self.parameter.modified_by_user)
        self.parameter.with_user(SUPERUSER_ID).write(
            {'parameter_version_ids': [[Command.UPDATE, self.value.id, {'parameter_value': '-1'}]]})
        self.assertFalse(self.parameter.modified_by_user)
        self.assertEqual(self.value.parameter_value, '-1')

        # The cron should reset the data
        self.env['hr.payslip']._update_payroll_data(country_code="US")
        self.assertFalse(self.parameter.modified_by_user)
        self.assertNotEqual(self.value.parameter_value, '-1')

    def test_parameter_value_modified_by_payroll_manager(self):
        """
        When a parameter value is modified by a payroll manager, the parameter is considered as modified by the user.
        Until the user chooses to reset the parameter manually,
        the update payroll data cron should NOT override the parameter and values with the data from the files.
        Resetting the parameter should override the parameter and values with the data from the files.
        """
        self.assertFalse(self.parameter.modified_by_user)
        self.parameter.with_user(self.payroll_manager).write(
            {'parameter_version_ids': [[Command.UPDATE, self.value.id, {'parameter_value': '-1'}]]})
        self.assertTrue(self.parameter.modified_by_user)
        self.assertEqual(self.value.parameter_value, '-1')

        # The cron should not reset the data
        self.env['hr.payslip']._update_payroll_data(country_code="US")
        self.assertTrue(self.parameter.modified_by_user)
        self.assertEqual(self.value.parameter_value, '-1')

        # Manual reset should reset the data
        self.parameter.with_user(self.payroll_manager).action_reset_rule_parameter()
        self.assertFalse(self.parameter.modified_by_user)
        self.assertNotEqual(self.value.parameter_value, '-1')

    def test_system_parameter_value_deleted_by_payroll_manager(self):
        """
        The payroll manager should not be able to delete a parameter value created by the system.
        """
        with self.assertRaises(UserError):
            self.value.with_user(self.payroll_manager).unlink()

    def test_user_parameter_value_deleted_by_payroll_manager(self):
        """
        The payroll manager should be able to delete a parameter value created by a user.
        """
        user_value = self.value.with_user(self.payroll_manager).copy({
            'date_from': '0001-01-01',
        })
        user_value.with_user(self.payroll_manager).unlink()
        self.assertFalse(user_value.exists())
