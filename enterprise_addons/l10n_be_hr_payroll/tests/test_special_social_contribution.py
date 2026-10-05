# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tests import tagged

from odoo.addons.l10n_be_hr_payroll.tests.common import TestPayrollCommon


@tagged('-at_install', 'post_install', 'post_install_l10n')
class TestSpecialSocialContribution(TestPayrollCommon):
    """
    The special social contribution (CSSS) is a quarterly tax that has to be
    deduced from the salary of the employee on a monthly basis (to not reduce
    the employees's wage all at once). This suite will test if the tax is
    implemented correctly.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cp200_struct = cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary')
        cls.cp200 = cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200')
        cls.cp302 = cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_302')
        cls.ordinary_worker_code = cls.env['l10n.be.worker.code'].search([('dmfa_code', '=', '015')])
        cls.ordinary_employee_code = cls.env['l10n.be.worker.code'].search([('dmfa_code', '=', '495')])

    @classmethod
    def _get_months(cls, year):
        def is_leap_year(y):
            if y % 4 != 0:
                return False
            if y % 100 != 0:
                return True
            return y % 400 == 0

        return {
            1: {'name': 'January', 'first_day': 1, 'last_day': 31},
            2: {'name': 'February', 'first_day': 1, 'last_day': 29 if is_leap_year(year) else 28},
            3: {'name': 'March', 'first_day': 1, 'last_day': 31},
            4: {'name': 'April', 'first_day': 1, 'last_day': 30},
            5: {'name': 'May', 'first_day': 1, 'last_day': 31},
            6: {'name': 'June', 'first_day': 1, 'last_day': 30},
            7: {'name': 'July', 'first_day': 1, 'last_day': 31},
            8: {'name': 'August', 'first_day': 1, 'last_day': 31},
            9: {'name': 'September', 'first_day': 1, 'last_day': 30},
            10: {'name': 'October', 'first_day': 1, 'last_day': 31},
            11: {'name': 'November', 'first_day': 1, 'last_day': 30},
            12: {'name': 'December', 'first_day': 1, 'last_day': 31},
        }

    @classmethod
    def _get_owed_csss(
            cls, gross_onss_wage, date, couple_status: str, frequency: str, round_result=True,
    ) -> float:
        """
        Return the owed special social contribution for a given wage and situation
        """
        if frequency not in ('monthly', 'quarterly'):
            raise UserError(f'frequency "{frequency}" is invalid')
        if couple_status not in ('single', 'couple_single_income', 'couple_dual_income'):
            raise UserError(f'Invalid couple_status "{couple_status}"')
        rates = cls.env['hr.rule.parameter']._get_parameter_from_code(f'special_social_contribution_{frequency}_rate_{couple_status}', date)

        # take the rates from the first matching bracket
        for rate in sorted(rates, key=lambda r: r['from'], reverse=True):
            if rate['from'] <= gross_onss_wage:
                exceeding_amount = gross_onss_wage - (rate['from'] - 0.01)
                owed_css = rate['amount'] + exceeding_amount * (rate.get('percentage', 0) / 100)
                if 'min' in rate:
                    owed_css = max(rate['min'], owed_css)
                if 'max' in rate:
                    owed_css = min(rate['max'], owed_css)
                if round_result:
                    return round(owed_css, 2)
                return owed_css

        return 0

    @classmethod
    def _get_payslips_csss(cls, payslip_ids) -> float:
        return sum(payslip_ids.line_ids.filtered_domain([['code', '=', 'M.ONSS']]).mapped('total'))

    @classmethod
    def _get_payslips_gross_onss_wage(cls, payslip_ids) -> float:
        """
        The only gross onss wages we care are the monthly salary and the 13th
        month salary, the rest is used differrently in the computation
        """
        return sum(payslip_ids.line_ids.filtered_domain([
            ['code', 'in', ('SALARY', 'BONUS_SALARY')],
        ]).mapped('total'))

    def _generate_monthly_payslips_range(self, date_from, date_to, employee):
        """
        Will create validated payslips from date_from to date_to (only years and
        months of the date parameters will be taken in account)
        """
        generated_payslips = []
        for year in range(date_from.year, date_to.year + 1):
            month_from = date_from.month if year == date_from.year else 1
            month_to = date_to.month if year == date_to.year else 1
            for month in range(month_from, month_to + 1):
                month_info = self._get_months(year)[month]
                payslip = self.env['hr.payslip'].create({
                    'employee_id': employee.id,
                    'version_id': employee.version_id.id,
                    "date_from": date(year, month, month_info['first_day']),
                    "date_to": date(year, month, month_info['last_day']),
                    "struct_id": self.cp200_struct.id,
                })
                payslip.action_validate()
                generated_payslips.append(payslip)
        return generated_payslips

    def _test_special_cotisation_all_months(self, employee, year: int, couple_status: str, last_work_month=12):
        """
        Will test if the employee's payslips of `year`, up to `last_work_month`
        have the correct amount of special social contributions
        """
        quarter_payslips = self.env['hr.payslip']
        for month_index, month in self._get_months(year).items():
            if month_index > last_work_month:
                return  # we did all months of year. We can stop
            if (month_index - 1) % 3 == 0:
                # beginning of new quarter - reset the payslips
                quarter_payslips = self.env['hr.payslip']

            month_start = date(year, month_index, month['first_day'])
            month_stop = date(year, month_index, month['last_day'])
            payslip = self.env['hr.payslip'].create({
                'employee_id': employee.id,
                'version_id': employee.version_id.id,
                "date_from": month_start,
                "date_to": month_stop,
                "struct_id": self.cp200_struct.id,
            })
            payslip.action_validate()
            quarter_payslips |= payslip

            frequency = 'monthly'
            if (month_index % 3) == 0 or month_index == last_work_month:
                frequency = 'quarterly'

            # to describe the worker uplift in error messages if needed
            error_msg_worker_extra = ' * 1.08 for workers' if payslip.version_id.is_worker() else ''
            # no worker uplift if employee is not a worker
            worker_uplift = 1.08 if payslip.version_id.is_worker() else 1

            if frequency == 'monthly':
                month_gross_wage = self._get_payslips_gross_onss_wage(payslip)
                wanted_csss = -self._get_owed_csss(
                    month_gross_wage * worker_uplift, payslip.date_to, couple_status, frequency,
                )
                self.assertAlmostEqual(wanted_csss, self._get_payslips_csss(payslip), msg=f'''
The special social contribution of payslip of {month['name']} should be the
monthly gross onss wage{error_msg_worker_extra} computed with the monthly
contribution rates for the marital status of {payslip.l10n_be_effective_marital}.
                ''')
            else:  # quarterly
                quarter_gross_wage = self._get_payslips_gross_onss_wage(quarter_payslips)
                csss_quarter_advances = -self._get_payslips_csss(quarter_payslips - payslip)
                wanted_csss = -(self._get_owed_csss(
                    quarter_gross_wage * worker_uplift, payslip.date_to, couple_status, frequency,
                ) - csss_quarter_advances)
                self.assertAlmostEqual(wanted_csss, self._get_payslips_csss(payslip), msg=f'''
The special social contribution of payslip of {month['name']} should be the
total quarterly gross onss wage{error_msg_worker_extra} computed with the
quarterly contribution rates for the marital status of {payslip.l10n_be_effective_marital}
minus the contributions paid in the two previous months.
                ''')

    def test_regular_year_employee_couple_single_income(self):
        """
        See if an employee has the correct special social contribution (csss)
        throughout the year, with the correct rates (couple rates - single income)
        """
        employee = self.env['hr.employee'].create({
            'name': 'Dr. Eggman',
            'contract_date_start': date(2024, 1, 1),
            'contract_date_end': False,
            'wage_type': 'monthly',
            'wage': 4000,
            'l10n_be_joint_committee_id': self.cp200.id,
            'resource_calendar_id': self.resource_calendar_40.id,
            'l10n_be_worker_code_id': self.ordinary_employee_code.id,
        })
        employee.version_id.marital = 'married'
        employee.version_id.spouse_fiscal_status = 'without_income'
        self._test_special_cotisation_all_months(employee, 2025, 'couple_single_income')

    def test_regular_year_employee_couple_dual_income(self):
        """
        See if an employee has the correct special social contribution (csss)
        throughout the year, with the correct rates (couple rates - dual income)
        """
        employee = self.env['hr.employee'].create({
            'name': 'Dr. Eggman',
            'contract_date_start': date(2024, 1, 1),
            'contract_date_end': False,
            'wage_type': 'monthly',
            'wage': 4000,
            'l10n_be_joint_committee_id': self.cp200.id,
            'resource_calendar_id': self.resource_calendar_40.id,
            'l10n_be_worker_code_id': self.ordinary_employee_code.id,
        })
        employee.version_id.marital = 'married'
        employee.version_id.spouse_fiscal_status = 'low_income'
        self._test_special_cotisation_all_months(employee, 2025, 'couple_dual_income')

    def test_regular_year_worker(self):
        """
        See if a worker has the correct special social contribution (csss)
        throughout the year (computed on wage * 1.08), with the correct rates
        """
        employee = self.env['hr.employee'].create({
            'name': 'Dr. Eggman',
            'contract_date_start': date(2024, 1, 1),
            'contract_date_end': False,
            'wage_type': 'hourly',
            'wage': 20,
            'l10n_be_joint_committee_id': self.cp200.id,
            'resource_calendar_id': self.resource_calendar_40.id,
            'l10n_be_worker_code_id': self.ordinary_worker_code.id,
        })
        self._test_special_cotisation_all_months(employee, 2025, 'single')

    def test_worker_stops_january(self):
        """
        If a worker stops working on the first month, he should pay the
        quarterly amount for january, which is usually nothing
        """
        employee = self.env['hr.employee'].create({
            'name': 'Dr. Eggman',
            'contract_date_start': date(2024, 1, 1),
            'contract_date_end': False,
            'wage_type': 'hourly',
            'wage': 10,
            'l10n_be_joint_committee_id': self.cp200.id,
            'resource_calendar_id': self.resource_calendar_40.id,
            'l10n_be_worker_code_id': self.ordinary_worker_code.id,
        })
        employee.version_id.date_end = date(2025, 1, 31)
        self._test_special_cotisation_all_months(employee, 2025, 'single', last_work_month=1)

    def test_worker_stops_mid_may_couple(self):
        """
        Test if the CSSS does get lowered correctly if the worker stop in the
        middle of a month
        """
        employee = self.env['hr.employee'].create({
            'name': 'Dr. Eggman',
            'contract_date_start': date(2024, 1, 1),
            'contract_date_end': date(2025, 5, 15),
            'wage_type': 'hourly',
            'hourly_wage': 30,
            'l10n_be_joint_committee_id': self.cp200.id,
            'resource_calendar_id': self.resource_calendar_40.id,
            'l10n_be_worker_code_id': self.ordinary_worker_code.id,
        })
        worker_uplift = 1.08
        employee.version_id.marital = 'married'
        employee.version_id.spouse_fiscal_status = 'high_income'

        payslip_april, payslip_may = self.env['hr.payslip'].create([
            {
                'name': "Payslip April Test",
                'employee_id': employee.id,
                'version_id': employee.version_id.id,
                "date_from": date(2025, 4, 1),
                "date_to": date(2025, 4, 30),
                "struct_id": self.cp200_struct.id,
            },
            {
                'name': "Payslip May Test",
                'employee_id': employee.id,
                'version_id': employee.version_id.id,
                "date_from": date(2025, 5, 1),
                "date_to": date(2025, 5, 15),
                "struct_id": self.cp200_struct.id,
            },
        ])
        # we have to do them one by one, otherwise payslip_may won't know that
        # there is a validated payslip in april
        payslip_april.compute_sheet()
        payslip_april.action_validate()
        payslip_may.compute_sheet()
        payslip_may.action_validate()

        april_gross_wage = self._get_payslips_gross_onss_wage(payslip_april)
        expected_april_csss = self._get_owed_csss(april_gross_wage * worker_uplift, payslip_april.date_to, 'couple_dual_income', 'monthly')
        april_csss = -self._get_payslips_csss(payslip_april)
        self.assertAlmostEqual(expected_april_csss, april_csss, msg='''
Failed a basic monthly CSSS test for april
        ''')
        may_gross_wage = self._get_payslips_gross_onss_wage(payslip_may)
        expected_may_csss = self._get_owed_csss(
            (april_gross_wage + may_gross_wage) * worker_uplift,
            payslip_may.date_to, 'couple_dual_income', 'quarterly',
        ) - april_csss
        may_csss = -self._get_payslips_csss(payslip_may)
        self.assertAlmostEqual(round(expected_may_csss, 2), may_csss, msg='''
The special social contribution should adjust correctly if the wage decreases
due to the worker stopping his collaboration in the middle of the month.
        ''')

    def test_employee_cancelled_payslips_quarterly(self):
        """
        The rate used for the Special Social Contribution should be always
        quarterly if there is a validated payslip at the end of the quarter
        """
        employee = self.env['hr.employee'].create({
            'name': 'Dr. Eggman',
            'contract_date_start': date(2025, 1, 1),
            'contract_date_end': False,
            'wage_type': 'monthly',
            'wage': 4000,
            'l10n_be_joint_committee_id': self.cp200.id,
            'resource_calendar_id': self.resource_calendar_40.id,
            'l10n_be_worker_code_id': self.ordinary_employee_code.id,
        })
        # will generate and validate payslips for the whole year
        self._test_special_cotisation_all_months(employee, 2025, 'single')

        quarter_payslips = self.env['hr.payslip'].search([
            ['date_from', '>=', date(2025, 4, 1)],
            ['date_to', '<=', date(2025, 6, 30)],
            ['employee_id', '=', employee.id],
            ['state', 'in', ('validated', 'paid')],
        ])

        # revert the current may payslip
        may_payslip = self.env['hr.payslip'].search([
            ['date_from', '>=', date(2025, 5, 1)],
            ['date_to', '<=', date(2025, 5, 31)],
            ['employee_id', '=', employee.id],
            ['state', 'in', ('validated', 'paid')],
        ])
        may_payslip.action_payslip_paid()
        may_payslip._action_refund_payslips().action_validate()

        # create a new may payslip that will replace the old, reverted one
        new_may_payslip = self.env['hr.payslip'].create([
            {
                'name': "Payslip May Test 2",
                'employee_id': employee.id,
                'version_id': employee.version_id.id,
                "date_from": date(2025, 5, 1),
                "date_to": date(2025, 5, 31),
                "struct_id": self.cp200_struct.id,
            },
        ])
        new_may_payslip.action_validate()

        quarter_payslips = (quarter_payslips - may_payslip) | new_may_payslip

        quarter_gross_wage = self._get_payslips_gross_onss_wage(quarter_payslips)
        csss_quarter_advances = -self._get_payslips_csss(quarter_payslips - new_may_payslip)
        wanted_csss = -(self._get_owed_csss(
            quarter_gross_wage, new_may_payslip.date_to, 'single', 'quarterly',
        ) - csss_quarter_advances)
        self.assertAlmostEqual(wanted_csss, self._get_payslips_csss(new_may_payslip), msg='''
When recomputing a payslip that has been reverted before, the applied rate for
the rate for the Special Social Contribution should be quarterly if a payslip at
the end of the quarter is already validated
        ''')

    def test_employee_cancelled_payslips_monthly(self):
        """
        The rate used for the Special Social Contribution should still be
        monthly if there is no validated payslip at the end of the quarter, and
        if the current computed paylsip is not the last one of the quarter
        """
        employee = self.env['hr.employee'].create({
            'name': 'Dr. Eggman',
            'contract_date_start': date(2025, 1, 1),
            'contract_date_end': False,
            'wage_type': 'monthly',
            'wage': 4000,
            'l10n_be_joint_committee_id': self.cp200.id,
            'resource_calendar_id': self.resource_calendar_40.id,
            'l10n_be_worker_code_id': self.ordinary_employee_code.id,
        })
        jan_payslip = self.env['hr.payslip'].create([
            {
                'name': "Payslip January Test",
                'employee_id': employee.id,
                'version_id': employee.version_id.id,
                "date_from": date(2025, 1, 1),
                "date_to": date(2025, 1, 31),
                "struct_id": self.cp200_struct.id,
            },
        ])
        jan_payslip.action_validate()
        jan_payslip.action_payslip_paid()
        old_jan_csss = self._get_payslips_csss(jan_payslip)
        jan_payslip._action_refund_payslips().action_validate()

        new_jan_payslip = self.env['hr.payslip'].create([
            {
                'name': "Payslip January Test 2",
                'employee_id': employee.id,
                'version_id': employee.version_id.id,
                "date_from": date(2025, 1, 1),
                "date_to": date(2025, 1, 31),
                "struct_id": self.cp200_struct.id,
            },
        ])
        new_jan_payslip.action_validate()
        new_jan_csss = self._get_payslips_csss(new_jan_payslip)

        self.assertAlmostEqual(old_jan_csss, new_jan_csss, msg='''
If we refund and redo a new payslip, and no payslip is validated at the end of
the quarter then the rate for the special social contribution should still be
the monthly rate
        ''')

    def test_employee_below_brackets(self):
        """
        If employees don't gain enough, and fall under any defined special
        social contribution brackets, then the special social contribution
        should be 0
        """
        employee = self.env['hr.employee'].create({
            'name': 'Egg Minion',
            'contract_date_start': date(2025, 1, 1),
            'contract_date_end': False,
            'wage_type': 'monthly',
            'wage': 400,  # really low wage, should be under any bracket
            'l10n_be_joint_committee_id': self.cp200.id,
            'resource_calendar_id': self.resource_calendar_40.id,
            'l10n_be_worker_code_id': self.ordinary_employee_code.id,
        })

        # will generate and validate payslips for the whole year
        self._test_special_cotisation_all_months(employee, 2025, 'single')

        all_year_payslips = self.env['hr.payslip'].search([
            ['date_from', '>=', date(2025, 1, 1)],
            ['date_to', '<=', date(2025, 12, 31)],
            ['employee_id', '=', employee.id],
            ['state', 'in', ('validated', 'paid')],
        ])

        for payslip in all_year_payslips:
            csss = self._get_payslips_csss(payslip)
            self.assertEqual(0, csss, f"""
