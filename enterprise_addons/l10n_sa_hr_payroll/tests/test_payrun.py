from .common import TestSACommon
from odoo.tests import tagged
from datetime import date


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestSaudiPayrun(TestSACommon):
    def test_payrun_total_costs(self):
        self.saudi_employee.write({
            "wage": 10000,
            "l10n_sa_housing_allowance": 5000,
            "l10n_sa_company_social_insurance_percentage": 0.2,
            "l10n_sa_employee_social_insurance_percentage": 0.2,
            "l10n_sa_company_oh_insurance_percentage": 0,
            "l10n_sa_company_unemployment_insurance_percentage": 0,
            "l10n_sa_employee_oh_insurance_percentage": 0,
            "l10n_sa_employee_unemployment_insurance_percentage": 0,
            "l10n_sa_iqama_annual_amount": 0,
            "l10n_sa_medical_insurance_annual_amount": 0,
            "l10n_sa_work_permit_annual_amount": 0,
        })
        payrun = self.env['hr.payslip.run'].create({
            'name': 'Saudi Payrun June 2026',
            'company_id': self.sa_company.id,
            'structure_id': self.saudi_employee.structure_id.id,
            'date_start': date(2026, 6, 1),
            'date_end': date(2026, 6, 30),
        })
        payslip1 = self.env['hr.payslip'].create({
            'payslip_run_id': payrun.id,
            'employee_id': self.saudi_employee.id,
            'state': "draft",
        })
        # gosi_contribution=6000, net_cost=18700 in payslip1
        payslip1.compute_sheet()
        payslip_results = {'GOSI_EMP': -3000, 'GOSI_COMP': -3000, 'NETCOST': 18700}
        self._validate_payslip(payslip1, payslip_results, skip_lines=True)

        employee_sa_2 = self.saudi_employee
        employee_sa_2.l10n_sa_housing_allowance = 0
        employee_sa_2.l10n_sa_company_social_insurance_percentage = 0.1
        employee_sa_2.l10n_sa_employee_social_insurance_percentage = 0.1
        payslip2 = self.env['hr.payslip'].create({
            'payslip_run_id': payrun.id,
            'employee_id': employee_sa_2.id,
            'state': "draft",
        })
        # gosi_contribution=2000, net_cost=11700 in payslip2
        payslip2.compute_sheet()
        payslip_results = {'GOSI_EMP': -1000, 'GOSI_COMP': -1000, 'NETCOST': 11700}
        self._validate_payslip(payslip2, payslip_results, skip_lines=True)

        self.assertEqual(payrun.l10n_sa_total_gosi_contribution, 8000)
        self.assertEqual(payrun.l10n_sa_total_net_cost, 30400)

        # gosi_contribution=2000, net_cost=11700 in payslip3
        payslip3 = self.env['hr.payslip'].create({
            'payslip_run_id': payrun.id,
            'employee_id': employee_sa_2.id,
            'state': "draft",
        })
        payslip3.compute_sheet()
        self.assertEqual(payrun.l10n_sa_total_gosi_contribution, 10000)
        self.assertEqual(payrun.l10n_sa_total_net_cost, 42100)

        payslip3.action_payslip_cancel()
        # cancelled one will not affect (same as previous result before payslip 3)
        self.assertEqual(payrun.l10n_sa_total_gosi_contribution, 8000)
        self.assertEqual(payrun.l10n_sa_total_net_cost, 30400)
