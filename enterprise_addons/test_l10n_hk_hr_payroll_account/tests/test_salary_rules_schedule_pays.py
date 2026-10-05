# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from dateutil.relativedelta import relativedelta
from odoo.tests import tagged

from .common import TestL10NHkHrPayrollAccountCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestSalaryRulesSchedulePays(TestL10NHkHrPayrollAccountCommon):
    """ Test suite to assert that our salary rules correctly calculate the amounts for a daily paid employee. """
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rental = cls._create_test_rental(cls, cls.version.employee_id)
        cls.rental.action_confirm_rental()
        cls.rental.valid_up_to_date = date(2027, 1, 31)
        cls.version.write({
            "l10n_hk_mpf_scheme_id": cls.mpf_scheme.id,
            "l10n_hk_mpf_contribution_start": "immediate",
            "l10n_hk_mpf_registration_status": "registered",
            "l10n_hk_member_class_id": cls.member_class.id,
            "l10n_hk_mpf_scheme_join_date": date(2011, 1, 2),
        })
        cls.version.l10n_hk_member_class_ct_ervc2_id = cls.env['l10n_hk.member.class.contribution.type'].create({
            'member_class_id': cls.member_class.id,
            'contribution_type': 'employer_2',
            'contribution_option': 'fixed',
            'amount': 1000,  # Monthly amount!
        })

    def test_weekly_schedule(self):
        self.version.write({
            'schedule_pay': 'weekly',
            'wage': 10000,
        })
        payslip = self._generate_payslip(
            date(2025, 1, 6),
            date(2025, 1, 12),
        )
        payslip_results = {
            'HRA': 1846.15,
            'BASIC': 8153.85,
            'ALW.INT': 200.0,
            '713_GROSS': 10200.0,
            'GROSS': 10200.0,
            'EEMC': -350.0,
            'ERMC': -350.0,
            'EEVC': -160.0,
            'ERVC': -160.0,
            'ERVC2': -230.77,
            'NET': 9690.0,
            'MEA': 9690.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_bi_weekly_schedule(self):
        self.version.write({
            'schedule_pay': 'bi-weekly',
            'wage': 20000,
        })
        payslip = self._generate_payslip(
            date(2025, 1, 6),
            date(2025, 1, 19),
        )
        payslip_results = {
            'HRA': 3692.31,
            'BASIC': 16307.69,
            'ALW.INT': 200.0,
            '713_GROSS': 20200.0,
            'GROSS': 20200.0,
            'EEMC': -700.0,
            'ERMC': -700.0,
            'EEVC': -310.0,
            'ERVC': -310.0,
            'ERVC2': -461.54,
            'NET': 19190.0,
            'MEA': 19190.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_daily_schedule(self):
        self.version.write({
            'schedule_pay': 'daily',
            'wage': 1500,
        })
        payslip = self._generate_payslip(
            date(2025, 1, 6),
            date(2025, 1, 6),
        )
        payslip_results = {
            'HRA': 369.23,
            'BASIC': 1130.77,
            'ALW.INT': 200.0,
            '713_GROSS': 1700.0,
            'GROSS': 1700.0,
            'EEMC': -50.0,
            'ERMC': -50.0,
            'EEVC': -35.0,
            'ERVC': -35.0,
            'ERVC2': -46.15,
            'NET': 1615.0,
            'MEA': 1615.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_semi_monthly_schedule(self):
        self.version.write({
            'schedule_pay': 'semi-monthly',
            'wage': 20000,
        })
        payslip = self._generate_payslip(
            date(2025, 1, 1),
            date(2025, 1, 15),
        )
        payslip_results = {
            'HRA': 4000.0,
            'BASIC': 16000.0,
            'ALW.INT': 200.0,
            '713_GROSS': 20200.0,
            'GROSS': 20200.0,
            'EEMC': -750.0,
            'ERMC': -750.0,
            'EEVC': -260.0,
            'ERVC': -260.0,
            'ERVC2': -500.0,
            'NET': 19190.0,
            'MEA': 19190.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_weekly_schedule_copay(self):
        self.rental.write({
            'lease_type': 'co_payment',
            'co_pay_amount': 2000,
        })
        self.version.write({
            'schedule_pay': 'weekly',
            'wage': 10000,
        })
        payslip = self._generate_payslip(
            date(2025, 1, 6),
            date(2025, 1, 12),
        )
        payslip_results = {
            'BASIC': 10000.0,
            'ALW.INT': 200.0,
            '713_GROSS': 10200.0,
            'GROSS': 10200.0,
            'EEMC': -350.0,
            'ERMC': -350.0,
            'EEVC': -160.0,
            'ERVC': -160.0,
            'ERVC2': -230.77,
            'NET': 9228.46,
            'MEA': 9228.46,
            'HEPR': 1846.15,
            'HC': -461.54,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_bi_weekly_schedule_copay(self):
        self.rental.write({
            'lease_type': 'co_payment',
            'co_pay_amount': 2000,
        })
        self.version.write({
            'schedule_pay': 'bi-weekly',
            'wage': 20000,
        })
        payslip = self._generate_payslip(
            date(2025, 1, 6),
            date(2025, 1, 19),
        )
        payslip_results = {
            'BASIC': 20000.0,
            'ALW.INT': 200.0,
            '713_GROSS': 20200.0,
            'GROSS': 20200.0,
            'EEMC': -700.0,
            'ERMC': -700.0,
            'EEVC': -310.0,
            'ERVC': -310.0,
            'ERVC2': -461.54,
            'NET': 18266.92,
            'MEA': 18266.92,
            'HEPR': 3692.31,
            'HC': -923.08,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_daily_schedule_copay(self):
        self.rental.write({
            'lease_type': 'co_payment',
            'co_pay_amount': 2000,
        })
        self.version.write({
            'schedule_pay': 'daily',
            'wage': 1500,
        })
        payslip = self._generate_payslip(
            date(2025, 1, 6),
            date(2025, 1, 6),
        )
        payslip_results = {
            'BASIC': 1500.0,
            'ALW.INT': 200.0,
            '713_GROSS': 1700.0,
            'GROSS': 1700.0,
            'EEMC': -50.0,
            'ERMC': -50.0,
            'EEVC': -35.0,
            'ERVC': -35.0,
            'ERVC2': -46.15,
            'NET': 1522.69,
            'MEA': 1522.69,
            'HEPR': 369.23,
            'HC': -92.31,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_semi_monthly_schedule_copay(self):
        self.rental.write({
            'lease_type': 'co_payment',
            'co_pay_amount': 2000,
        })
        self.version.write({
            'schedule_pay': 'semi-monthly',
            'wage': 20000,
        })
        payslip = self._generate_payslip(
            date(2025, 1, 1),
            date(2025, 1, 15),
        )
        payslip_results = {
            'BASIC': 20000.0,
            'ALW.INT': 200.0,
            '713_GROSS': 20200.0,
            'GROSS': 20200.0,
            'EEMC': -750.0,
            'ERMC': -750.0,
            'EEVC': -260.0,
            'ERVC': -260.0,
            'ERVC2': -500.0,
            'NET': 18190.0,
            'MEA': 18190.0,
            'HEPR': 4000.0,
            'HC': -1000.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_semi_monthly_schedule_contract_change(self):
        """
        Test the case of a contract change where an employer paid rent is involved.
        In this scenario, the employer pays the full amount in the first payslip.
        """
        self.version.write({
            'schedule_pay': 'semi-monthly',
            'date_version': date(2025, 10, 1),
            'contract_date_start': date(2025, 10, 1),
            'contract_date_end': date(2026, 1, 10),
            'wage': 20000,
        })
        self.employee.create_version({
            'date_version': date(2026, 1, 11),
            'contract_date_start': date(2026, 1, 11),
            'wage': 20000,
        })
        structure = self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary')
        structure.type_id.default_schedule_pay = 'semi-monthly'  # for the payrun

        payrun = self.env['hr.payslip.run'].create({
            'date_start': date(2026, 1, 1),
            'date_end': date(2026, 1, 15),
            'company_id': self.env.company.id,
            'structure_id': structure.id,
        })
        payrun._generate_payslips()
        payslips = payrun.slip_ids.sorted('date_from asc')
        self.assertEqual(len(payslips), 2)
        # Assert the first payslip's line
        first_payslip_results = {
            'HRA': 4000.0,
            'BASIC': 9333.33,
            'ALW.INT': 133.33,
            '713_GROSS': 13466.66,
            'GROSS': 13466.66,
            'EEMC': -673.33,
            'ERMC': -673.33,
            'EEVC': 0.0,
            'ERVC': 0.0,
            'ERVC2': -333.33,
            'NET': 12793.33,
            'MEA': 12793.33,
        }
        self._validate_payslip(payslips[0], first_payslip_results)
        # And the second
        second_payslip_results = {
            'HRA': 0.0,
            'BASIC': 6666.66,
            'ALW.INT': 66.67,
            '713_GROSS': 6733.33,
            'GROSS': 6733.33,
            'EEMC': -76.67,
            'ERMC': -76.67,
            'EEVC': -260.0,
            'ERVC': -260.0,
            'ERVC2': -166.67,
            'NET': 6396.66,
            'MEA': 6396.66,
        }
        self._validate_payslip(payslips[1], second_payslip_results)
        # As comparison, we'll also do a payslip for another month of same length.
        date_start = date(2026, 3, 1)
        payrun = self.env['hr.payslip.run'].create({
            'date_start': date_start,
            'date_end': date_start + relativedelta(day=15),
            'company_id': self.env.company.id,
            'structure_id': structure.id,
        })
        payrun._generate_payslips()
        payslips = payrun.slip_ids
        control_payslip_results = {
            'HRA': 4000.0,
            'BASIC': 16000.0,
            'ALW.INT': 200.0,
            '713_GROSS': 20200.0,
            'GROSS': 20200.0,
            'EEMC': -750.0,
            'ERMC': -750.0,
            'EEVC': -260.0,
            'ERVC': -260.0,
            'ERVC2': -500.0,
            'NET': 19190.0,
            'MEA': 19190.0,
        }
        self._validate_payslip(payslips, control_payslip_results)
        # And to make sure we're all good, we now sum the two half month payslip and compare the result with the full month one!
        for rule, control_value in control_payslip_results.items():
            self.assertAlmostEqual(
                first_payslip_results[rule] + second_payslip_results[rule], control_value, places=1
            )

    def test_semi_monthly_schedule_hra_cap(self):
        self.version.write({
            'schedule_pay': 'semi-monthly',
            'wage': 20000,
        })
        self.rental.amount = 40000
        payslip = self._generate_payslip(
            date(2025, 1, 1),
            date(2025, 1, 15),
        )
        payslip_results = {
            'HRA': 16480.0,
            'BASIC': 3520.0,
            'ALW.INT': 200.0,
            '713_GROSS': 20200.0,
            'GROSS': 20200.0,
            'EEMC': -750.0,
            'ERMC': -750.0,
            'EEVC': -260.0,
            'ERVC': -260.0,
            'ERVC2': -500.0,
            'NET': 19190.0,
            'MEA': 19190.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_semi_monthly_schedule_co_pay_cap(self):
        self.rental.write({
            'lease_type': 'co_payment',
            'co_pay_amount': 40000,
            'amount': 80000,
        })
        self.version.write({
            'schedule_pay': 'semi-monthly',
            'wage': 20000,
        })
        payslip = self._generate_payslip(
            date(2025, 1, 1),
            date(2025, 1, 15),
        )
        payslip_results = {
            'BASIC': 20000.0,
            'ALW.INT': 200.0,
            '713_GROSS': 20200.0,
            'GROSS': 20200.0,
            'EEMC': -750.0,
            'ERMC': -750.0,
            'EEVC': -260.0,
            'ERVC': -260.0,
            'ERVC2': -500.0,
            'NET': 0.0,
            'MEA': 0.0,
            'HEPR': 40000.0,
            'HC': -19190.0,
        }
        self._validate_payslip(payslip, payslip_results)