An employee with a really low wage, should not have any Special Social
Contribution as it should fall below the defined brackets.
Got {csss} instead of 0.0 for the month of {self._get_months(2025)[payslip.date_to.month]['name']}
            """)

    def test_thirteen_month_special_social_contribution(self):
        """
        The thirteen month's payslip (e.g.: for the cp200) should also be
        counted, and compute the special social contribution (CSSS)
        """
        employee = self.env['hr.employee'].create({
            'name': 'Dr. Eggman',
            'contract_date_start': date(2025, 1, 1),
            'contract_date_end': False,
            'wage_type': 'monthly',
            'wage': 3500,
            'l10n_be_joint_committee_id': self.cp200.id,
            'resource_calendar_id': self.resource_calendar_40.id,
            'l10n_be_worker_code_id': self.ordinary_worker_code.id,
        })
        # employee is a worker (ouvrier). He will be subject to the 108% uplift
        # on all his ONSS-subject salaries during the computation
        uplift = 1.08

        # we have to validate the following payslips one by one, otherwise
        # payslip_november won't know that there is a validated payslip in october
        payslip_october, payslip_november = self.env['hr.payslip'].create([
            {
                'name': "Payslip October Test",
                'employee_id': employee.id,
                'version_id': employee.version_id.id,
                "date_from": date(2025, 10, 1),
                "date_to": date(2025, 10, 31),
                "struct_id": self.cp200_struct.id,
            },
            {
                'name': "Payslip November Test",
                'employee_id': employee.id,
                'version_id': employee.version_id.id,
                "date_from": date(2025, 11, 1),
                "date_to": date(2025, 11, 30),
                "struct_id": self.cp200_struct.id,
            },
        ])
        payslip_october.action_validate()
        wanted_csss_october = -(self._get_owed_csss(
            self._get_payslips_gross_onss_wage(payslip_october) * uplift,
            payslip_october.date_to,
            'single',
            'monthly',
        ))
        self.assertAlmostEqual(wanted_csss_october, self._get_payslips_csss(payslip_october), msg='''
Got an unexpected special social contribution value for a regular month (october)
        ''')
        payslip_november.action_validate()
        wanted_csss_november = -(self._get_owed_csss(
            self._get_payslips_gross_onss_wage(payslip_november) * uplift,
            payslip_november.date_to,
            'single',
            'monthly',
        ))
        self.assertAlmostEqual(wanted_csss_november, self._get_payslips_csss(payslip_november), msg='''
Got an unexpected special social contribution value for a regular month (november)
        ''')

        # create the 13th month now to see if it reuses the values from october
        # and november
        payslip_13th_month = self.env['hr.payslip'].create({
            'version_id': employee.version_id.id,
            'date_from': date(2025, 12, 1),
            'date_to': date(2025, 12, 31),
            'employee_id': employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_thirteen_month').id,
        })
        payslip_13th_month.action_validate()
        wanted_csss_13th_month = -(self._get_owed_csss(
            self._get_payslips_gross_onss_wage(payslip_13th_month) * uplift,
            payslip_13th_month.date_to,
            'single',
            'monthly',
        ))
        self.assertAlmostEqual(wanted_csss_13th_month, self._get_payslips_csss(payslip_13th_month), msg='''
The 13th month payslip is generated before the monthly payslip of december, so
it is not the last payslip of the quarter: it should compute its special social
contribution using the monthly rates. The december payslip will be the one
closing the quarter with the quarterly rates.
        ''')

        # let's see if the december payslip does indeed reuse also the csss and
        # gross wage of the 13th month now.
        payslip_december = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2025, 12, 1),
            "date_to": date(2025, 12, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip_december.action_validate()
        quarter_wanted_csss = -(self._get_owed_csss(
            self._get_payslips_gross_onss_wage(payslip_october | payslip_november | payslip_13th_month | payslip_december) * uplift,
            payslip_december.date_to,
            'single',
            'quarterly',
        ))
        wanted_csss_december = quarter_wanted_csss - wanted_csss_november - wanted_csss_october - wanted_csss_13th_month
        self.assertAlmostEqual(wanted_csss_december, self._get_payslips_csss(payslip_december), msg='''
The payslip for december should be computed based on the total gross onss wage
of the quarter (in this case october + november + 13th month + december), minus
the CSSS already paid in october + november + 13th month
        ''')

        # just in case if the quarter payslips are incorrectly retrieved
        payslip_january = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2026, 1, 1),
            "date_to": date(2026, 1, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip_january.action_validate()
        wanted_csss_january = -(self._get_owed_csss(
            self._get_payslips_gross_onss_wage(payslip_january) * uplift,
            payslip_january.date_to,
            'single',
            'monthly',
        ))
        self.assertAlmostEqual(wanted_csss_january, self._get_payslips_csss(payslip_january), msg='''
The 13th month payslip seems to have affected the next year's payslips. This
should not happen as they don't belong in the same quarter.
        ''')

    def test_thirteen_month_last_payslip_of_quarter_special_social_contribution(self):
        """
        The 13th month payslip should close the quarter when the monthly
        payslip for the same month is already validated, regardless of the
        quarter in which the employee leaves.
        """
        employee = self.env['hr.employee'].create({
            'name': 'Test Employee',
            'contract_date_start': date(2025, 1, 1),
            'contract_date_end': date(2025, 9, 30),
            'wage_type': 'monthly',
            'wage': 3500,
            'l10n_be_joint_committee_id': self.cp200.id,
            'resource_calendar_id': self.resource_calendar_40.id,
            'l10n_be_worker_code_id': self.ordinary_worker_code.id,
        })
        uplift = 1.08

        # the employee worked up to the end of september, when
        # he leaves the company (third quarter's last month)
        payslip_july, payslip_august, payslip_september = self._generate_monthly_payslips_range(
            date(2025, 7, 1), date(2025, 9, 30), employee,
        )
        wanted_csss_july = -(self._get_owed_csss(
            self._get_payslips_gross_onss_wage(payslip_july) * uplift,
            payslip_july.date_to,
            'single',
            'monthly',
        ))
        wanted_csss_august = -(self._get_owed_csss(
            self._get_payslips_gross_onss_wage(payslip_august) * uplift,
            payslip_august.date_to,
            'single',
            'monthly',
        ))

        # the 13th month is generated after the monthly payslip of september
        # (the last month of the quarter), so it should close the quarter and
        # be computed with the quarterly rates
        payslip_13th_month = self.env['hr.payslip'].create({
            'version_id': employee.version_id.id,
            'date_from': date(2025, 9, 30),
            'date_to': date(2025, 9, 30),
            'employee_id': employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_thirteen_month').id,
        })
        payslip_13th_month.action_validate()
        quarter_wanted_csss = -(self._get_owed_csss(
            self._get_payslips_gross_onss_wage(payslip_july | payslip_august | payslip_september | payslip_13th_month) * uplift,
            payslip_13th_month.date_to,
            'single',
            'quarterly',
        ))
        wanted_csss_13th_month = quarter_wanted_csss - wanted_csss_july - wanted_csss_august \
            - self._get_payslips_csss(payslip_september)
        self.assertAlmostEqual(wanted_csss_13th_month, self._get_payslips_csss(payslip_13th_month), msg='''
When a 13th month payslip is generated after the monthly payslip closing the
quarter (here in september, not december), it should be computed using the
quarterly rates, based on the total gross wage of the quarter, minus the CSSS
already paid in july, august and september.
        ''')

    def test_simple_pay_in_csss_contribution(self):
        """
        When an employee is fired, the simple pay (simple pécule) of the
        termination holidays (N and N-1) should be taken in account for the
        CSSS computation
        """
        employee = self.env['hr.employee'].create({
            'name': 'Dr. Eggman',
            'contract_date_start': date(2024, 1, 1),
            'contract_date_end': date(2025, 5, 31),
            'wage_type': 'monthly',
            'wage': 4000,
            'l10n_be_joint_committee_id': self.cp200.id,
            'resource_calendar_id': self.resource_calendar_40.id,
            'l10n_be_worker_code_id': self.ordinary_employee_code.id,
        })

        # so that the holiday attests (n-1) has some value > 0
        self._generate_monthly_payslips_range(date(2024, 1, 1), date(2024, 12, 31), employee)

        payslip_april = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2025, 4, 1),
            "date_to": date(2025, 4, 30),
            "struct_id": self.cp200_struct.id,
        })
        payslip_april.action_validate()

        csss_april = -self._get_payslips_csss(payslip_april)
        expected_csss = self._get_owed_csss(employee.wage, payslip_april.date_to, "single", "monthly")
        self.assertAlmostEqual(expected_csss, csss_april, msg="A basic monthly CSSS test failed for april 2025")

        departure_holidays_n1 = self.env['hr.payslip'].create({
            'version_id': employee.version_id.id,
            'date_from': date(2025, 5, 1),
            'date_to': date(2025, 5, 31),
            'employee_id': employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n1_holidays').id,
        })
        # Employee can still use 20 days off this year, they will be given to
        # him as cash that is subject to the CSSS
        departure_holidays_n1.compute_sheet()
        departure_holidays_n1.action_validate()
        simple_pay_n1 = departure_holidays_n1.line_ids.filtered_domain([['code', '=', 'PAY_SIMPLE']]).total
        self.assertGreater(
            simple_pay_n1, 0,
            msg="""
