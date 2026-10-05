# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from dateutil.relativedelta import relativedelta

from odoo.tests import tagged
from odoo.addons.l10n_be_hr_payroll.tests.common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestScientificResearchExemption(TestPayrollCommon):

    @classmethod
    def _create_274xx_sheet(cls, profiles, period_start):
        """ Create payslips for researcher profiles and return a 274.XX sheet for that month. """
        period_end = period_start + relativedelta(day=31)
        struct = cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary')
        slip_vals = []
        for i, (cert, wage, rd) in enumerate(profiles, 1):
            emp = cls.create_employee({
                'name': f'R{i}', 'certificate': cert, 'wage': wage,
                'date_version': period_start, 'contract_date_start': period_start, 'contract_date_end': False,
            })
            emp.version_id.write({'rd_percentage': rd})
            emp.version_id.generate_work_entries(period_start, period_end)
            slip_vals.append({
                'name': f'R{i}', 'employee_id': emp.id, 'struct_id': struct.id,
                'version_id': emp.version_id.id, 'date_from': period_start, 'date_to': period_end,
            })
        slips = cls.env['hr.payslip'].create(slip_vals)
        slips.compute_sheet()
        slips.action_payslip_done()
        return cls.env['l10n_be.274_xx'].create({
            'year': period_start.year, 'month': str(period_start.month), 'company_id': cls.belgian_company.id,
        })

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.belgian_company.current_payroll_config_id.onss_importance_code = '1'
        cls.sheet_jan_2026 = cls._create_274xx_sheet([
            ('doctor',   100000.0, 0.50), ('master',   100000.0, 0.50),
            ('doctor',   100000.0, 0.70), ('doctor',   100000.0, 1.00),
            ('bachelor', 100000.0, 0.20), ('bachelor', 100000.0, 0.50),
            ('bachelor', 100000.0, 0.50), ('bachelor', 100000.0, 0.80),
            ('bachelor', 100000.0, 1.00),
        ], date(2026, 1, 1))

    def test_doctor_master_not_capped_bachelor_capped_proportionally(self):
        """ Verify bachelor exemption is capped at 50% of the doctor/master total (small company). """
        sheet = self.sheet_jan_2026
        raw_dm = sheet.deducted_amount_32 + sheet.deducted_amount_33
        expected_cap = raw_dm * 0.50
        self.assertGreater(sheet.deducted_amount_34, expected_cap, 'Raw bachelor must exceed the 50% cap.')
        self.assertAlmostEqual(sheet.capped_amount_34, expected_cap, places=2, msg='capped_amount_34 must equal 50% of doctor/master total.')
        self.assertAlmostEqual(sum(line.amount for line in sheet.line_274_34_ids), sheet.capped_amount_34, places=1, msg='Bachelor line amounts must sum to the granted (capped) total.')
        self.assertAlmostEqual(sheet.deducted_amount, raw_dm + expected_cap, places=2, msg='Total deducted must be doctor/master plus capped bachelor.')
        self.assertAlmostEqual(sheet.amount_to_pay, sheet.total_pp_amount - raw_dm - expected_cap, places=2, msg='Amount to pay must be total PP minus granted exemption.')

    def test_bachelor_rate_derived_limit_is_binding(self):
        """ Verify the 25% rate cap applies for large companies (50+ employees). """
        self.belgian_company.current_payroll_config_id.write({'onss_importance_code': '6'})
        sheet = self._create_274xx_sheet([
            ('doctor', 3000.0, 1.0), ('master', 3000.0, 1.0), ('bachelor', 5000.0, 1.0),
        ], date(2026, 3, 1))
        raw_dm = sheet.deducted_amount_32 + sheet.deducted_amount_33
        self.assertGreater(sheet.deducted_amount_34, raw_dm * 0.25, 'Raw bachelor must exceed the 25% cap.')
        self.assertAlmostEqual(sheet.capped_amount_34, raw_dm * 0.25, places=2, msg='capped_amount_34 must equal 25% of doctor/master total for a large company.')

    def test_bachelor_rate_defaults_to_25_percent_when_company_size_undefined(self):
        """ Verify the 25% rate applies when the company size is not configured. """
        self.belgian_company.current_payroll_config_id.write({'onss_importance_code': False})
        sheet = self._create_274xx_sheet([
            ('doctor', 3000.0, 1.0), ('master', 3000.0, 1.0), ('bachelor', 5000.0, 1.0),
        ], date(2026, 4, 1))
        raw_dm = sheet.deducted_amount_32 + sheet.deducted_amount_33
        self.assertGreater(sheet.deducted_amount_34, raw_dm * 0.25, 'Raw bachelor must exceed the 25% cap.')
        self.assertAlmostEqual(sheet.capped_amount_34, raw_dm * 0.25, places=2, msg='capped_amount_34 must default to 25% of doctor/master total when company size is undefined.')

    def test_bachelor_without_doctors_gets_zero_exemption(self):
        """ Verify a bachelor with no doctor/master peers gets zero exemption. """
        sheet = self._create_274xx_sheet([('bachelor', 100000.0, 1.0)], date(2026, 2, 1))
        self.assertGreater(sheet.deducted_amount_34, 0.0, 'Raw bachelor must be positive before the cap is applied.')
        self.assertAlmostEqual(sheet.capped_amount_34, 0.0, places=2, msg='capped_amount_34 must be zero when no doctors or masters are present.')
        self.assertAlmostEqual(sum(line.amount for line in sheet.line_274_34_ids), 0.0, places=2, msg='Bachelor line amounts must also be zero when the exemption is fully denied.')
        self.assertAlmostEqual(sheet.deducted_amount, 0.0, places=2, msg='Total deducted must be zero when bachelor exemption is fully denied.')

    def test_bachelor_amounts_scaled_proportionally_per_employee(self):
        """ Verify each employee's exempted amount is scaled by the same ratio as the aggregate cap,
        proportional to their own uncapped share, not split equally or by headcount. """
        self.belgian_company.current_payroll_config_id.write({'onss_importance_code': '6'})
        bachelor_profiles = [('bachelor', 8000.0, 1.0), ('bachelor', 4000.0, 1.0)]

        # Large doctor/master pool so the cap never binds here: line amounts stay at their raw value.
        uncapped_sheet = self._create_274xx_sheet(
            [('doctor', 100000.0, 1.0), ('master', 100000.0, 1.0)] + bachelor_profiles, date(2026, 5, 1))
        raw_amounts = sorted(uncapped_sheet.line_274_34_ids.mapped('amount'))

        # Same bachelor profiles, but a small doctor/master pool so the 25% cap is now binding.
        capped_sheet = self._create_274xx_sheet(
            [('doctor', 3000.0, 1.0), ('master', 3000.0, 1.0)] + bachelor_profiles, date(2026, 6, 1))
        capped_amounts = sorted(capped_sheet.line_274_34_ids.mapped('amount'))

        self.assertLess(capped_sheet.capped_amount_34, capped_sheet.deducted_amount_34, 'Cap must actually bind for this scenario.')
        ratio = capped_sheet.capped_amount_34 / capped_sheet.deducted_amount_34
        for raw, capped in zip(raw_amounts, capped_amounts):
            self.assertAlmostEqual(capped, raw * ratio, places=1, msg='Each employee amount must scale by the same ratio as the aggregate cap.')
        self.assertAlmostEqual(sum(capped_amounts), capped_sheet.capped_amount_34, places=1, msg='Bachelor line amounts must sum to the granted (capped) total.')
