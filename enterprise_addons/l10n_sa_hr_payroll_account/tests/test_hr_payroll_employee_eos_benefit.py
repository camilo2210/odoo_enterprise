# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests import tagged

from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestHrPayrollEmployeeEosBenefit(TestPayslipValidationCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestPayslipValidationCommon.setup_country('sa')
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref('hr_payroll.group_hr_payroll_manager')
        cls._setup_common(
            country=cls.env.ref('base.sa'),
            structure=cls.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure'),
            structure_type=cls.env.ref('l10n_sa_hr_payroll.ksa_employee_payroll_structure_type'),
            version_fields={
                'wage': 10000,
                'l10n_sa_eos_number_of_days_in_year': '360',
            }
        )

    def test_sa_end_of_service_benefit(self):
        self.employee.version_id.contract_date_start = date(2025, 1, 1)
        self.env['hr.employee.departure'].create([{
            'employee_id': self.employee.id,
            'dismissal_date': date(2025, 6, 9),
            'departure_reason_id': self.env.ref('l10n_sa_hr_payroll.saudi_departure_end_of_contract').id,
        }]).action_register()
        payslip = self._generate_payslip(date(2025, 6, 1), date(2025, 6, 30))

        # test end of contract with approximation of number of days
        payslip.compute_sheet()
        self.assertAlmostEqual(payslip.line_ids.filtered(lambda l: l.code == 'EOSB').total, 0, 2)

        self.employee.version_id.contract_date_start = date(2023, 4, 18)
        payslip.compute_sheet()
        self.assertAlmostEqual(payslip.line_ids.filtered(lambda l: l.code == 'EOSB').total, 10875.00, 2)

        self.employee.version_id.contract_date_start = date(2020, 3, 31)
        payslip.compute_sheet()
        self.assertAlmostEqual(payslip.line_ids.filtered(lambda l: l.code == 'EOSB').total, 27666.67, 2)

        self.employee.version_id.contract_date_start = date(2014, 6, 30)
        payslip.compute_sheet()
        self.assertAlmostEqual(payslip.line_ids.filtered(lambda l: l.code == 'EOSB').total, 86027.78, 2)

        # test resignation with approximation of number of days
        self.employee.departure_reason_id = self.env.ref('hr.departure_resigned').id

        self.employee.version_id.contract_date_start = date(2025, 1, 1)
        payslip.compute_sheet()
        self.assertAlmostEqual(payslip.line_ids.filtered(lambda l: l.code == 'EOSB').total, 0, 2)

        self.employee.version_id.contract_date_start = date(2023, 4, 18)
        payslip.compute_sheet()
        self.assertAlmostEqual(payslip.line_ids.filtered(lambda l: l.code == 'EOSB').total, 3625.00, 2)

        self.employee.version_id.contract_date_start = date(2020, 3, 31)
        payslip.compute_sheet()
        self.assertAlmostEqual(payslip.line_ids.filtered(lambda l: l.code == 'EOSB').total, 8777.78, 2)

        self.employee.version_id.contract_date_start = date(2014, 6, 30)
        payslip.compute_sheet()
        self.assertAlmostEqual(payslip.line_ids.filtered(lambda l: l.code == 'EOSB').total, 86027.78, 2)

        # test end of contract with actual of number of days
        self.employee.version_id.l10n_sa_eos_number_of_days_in_year = 'actual'
        self.employee.departure_reason_id = self.env.ref('l10n_sa_hr_payroll.saudi_departure_end_of_contract').id

        self.employee.version_id.contract_date_start = date(2025, 1, 1)
        payslip.compute_sheet()
        self.assertAlmostEqual(payslip.line_ids.filtered(lambda l: l.code == 'EOSB').total, 0, 2)

        self.employee.version_id.contract_date_start = date(2023, 4, 18)
        payslip.compute_sheet()
        self.assertAlmostEqual(payslip.line_ids.filtered(lambda l: l.code == 'EOSB').total, 10736.11, 2)

        self.employee.version_id.contract_date_start = date(2020, 3, 31)
        payslip.compute_sheet()
        self.assertAlmostEqual(payslip.line_ids.filtered(lambda l: l.code == 'EOSB').total, 26944.44, 2)

        self.employee.version_id.contract_date_start = date(2014, 6, 30)
        payslip.compute_sheet()
        self.assertAlmostEqual(payslip.line_ids.filtered(lambda l: l.code == 'EOSB').total, 84472.22, 2)

        # test resignation with actual of number of days
        self.employee.departure_reason_id = self.env.ref('hr.departure_resigned').id

        self.employee.version_id.contract_date_start = date(2025, 1, 1)
        payslip.compute_sheet()
        self.assertAlmostEqual(payslip.line_ids.filtered(lambda l: l.code == 'EOSB').total, 0, 2)

        self.employee.version_id.contract_date_start = date(2023, 4, 18)
        payslip.compute_sheet()
        self.assertAlmostEqual(payslip.line_ids.filtered(lambda l: l.code == 'EOSB').total, 3578.70, 2)

        self.employee.version_id.contract_date_start = date(2020, 3, 31)
        payslip.compute_sheet()
        self.assertAlmostEqual(payslip.line_ids.filtered(lambda l: l.code == 'EOSB').total, 8657.41, 2)

        self.employee.version_id.contract_date_start = date(2014, 6, 30)
        payslip.compute_sheet()
        self.assertAlmostEqual(payslip.line_ids.filtered(lambda l: l.code == 'EOSB').total, 84472.22, 2)

        # test fired employee with actual of number of days
        self.employee.departure_reason_id = self.env.ref('hr.departure_fired').id
        payslip.compute_sheet()
        self.assertAlmostEqual(payslip.line_ids.filtered(lambda l: l.code == 'EOSB').total, 0, 2)

        # test laid off employee with actual of number of days
        self.employee.departure_reason_id = self.env.ref('l10n_sa_hr_payroll.saudi_departure_company_article_77').id
        payslip.compute_sheet()
        self.assertAlmostEqual(payslip.line_ids.filtered(lambda l: l.code == 'EOSB').total, 20000, 2)