Expected a non-zero PAY_SIMPLE on the departure holidays (N-1) payslip when
having used no holidays (all previous year has been prestated)
            """,
        )

        # departure holidays (N-1) is at the end of the contract, so it should
        # base its computation on all the quarter's payslips for the CSSS
        expected_csss = self._get_owed_csss(employee.wage + simple_pay_n1, departure_holidays_n1.date_to, "single", "quarterly")
        css_paid_for_quarter = -self._get_payslips_csss(payslip_april | departure_holidays_n1)
        self.assertAlmostEqual(
            expected_csss, css_paid_for_quarter,
            msg="The departure holidays (N-1) payslip should have its Special Social Contribution be computed with quarterly rates",
        )

        departure_holidays_n = self.env['hr.payslip'].create({
            'version_id': employee.version_id.id,
            'date_from': date(2025, 5, 1),
            'date_to': date(2025, 5, 31),
            'employee_id': employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n_holidays').id,
        })
        # Employee has gained the right to 10 days off next year, they will be
        # given to him as cash that is subject to the CSSS
        departure_holidays_n.compute_sheet()
        departure_holidays_n.action_validate()
        simple_pay_n = departure_holidays_n.line_ids.filtered_domain([['code', '=', 'PAY_SIMPLE']]).total
        self.assertGreater(
            simple_pay_n1, 0,
            msg="Expected a non-zero PAY_SIMPLE on the departure holidays (N) payslip when employee gained 10 days for next year",
        )

        # departure holidays (N) is at the end of the contract, so it should
        # base its computation on all the quarter's payslips for the CSSS
        expected_csss = self._get_owed_csss(employee.wage + simple_pay_n1 + simple_pay_n, departure_holidays_n1.date_to, "single", "quarterly")
        css_paid_for_quarter = -self._get_payslips_csss(payslip_april | departure_holidays_n1 | departure_holidays_n)
        self.assertAlmostEqual(
            expected_csss, css_paid_for_quarter,
            msg="The departure holidays (N) payslip should have its Special Social Contribution be computed with quarterly rates",
        )

        payslip_may = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2025, 5, 1),
            "date_to": date(2025, 5, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip_may.compute_sheet()
        payslip_may.action_validate()

        # the may payslip is quarterly since it's the last one of the contract
        csss_may = -self._get_payslips_csss(payslip_may)
        expected_csss = self._get_owed_csss(employee.wage * 2 + simple_pay_n1 + simple_pay_n, departure_holidays_n1.date_to, "single", "quarterly")
        expected_csss -= css_paid_for_quarter  # we have to deduce the advances of CSSS already paid during the quarter
        self.assertAlmostEqual(expected_csss, csss_may, msg="""
