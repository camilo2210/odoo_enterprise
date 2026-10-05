# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from freezegun import freeze_time

from odoo.tests import tagged
from odoo.addons.l10n_be_hr_payroll.tests.common import TestPayrollCommon


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestPayrollTransportExemption(TestPayrollCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with freeze_time('2026-01-20'):
            cls.transport_employee = cls.create_employee({
                'name': 'Transport Employee',
                'date_version': date(2025, 1, 1),
                'contract_date_start': date(2025, 1, 1),
                'contract_date_end': False,
                'fuel_card': 0.0,
            })
            cls.transport_employee.version_id.generate_work_entries(date(2026, 1, 1), date(2026, 1, 31))

    def _compute_january_payslip(self):
        payslip = self.env['hr.payslip'].create({
            'name': 'Transport Payslip January 2026',
            'employee_id': self.transport_employee.id,
            'company_id': self.belgian_company.id,
            'version_id': self.transport_employee.version_id.id,
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 1, 31),
        })
        payslip.compute_sheet()
        return payslip

    def _get_line(self, payslip, code):
        return payslip.line_ids.filtered(lambda l: l.code == code)

    def test_no_transport_no_deduction(self):
        with freeze_time('2026-01-20'):
            payslip = self._compute_january_payslip()
        self.assertFalse(self._get_line(payslip, 'CAR.PRIV').total)
        self.assertFalse(self._get_line(payslip, 'CYCLE.TAX').total)
        self.assertFalse(self._get_line(payslip, 'TRANSPORT_TAX_DED').total,
            "Without any taxable transportation amount, no exemption may be granted")

    def test_private_car_added_to_withholding_base(self):
        with freeze_time('2026-01-20'):
            baseline = self._compute_january_payslip()
            gross_without = self._get_line(baseline, 'GROSS').total

            self.transport_employee.version_id.write({
                'private_car_employee_kilometer': 25,
            })
            payslip = self._compute_january_payslip()

        car_priv = self._get_line(payslip, 'CAR.PRIV')
        self.assertTrue(car_priv.total, "The private car reimbursement should be paid")
        self.assertAlmostEqual(self._get_line(payslip, 'GROSS').total, gross_without + car_priv.total, 2,
            "The reimbursement should be added to the withholding tax base")
        expected_deduction = -min(500, 12 * car_priv.total)
        self.assertAlmostEqual(self._get_line(payslip, 'TRANSPORT_TAX_DED').total, expected_deduction, 2)

    def test_private_car_fully_exempt_does_not_increase_withholding(self):
        # A private-car reimbursement fully below the yearly exemption cap is added to the
        # taxable base and cancelled by TRANSPORT_TAX_DED, so it must not change the withholding
        # tax. Regression: the reimbursement used to be counted a second time in the bareme,
        # over-taxing an amount that is entirely exempt.
        with freeze_time('2026-01-20'):
            baseline = self._compute_january_payslip()
            pp_without = self._get_line(baseline, 'P.P').total
            net_without = self._get_line(baseline, 'NET').total

            self.transport_employee.version_id.write({'private_car_employee_kilometer': 10})
            payslip = self._compute_january_payslip()

        car_priv = self._get_line(payslip, 'CAR.PRIV').total
        deduction = self._get_line(payslip, 'TRANSPORT_TAX_DED').total
        self.assertTrue(car_priv, "The private car reimbursement should be taxable")
        self.assertAlmostEqual(deduction, -12 * car_priv, 2,
            "Premise: the reimbursement is fully below the yearly exemption cap")
        self.assertAlmostEqual(self._get_line(payslip, 'P.P').total, pp_without, 2,
            "A fully-exempt transport reimbursement must not change the withholding tax")
        self.assertAlmostEqual(self._get_line(payslip, 'NET').total, net_without + car_priv, 2,
            "The reimbursement is still fully paid to the employee")

    def test_fuel_card_commute_deduction(self):
        with freeze_time('2026-01-20'):
            payslip = self._compute_january_payslip()
            payslip._set_input_value('FUEL_CARD_COMMUTE', 30.0)
            payslip.compute_sheet()
        self.assertAlmostEqual(self._get_line(payslip, 'FUEL_CARD_COMMUTE').total, 30.0, 2)
        # min(500 (2026 threshold), 12 x 30 = 360) = 360
        self.assertAlmostEqual(self._get_line(payslip, 'TRANSPORT_TAX_DED').total, -360.0, 2)

    def test_cycle_reimbursement_within_exempt_rate(self):
        self.transport_employee.version_id.write({
            'bike_transport_employee_kilometer': 5,
        })
        with freeze_time('2026-01-20'):
            payslip = self._compute_january_payslip()
        self.assertTrue(self._get_line(payslip, 'CYCLE').total, "The bike reimbursement should be paid")
        self.assertFalse(self._get_line(payslip, 'CYCLE.TAX').total,
            "A bike allowance at or below the exempt rate per km is fully exempted")
        self.assertFalse(self._get_line(payslip, 'TRANSPORT_TAX_DED').total)

    def test_cycle_reimbursement_above_exempt_rate(self):
        self.env['hr.rule.parameter.value'].create({
            'parameter_value': '0.45',
            'rule_parameter_id': self.env.ref('l10n_be_hr_payroll.rule_parameter_cp200_cycle_reimbursement_per_km').id,
            'date_from': date(2026, 1, 1),
        })
        self.transport_employee.version_id.write({
            'bike_transport_employee_kilometer': 5,
        })
        with freeze_time('2026-01-20'):
            payslip = self._compute_january_payslip()
        cycle = self._get_line(payslip, 'CYCLE')
        cycle_tax = self._get_line(payslip, 'CYCLE.TAX')
        # paid: 0.45 x 5 km x 2 = 4.5/day, exempt: 0.37 x 5 km x 2 = 3.7/day
        self.assertAlmostEqual(cycle_tax.amount, 0.8, 2,
            "Only the 0.08/km above the exempt rate is taxable")
        self.assertAlmostEqual(cycle.amount, 3.7, 2)
        self.assertAlmostEqual(cycle.total + cycle_tax.total, 4.5 * cycle.quantity, 2,
            "The two lines together still pay the whole reimbursement")
        self.assertTrue(cycle_tax.total)
        expected_deduction = -min(500, 12 * cycle_tax.total)
        self.assertAlmostEqual(self._get_line(payslip, 'TRANSPORT_TAX_DED').total, expected_deduction, 2)
