# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import TestPayslipBase


@tagged('-at_install', 'post_install')
class TestSalaryIncreaseWizard(TestPayslipBase):

    def _create_wizard(self, employees, increase_date, rate=0.0, extra=0.0, applied_on='full', capped_wage=0.0):
        return self.env['hr.payroll.salary.increase'].create({
            'employee_ids': employees.ids,
            'increase_date': increase_date,
            'increase_rate': rate,
            'extra_amount': extra,
            'applied_on': applied_on,
            'capped_wage': capped_wage,
        })

    def _validated_payslip(self, employee, date_from, date_to):
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'struct_id': self.developer_pay_structure.id,
            'version_id': employee._get_version(date=date_from).id,
            'date_from': date_from,
            'date_to': date_to,
        })
        payslip.action_validate()
        return payslip

    def test_validation_negative_rate(self):
        wizard = self._create_wizard(self.richard_emp, date.today() + relativedelta(days=30), rate=-0.1)
        with self.assertRaises(UserError):
            wizard.action_confirm()

    def test_validation_negative_amount(self):
        wizard = self._create_wizard(self.richard_emp, date.today() + relativedelta(days=30), extra=-100.0)
        with self.assertRaises(UserError):
            wizard.action_confirm()

    def test_validation_neither_rate_nor_amount(self):
        wizard = self._create_wizard(self.richard_emp, date.today() + relativedelta(days=30))
        with self.assertRaises(UserError):
            wizard.action_confirm()

    def test_validation_no_version_before_increase_date(self):
        wizard = self._create_wizard(self.richard_emp, date(2000, 1, 1), rate=0.1)
        with self.assertRaises(ValidationError):
            wizard.action_confirm()

    def test_increase_by_rate(self):
        future_date = date.today() + relativedelta(months=1, day=1)
        self._create_wizard(self.richard_emp, future_date, rate=0.1).action_confirm()

        new_version = self.richard_emp._get_version(date=future_date)
        wage_field = new_version._get_contract_wage_field()
        self.assertAlmostEqual(new_version[wage_field], 5000.33 * 1.1, places=2)

    def test_increase_by_extra_amount(self):
        future_date = date.today() + relativedelta(months=1, day=1)
        self._create_wizard(self.richard_emp, future_date, extra=500.0).action_confirm()

        new_version = self.richard_emp._get_version(date=future_date)
        wage_field = new_version._get_contract_wage_field()
        self.assertAlmostEqual(new_version[wage_field], 5000.33 + 500.0, places=2)

    def test_increase_capped_wage(self):
        # wage = 5000.33, cap = 4000, rate = 10%
        # new wage = 5000.33 + 4000 * 0.1
        future_date = date.today() + relativedelta(months=1, day=1)
        self._create_wizard(
            self.richard_emp, future_date,
            rate=0.1, applied_on='capped', capped_wage=4000.0,
        ).action_confirm()

        new_version = self.richard_emp._get_version(date=future_date)
        wage_field = new_version._get_contract_wage_field()
        self.assertAlmostEqual(new_version[wage_field], 5000.33 + 4000.0 * 0.1, places=2)

    def test_new_version_created_on_increase_date(self):
        future_date = date.today() + relativedelta(months=1, day=1)
        version_count_before = len(self.richard_emp.version_ids)
        self._create_wizard(self.richard_emp, future_date, rate=0.1).action_confirm()

        self.assertEqual(len(self.richard_emp.version_ids), version_count_before + 1)
        self.assertEqual(self.richard_emp._get_version(date=future_date).date_version, future_date)

    def test_no_new_version_if_date_matches_existing(self):
        future_date = date.today() + relativedelta(months=1, day=1)
        self.richard_emp.create_version({'date_version': future_date})
        version_count_before = len(self.richard_emp.version_ids)

        self._create_wizard(self.richard_emp, future_date, rate=0.1).action_confirm()

        self.assertEqual(len(self.richard_emp.version_ids), version_count_before)

    def test_future_affected_versions_updated(self):
        increase_date = date.today() + relativedelta(months=1, day=1)
        later_date = date.today() + relativedelta(months=3, day=1)
        later_version = self.richard_emp.create_version({'date_version': later_date})
        wage_field = later_version._get_contract_wage_field()
        wage_before = later_version[wage_field]

        self._create_wizard(self.richard_emp, increase_date, rate=0.1).action_confirm()

        self.assertAlmostEqual(later_version[wage_field], wage_before * 1.1, places=2)

    def test_past_increase_detects_affected_payslips(self):
        increase_date = date.today() - relativedelta(months=3, day=1)
        payslip_date = increase_date + relativedelta(months=1)
        payslip = self._validated_payslip(
            self.richard_emp, payslip_date, payslip_date + relativedelta(months=1, days=-1),
        )

        wizard = self._create_wizard(self.richard_emp, increase_date, rate=0.1)
        action = wizard.action_confirm()

        self.assertEqual(action['res_model'], 'hr.payslip.correction.wizard')
        correction_wizard = self.env['hr.payslip.correction.wizard'].browse(action['res_id'])
        self.assertIn(payslip, correction_wizard.payslip_ids)

    def test_past_increase_payslips_before_increase_date_not_affected(self):
        increase_date = date.today() - relativedelta(months=2, day=1)
        before_date = increase_date - relativedelta(months=1)
        payslip_before = self._validated_payslip(
            self.richard_emp, before_date, before_date + relativedelta(months=1, days=-1),
        )

        wizard = self._create_wizard(self.richard_emp, increase_date, rate=0.1)
        wizard.action_confirm()

        self.assertNotIn(payslip_before, wizard.affected_payslip_ids)

    def test_past_increase_future_version_payslips_affected(self):
        increase_date = date.today() - relativedelta(months=4, day=1)
        later_version_date = date.today() - relativedelta(months=2, day=1)
        later_version = self.richard_emp.create_version({'date_version': later_version_date})

        payslip = self._validated_payslip(
            self.richard_emp, later_version_date, later_version_date + relativedelta(months=1, days=-1),
        )
        payslip.version_id = later_version

        wizard = self._create_wizard(self.richard_emp, increase_date, rate=0.1)
        wizard.action_confirm()

        self.assertIn(payslip, wizard.affected_payslip_ids)