If the employee's contract ends on may the May payslip should:
- be based on a quarterly basis
- take in account the payslips of the quarter:
        - the May payslip's gross wage
        - the April payslip's gross wage
        - the simple pay of the departure holidays (N-1)
        - the simple pay of the departure holidays (N)
""",
        )

    def test_csss_notice_period_irc_no_notice_respect(self):
        """
        If the employee stops working, does not respect his notice period, then
        he should receive all of his notice salary when he stops working (irc).
        This irc is subject to the CSSS. But, the irc has to be split per
        quarter, then taxed per quarter using quarterly rates, the sum of the
        results being shown in the last payslip's M.ONSS field.
        """
        employee = self.env['hr.employee'].create({
            'name': 'Dr. Eggman',
            'contract_date_start': date(2020, 1, 1),
            'wage_type': 'monthly',
            'wage': 4000,
            'l10n_be_joint_committee_id': self.cp200.id,
            'resource_calendar_id': self.resource_calendar_40.id,
            'l10n_be_worker_code_id': self.ordinary_worker_code.id,
        })
        # employee is a worker (ouvrier). He will be subject to the 108% uplift
        # on all his ONSS-subject salaries during the computation
        uplift = 1.08

        # we need to generate payslips for the previous year up to now so that
        # the holiday attests (n-1) have some value, and at least one payslip is
        # in the quarter we will test to see if its CSSS is used in the
        # quarterly computation
        payslip_october = self._generate_monthly_payslips_range(date(2024, 1, 1), date(2025, 10, 31), employee)[-1]
        expected_october_csss = self._get_owed_csss(
            employee.wage * uplift, payslip_october.date_to,
            "single", "monthly",
        )
        october_csss = -payslip_october.line_ids.filtered_domain([['code', '=', 'M.ONSS']]).total
        self.assertAlmostEqual(expected_october_csss, october_csss, msg="""
A simple payslip for october failed to give the correct special social contribution
        """)

        departure = self.env['hr.employee.departure'].create({
            'departure_description': "Oh no you're fired",
            'employee_id': employee.id,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'dismissal_date': date(2025, 11, 12),  # wednesday
        })
        departure.l10n_be_notice_respect = 'without'

        # we have to compute/validate the payslips one by one, otherwise the CSS
        # might have wrongs values (it deducts the validated CSSS advances at
        # the time of the computation)
        termination_fees_payslip = self.env['hr.payslip'].browse(employee.action_generate_termination_payslip()['res_id'])
        termination_fees_payslip.compute_sheet()
        termination_fees_payslip.action_validate()
        irc_total_amount = termination_fees_payslip.line_ids.filtered_domain([['code', '=', 'TERM_SALARY']]).total

        # start and end of the unprestated notice period
        notice_start = employee.l10n_be_notice_period_start + relativedelta(days=1)
        notice_end = departure.l10n_be_notice_period_theoretical_end

        # Stop here if the notice period formulae ever changes
        self.assertGreater(notice_start, date(2025, 9, 30), msg="Expected notice period to begin in the 4th quarter of 2025")
        self.assertGreater(date(2026, 1, 1), notice_start, msg="Expected notice period to begin in the 4th quarter of 2025")
        self.assertGreater(notice_end, date(2025, 12, 31), msg="Expected notice period to end in the 1st quarter of 2026")
        self.assertGreater(date(2026, 4, 1), notice_end, msg="Expected notice period to end in the 1st quarter of 2026")

        unprestated_notice_hours = employee.version_id.resource_calendar_id.get_work_hours_count(notice_start, notice_end, compute_leaves=False)

        # let's divide the irc per quarter:
        work_hours_q4 = employee.version_id.resource_calendar_id.get_work_hours_count(notice_start, date(2025, 12, 31), compute_leaves=False)
        work_hours_q1 = employee.version_id.resource_calendar_id.get_work_hours_count(date(2026, 1, 1), notice_end, compute_leaves=False)
        irc_q4 = irc_total_amount * (work_hours_q4 / unprestated_notice_hours)
        irc_q1 = irc_total_amount * (work_hours_q1 / unprestated_notice_hours)

        # CSSS of termination fees is:
        # CSSS(gross revenue of q4) + (CSSS(gross revenue of quarter) for each next quarter of the notice period)
        total_wanted_csss = self._get_owed_csss(
            (employee.wage + irc_q4) * uplift,
            termination_fees_payslip.date_to,
            "single", "quarterly",
        )
        total_wanted_csss += self._get_owed_csss(irc_q1 * uplift, termination_fees_payslip.date_to, "single", "quarterly")

        expected_termination_fees_csss = round(total_wanted_csss - october_csss, 2)
        termination_fees_csss = -termination_fees_payslip.line_ids.filtered_domain([['code', '=', 'M.ONSS']]).total
        self.assertAlmostEqual(expected_termination_fees_csss, termination_fees_csss, msg="""
If the employee does not work during his notice period, then his IRC
(i.e.: TERM_SALARY line of his termination fees) should also be subject to the
Special Social Contribtion (CSSS), but, the amount must be split per quarter of
the unprestated notice and the CSSS tax must then be applied on each quarter.
        """)

        # let's test if the temrination holidays deduce the IRC as well
        # again, payslips must be validated/computed one by one
        holidays_salary = 0
        termination_holidays_payslips = self.env['hr.payslip'].search(employee.action_generate_termination_holidays()['domain'])
        for termination_holidays_payslip in termination_holidays_payslips:
            termination_holidays_payslip.compute_sheet()
            termination_holidays_payslip.action_validate()
            holidays_salary += termination_holidays_payslip.line_ids.filtered_domain([['code', '=', 'PAY_SIMPLE']]).total
        total_wanted_csss = self._get_owed_csss(
            (employee.wage + irc_q4) * uplift + holidays_salary,
            termination_fees_payslip.date_to,
            "single", "quarterly",
        )
        total_wanted_csss += self._get_owed_csss(irc_q1 * uplift, termination_fees_payslip.date_to, "single", "quarterly")
        termination_holidays_csss = -sum(termination_holidays_payslips.line_ids.filtered_domain([['code', '=', 'M.ONSS']]).mapped('total'))
        self.assertAlmostEqual(
            total_wanted_csss - october_csss - termination_fees_csss,
            termination_holidays_csss,
            msg="""
When computing the special social contribution of the temrination holidays, they
must deduce the CSSS of validated payslips/termination fees of the current quarter
        """)

    def test_csss_notice_period_irc_partial_notice_respect(self):
        """
        If the employee stops working, and works partially during his notice
        period, then he should receive the remaining of his notice salary when
        he stops working (irc).
        This irc is subject to the CSSS. But, the irc has to be split per
        quarter, then taxed per quarter using quarterly rates, the sum of the
        results being shown in the last payslip's M.ONSS field.
        """
        employee = self.env['hr.employee'].create({
            'name': 'Dr. Eggman',
            'contract_date_start': date(2020, 1, 1),
            'wage_type': 'monthly',
            'wage': 4000,
            'l10n_be_joint_committee_id': self.cp200.id,
            'resource_calendar_id': self.resource_calendar_40.id,
            'l10n_be_worker_code_id': self.ordinary_employee_code.id,
        })

        # we need to generate payslips for the previous year up to now so that
        # the holiday attests (n-1) have some value, and at least one payslip is
        # in the quarter we will test to see if its CSSS is used in the
        # quarterly computation
        payslip_october = self._generate_monthly_payslips_range(date(2024, 1, 1), date(2025, 10, 31), employee)[-1]

        departure = self.env['hr.employee.departure'].create({
            'departure_description': "Oh no you're fired",
            'employee_id': employee.id,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'dismissal_date': date(2025, 11, 12),  # wednesday
        })
        departure.l10n_be_notice_respect = 'partial'
        departure.departure_date = date(2025, 12, 18)  # stops working on thursday

        # we have to compute/validate the payslips one by one, otherwise the CSS
        # might have wrongs values (it deducts the validated CSSS advances at
        # the time of the computation)
        termination_fees_payslip = self.env['hr.payslip'].browse(employee.action_generate_termination_payslip()['res_id'])
        termination_fees_payslip.compute_sheet()
        termination_fees_payslip.action_validate()
        irc_total_amount = termination_fees_payslip.line_ids.filtered_domain([['code', '=', 'TERM_SALARY']]).total

        # same for here, payslips must be validated/computed one by one
        holidays_salary = 0
        termination_holidays_payslips = self.env['hr.payslip'].search(employee.action_generate_termination_holidays()['domain'])
        for termination_holidays_payslip in termination_holidays_payslips:
            termination_holidays_payslip.compute_sheet()
            termination_holidays_payslip.action_validate()
            holidays_salary += termination_holidays_payslip.line_ids.filtered_domain([['code', '=', 'PAY_SIMPLE']]).total

        # start and end of the unprestated notice period
        notice_start = departure.departure_date + relativedelta(days=1)
        notice_end = departure.l10n_be_notice_period_theoretical_end

        # Stop here if the notice period formulae ever changes
        self.assertGreater(notice_start, date(2025, 9, 30), msg="Expected notice period to begin in the 4th quarter of 2025")
        self.assertGreater(date(2026, 1, 1), notice_start, msg="Expected notice period to begin in the 4th quarter of 2025")
        self.assertGreater(notice_end, date(2025, 12, 31), msg="Expected notice period to end in the 1st quarter of 2026")
        self.assertGreater(date(2026, 4, 1), notice_end, msg="Expected notice period to end in the 1st quarter of 2026")

        unprestated_notice_hours = employee.version_id.resource_calendar_id.get_work_hours_count(notice_start, notice_end, compute_leaves=False)

        # Let's divide the irc per quarter:
        work_hours_q4 = employee.version_id.resource_calendar_id.get_work_hours_count(notice_start, date(2025, 12, 31), compute_leaves=False)
        work_hours_q1 = employee.version_id.resource_calendar_id.get_work_hours_count(date(2026, 1, 1), notice_end, compute_leaves=False)
        irc_q4 = irc_total_amount * (work_hours_q4 / unprestated_notice_hours)
        irc_q1 = irc_total_amount * (work_hours_q1 / unprestated_notice_hours)

        # CSSS of termination fees is:
        # CSSS(gross revenue of q4) + (CSSS(gross revenue of quarter) for each next quarter of the notice period)
        total_wanted_csss = self._get_owed_csss(
            # payslip october + simple holiday pay + temrination fees irc
            employee.wage + holidays_salary + irc_q4,
            termination_fees_payslip.date_to,
            "single", "quarterly",
        )
        total_wanted_csss += self._get_owed_csss(irc_q1, termination_fees_payslip.date_to, "single", "quarterly")

        total_csss = -sum((payslip_october | termination_fees_payslip | termination_holidays_payslips).line_ids.filtered_domain([['code', '=', 'M.ONSS']]).mapped('total'))
        self.assertAlmostEqual(total_wanted_csss, total_csss, msg="""
If the employee does not fully work during his notice period, then his IRC
(i.e.: TERM_SALARY line of his termination fees) should also be subject to the
Special Social Contribtion (CSSS), but, the amount must be split per quarter of
the unprestated notice and the CSSS tax must then be applied on each quarter.
""")

    def test_csss_notice_period_irc_full_notice_respect(self):
        """
        If the employee stops working, and works during his notice period, then
        all of his IRC (and thus the CSS of it) was already paid during his
        monthly fees. Since this employee is a worker, he gets no holiday pay
        from the employer (PAY_SIMPLE = 0), so the holiday attests must not add
        any extra CSSS on top of what the monthly payslips already owed.
        """
        employee = self.env['hr.employee'].create({
            'name': 'Dr. Eggman',
            'contract_date_start': date(2020, 1, 1),
            'wage_type': 'monthly',
            'wage': 4000,
            'l10n_be_joint_committee_id': self.cp200.id,
            'resource_calendar_id': self.resource_calendar_40.id,
            'l10n_be_worker_code_id': self.ordinary_worker_code.id,
        })
        # employee is a worker (ouvrier). He will be subject to the 108% uplift
        # on all his ONSS-subject salaries during the computation
        uplift = 1.08

        # so that the holiday attests (n-1) have some value
        self._generate_monthly_payslips_range(date(2025, 1, 1), date(2025, 12, 31), employee)

        # fire with full notice respect, employee will receive his IRC on a
        # month by month basis
        departure_notice = self.env['hr.employee.departure'].create({
            'employee_id': employee.id,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'dismissal_date': date(2025, 11, 12),  # wednesday
            'departure_description': "Oh no you're fired",
        })
        departure_notice.l10n_be_notice_respect = 'with'
        departure_notice.action_register()
        departure_payslips = departure_notice._generate_termination_holidays()
        departure_domain = [('id', 'in', departure_payslips.ids)]

        notice_start = departure_notice.l10n_be_notice_period_start
        notice_end = notice_start + relativedelta(weeks=departure_notice.l10n_be_notice_duration_week_after_2014)

        # Stop here if the notice period formulae ever changes
        self.assertGreater(notice_end, date(2026, 3, 1), msg="Expected notice period to end in march of 2026")
        self.assertGreater(date(2026, 3, 31), notice_end, msg="Expected notice period to end in march of 2026")

        # the payslips must be validated one by one, otherwise march's CSSS
        # computation would fail (as it won't see the jan and feb payslips as
        # validated)
        payslip_jan, payslip_feb, payslip_mar = self.env['hr.payslip'].create([
            {
                'name': "Payslip January Test",
                'employee_id': employee.id,
                'version_id': employee.version_id.id,
                "date_from": date(2026, 1, 1),
                "date_to": date(2026, 1, 31),
                "struct_id": self.cp200_struct.id,
            },
            {
                'name': "Payslip February Test",
                'employee_id': employee.id,
                'version_id': employee.version_id.id,
                "date_from": date(2026, 2, 1),
                "date_to": date(2026, 2, 28),
                "struct_id": self.cp200_struct.id,
            },
            {
                'name': "Payslip March Test",
                'employee_id': employee.id,
                'version_id': employee.version_id.id,
                "date_from": date(2026, 3, 1),
                "date_to": date(2026, 3, 31),
                "struct_id": self.cp200_struct.id,
            },
        ])
        payslip_jan.compute_sheet()
        payslip_jan.action_validate()
        payslip_feb.compute_sheet()
        payslip_feb.action_validate()
        payslip_mar.compute_sheet()
        payslip_mar.action_validate()
        monthly_wages = self._get_payslips_gross_onss_wage(payslip_jan | payslip_feb | payslip_mar)
        expected_csss = self._get_owed_csss(monthly_wages * uplift, payslip_mar.date_to, "single", "quarterly")
        already_paid_csss = -self._get_payslips_csss(payslip_jan | payslip_feb | payslip_mar)
        self.assertAlmostEqual(expected_csss, already_paid_csss, msg="A basic quarterly CSSS test failed for Q1 of 2026")

        # the employee finished his notice period. We can give him his
        # holiday pay

        holiday_attests_n = self.env['hr.payslip'].search(Domain.AND([
            departure_domain,
            Domain('employee_id', '=', employee.id),
            Domain('struct_id', '=', self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n_holidays').id),
        ]))
        holiday_attests_n._set_input_value('GROSS_REF', employee.wage)
        holiday_attests_n.compute_sheet()
        holiday_attests_n.action_validate()
        simple_pay_n = holiday_attests_n.line_ids.filtered_domain([['code', '=', 'PAY_SIMPLE']]).total
        self.assertEqual(
            simple_pay_n, 0,
            msg="""
Workers get no holiday pay from the employer (l10n_be_hr_payroll: PAY_SIMPLE is
forced to 0 for is_worker()), so the departure holidays (N) payslip should
carry no simple holiday pay at all.
            """,
        )
        quarter_onss_wage = monthly_wages * uplift + simple_pay_n
        expected_csss = self._get_owed_csss(quarter_onss_wage, payslip_mar.date_to, "single", "quarterly") - already_paid_csss
        holiday_n_csss = -self._get_payslips_csss(holiday_attests_n)
        self.assertAlmostEqual(expected_csss, holiday_n_csss, msg="""
Since the worker's holiday pay is zero, generating the holiday attests (for
Year N, current) must not add any extra CSSS (M.ONSS) on top of what the
quarter's validated monthly payslips already owed.
        """)

        already_paid_csss += holiday_n_csss

        # Holiday pay for next year's holidays worked. Now we will generate the
        # employee's holiday pay for the current year's holidays
        holiday_attests_n1 = self.env['hr.payslip'].search(Domain.AND([
            departure_domain,
            Domain('employee_id', '=', employee.id),
            Domain('struct_id', '=', self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n1_holidays').id),
        ]))
        holiday_attests_n1.compute_sheet()
        holiday_attests_n1.action_validate()
        simple_pay_n1 = holiday_attests_n1.line_ids.filtered_domain([['code', '=', 'PAY_SIMPLE']]).total
        self.assertEqual(
            simple_pay_n1, 0,
            msg="""
Workers get no holiday pay from the employer (l10n_be_hr_payroll: PAY_SIMPLE is
forced to 0 for is_worker()), so the departure holidays (N-1) payslip should
carry no simple holiday pay at all.
            """,
        )
        quarter_onss_wage += simple_pay_n1
        expected_csss = self._get_owed_csss(quarter_onss_wage, payslip_mar.date_to, "single", "quarterly") - already_paid_csss
        holiday_n1_csss = -self._get_payslips_csss(holiday_attests_n1)
        self.assertAlmostEqual(expected_csss, holiday_n1_csss, msg="""
Since the worker's holiday pay is zero, generating the holiday attests (for
Year N-1, current) must not add any extra CSSS (M.ONSS) on top of what the
quarter's validated monthly payslips and the (N) holiday attest already owed.
        """)

    def test_cp302_thirteen_month_special_social_contribution(self):
        """
        The thirteen month's payslip for the cp302 should also be counted, and
        compute the special social contribution (CSSS).
        This case is different because the cp302's 13th month is located on the
        same payslip as on the monthly payslip.
        """
        employee = self.env['hr.employee'].create({
            'name': 'Dr. Eggman',
            'contract_date_start': date(2025, 1, 1),
            'contract_date_end': False,
            'wage_type': 'monthly',
            'wage': 4000,
            'l10n_be_joint_committee_id': self.cp302.id,
            'resource_calendar_id': self.resource_calendar_40.id,
        })

        # we have to validate the following payslips one by one, otherwise
        # payslip_november won't know that there is a validated payslip in october
        payslip_october, payslip_november, payslip_december = self.env['hr.payslip'].create([
            {
                'name': "Payslip October Test",
                'employee_id': employee.id,
                'version_id': employee.version_id.id,
                "date_from": date(2025, 10, 1),
                "date_to": date(2025, 10, 31),
                "struct_id": self.cp200_struct.id,
            },
            {
                'name': "Payslip November Test",
                'employee_id': employee.id,
                'version_id': employee.version_id.id,
                "date_from": date(2025, 11, 1),
                "date_to": date(2025, 11, 30),
                "struct_id": self.cp200_struct.id,
            },
            {
                'name': "Payslip December Test",
                'employee_id': employee.id,
                'version_id': employee.version_id.id,
                "date_from": date(2025, 12, 1),
                "date_to": date(2025, 12, 31),
                "struct_id": self.cp200_struct.id,
            },
        ])
        payslip_october.action_validate()
        wanted_csss_october = -(self._get_owed_csss(
            self._get_payslips_gross_onss_wage(payslip_october),
            payslip_october.date_to,
            'single',
            'monthly',
        ))
        self.assertAlmostEqual(wanted_csss_october, self._get_payslips_csss(payslip_october), msg='''
Got an unexpected special social contribution value for a regular month (october)
        ''')
        payslip_november.action_validate()
        wanted_csss_november = -(self._get_owed_csss(
            self._get_payslips_gross_onss_wage(payslip_november),
            payslip_november.date_to,
            'single',
            'monthly',
        ))
        self.assertAlmostEqual(wanted_csss_november, self._get_payslips_csss(payslip_november), msg='''
Got an unexpected special social contribution value for a regular month (november)
        ''')
        payslip_december.action_validate()

        cp302_13th_month = payslip_december.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total

        self.assertGreater(cp302_13th_month, 0, msg="""
Expected employee with 1 year of seniority to have a 13th month under the cp302.
        """)

        quarter_wanted_csss = -(self._get_owed_csss(
            cp302_13th_month + self._get_payslips_gross_onss_wage(payslip_october | payslip_november | payslip_december),
            payslip_december.date_to,
            'single',
            'quarterly',
        ))
        wanted_csss_december = quarter_wanted_csss - wanted_csss_november - wanted_csss_october
        # the main difference between this test and the others is that here we
        self.assertAlmostEqual(wanted_csss_december, self._get_payslips_csss(payslip_december), msg='''
The payslip for december (Joint Committee 302) should be computed based on the
total gross onss wage of the quarter (in this case october + november
+ 13th month + december), minus the CSSS already paid in october + november
        ''')
