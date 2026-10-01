# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests import tagged
from odoo.fields import Command
from odoo.addons.hr_payroll.tests.common import TestPayrollBase
from odoo.addons.l10n_be_hr_payroll.tests.common import TestBelgiumCommon


@tagged('-at_install', 'post_install', 'post_install_l10n')
class TestPayslipValidationCp302(TestPayrollBase, TestBelgiumCommon):
    """
    All tests related to the payslips values under the Joint Committee 302
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.belgian_company = cls.env['res.company'].create({
            'name': 'Belgian Red Devils & Co',
            'country_id': cls.env.ref('base.be').id,
            'currency_id': cls.env.ref('base.EUR').id,
            'street': "Rue d'Enfer",
            'zip': '6666',
            'city': 'Tourinnes-Saint-Lambert',
        })
        cls.belgian_company.current_payroll_config_id.write({
            'l10n_be_employer_category_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_employer_category_00017').id
        })
        cls.env.user.company_ids |= cls.belgian_company
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.belgian_company.ids))

        cls.resource_calendar_38_hours_per_week = cls.env['resource.calendar'].create({
                'name': "Test Calendar : 38 Hours/Week",
                'company_id': cls.env.company.id,
                'hours_per_day': 7.6,
                'full_time_required_hours': 38.0,
                'attendance_ids': [Command.create({
                    'dayofweek': dayofweek,
                    'hour_from': hour_from,
                    'hour_to': hour_to,
                    'work_entry_type_id': cls.env.ref('hr_work_entry.be_work_entry_type_attendance').id
                }) for dayofweek, hour_from, hour_to in [
                    ("0", 8.0, 12.0),
                    ("0", 13.0, 16.6),
                    ("1", 8.0, 12.0),
                    ("1", 13.0, 16.6),
                    ("2", 8.0, 12.0),
                    ("2", 13.0, 16.6),
                    ("3", 8.0, 12.0),
                    ("3", 13.0, 16.6),
                    ("4", 8.0, 12.0),
                    ("4", 13.0, 16.6),
                ]],
            })

        cls._setup_common(
            country=cls.env.ref('base.be'),
            structure=cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary'),
            structure_type=cls.env.ref('hr.structure_type_employee_cp200'),
            tz='Europe/Brussels',
            resource_calendar=cls.resource_calendar_38_hours_per_week,
            version_fields={
                'contract_date_start': date(2018, 12, 31),
                'date_version': date(2018, 12, 31),
                'wage': 2650.0,
                'transport_mode_car': True,
                'fuel_card': 150.0,
                'internet': 38.0,
                'mobile': 30.0,
                'meal_voucher_amount': 7.45,
                'ip_wage_rate': 0.25,
                'l10n_be_lsa_monthly_pro_other_amount': 150,
                'eco_checks': 250,
                'l10n_be_joint_committee_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_302').id,
                'l10n_be_worker_code_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00015').id,
            },
            employee_fields={
                'distance_home_work': 75,
            },
        )

    def _create_worker(self, name, wage, **version_fields):
        worker = self.env['hr.employee'].sudo().create({
            'name': name,
            'resource_calendar_id': self.resource_calendar_38_hours_per_week.id,
            'company_id': self.env.company.id,
            'country_id': self.env.ref('base.be').id,
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'contract_date_start': date(2023, 1, 1),
            'date_version': date(2023, 1, 1),
            'wage': wage,
        }).sudo(False)
        worker.sudo().version_id.write({
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_302').id,
            'l10n_be_worker_code_id': self.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00015').id,
            **version_fields,
        })
        return worker

    def _generate_worker_termination_payslip(self, worker, departure_date, dismissal_date,
                                             reason_code=340):
        departure_reason = self.env['hr.departure.reason'].create({
            'name': 'Termination',
            'l10n_be_reason_code': reason_code,
        })
        departure = self.env['hr.employee.departure'].create({
            'employee_id': worker.id,
            'dismissal_date': dismissal_date,
            'departure_date': departure_date,
            'departure_reason_id': departure_reason.id,
            'departure_description': 'Worker termination test',
            'l10n_be_notice_respect': 'without',
        })
        departure.action_register()
        payslips = departure._generate_termination_payslip() + departure._generate_termination_holidays()
        termination_structure = self.env.ref(
            'l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_termination_fees',
        )
        termination_payslip = payslips.filtered(
            lambda payslip: payslip.struct_id == termination_structure,
        )
        self.assertTrue(termination_payslip, "Termination payslip should be generated")
        termination_payslip.compute_sheet()
        return departure, termination_payslip[0]

    def test_compute_cp302_professional_fees(self):
        """
        The flat_rate_professional_fees_max and rate rule parameter name are
        generated dynamically for the professional fees. Since they don't exist
        for the cp302, it should fall back to the cp200's values during the
        computation of regular payslips
        """
        payslip = self._generate_payslip(date_from=date(2025, 12, 1), date_to=date(2025, 12, 31))

        fees_max = payslip._rule_parameter('flat_rate_professional_fees_max_cp200')
        fees_rate = payslip._rule_parameter('flat_rate_professional_fees_rate_cp200')
        yearly_taxable = payslip.line_ids.filtered_domain([('code', '=', 'GROSS.Y')]).total
        expected_professional_fees = -min(yearly_taxable * fees_rate, fees_max)
        professional_fees = payslip.line_ids.filtered_domain([('code', '=', 'F_PROFESSIONAL_FEES')]).total
        self.assertAlmostEqual(round(expected_professional_fees, 2), professional_fees, msg="""
Since flat_rate_professional_fees_max_cp302 and flat_rate_professional_fees_rate_cp302
don't exist, the computation of the professional fees under the cp302 should fall back
to flat_rate_professional_fees_max_cp200 and flat_rate_professional_fees_rate_cp200
        """)

    def test_termination_fees_cp302_professional_fees(self):
        """
        The flat_rate_professional_fees_max and rate rule parameter name are
        generated dynamically for the professional fees. Since they don't exist
        for the cp302, it should fall back to the cp200's values during the
        computation of termination fees
        """
        departure_notice = self.env['hr.employee.departure'].create({
            'employee_id': self.employee.id,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'dismissal_date': date(2025, 12, 20),
            'l10n_be_notice_respect': 'without',
            'departure_description': "Oh no you're fired",
            'action_date': date(2025, 12, 21),
        })
        departure_notice.action_register()
        departure_payslips = departure_notice._generate_termination_payslip()
        departure_payslips += departure_notice._generate_termination_holidays()
        struct_id = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_termination_fees')
        termination_fees = departure_payslips.filtered(lambda dep: dep.struct_id == struct_id)
        termination_fees.compute_sheet()

        fees_max = termination_fees._rule_parameter('flat_rate_professional_fees_max_cp200')
        fees_rate = termination_fees._rule_parameter('flat_rate_professional_fees_rate_cp200')
        yearly_taxable = termination_fees.line_ids.filtered_domain([('code', '=', 'GROSS.Y')]).total
        expected_professional_fees = -min(yearly_taxable * fees_rate, fees_max)
        professional_fees = termination_fees.line_ids.filtered_domain([('code', '=', 'F_PROFESSIONAL_FEES')]).total

        self.assertAlmostEqual(round(expected_professional_fees, 2), professional_fees, msg="""
Since flat_rate_professional_fees_max_cp302 and flat_rate_professional_fees_rate_cp302
don't exist, the computation of the professional fees for termination fees under the cp302 should fall back
to flat_rate_professional_fees_max_cp200 and flat_rate_professional_fees_rate_cp200
        """)

    def test_eco_voucher_cp302_full_time_partial_year(self):
        """
        Full-time CP302 employee whose contract starts on 01/09/2025.
        December 2025 is the eco-voucher payment month for CP302,.
        Sep-Nov 2025 = 3 complete calendar months.
        Expected: 250 * 3/12 = 62.50 €
        """
        employee = self.env['hr.employee'].sudo().create({
            'name': 'BE Full-Time Eco Voucher Test',
            'resource_calendar_id': self.resource_calendar_38_hours_per_week.id,
            'company_id': self.env.company.id,
            'country_id': self.env.ref('base.be').id,
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'contract_date_start': date(2025, 9, 1),
            'date_version': date(2025, 9, 1),
            'wage': 2000.0,
        }).sudo(False)
        employee.sudo().version_id.write({
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_302').id,
            'l10n_be_worker_code_id': self.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00015').id,
        })

        payslip = self._generate_payslip(
            date_from=date(2025, 12, 1),
            date_to=date(2025, 12, 31),
            employee_id=employee.id,
            version_id=employee.version_id.id,
        )

        eco_voucher = payslip.line_ids.filtered_domain([('code', '=', 'ECOVOUCHERS')]).total
        self.assertAlmostEqual(eco_voucher, 250 * 3 / 12, places=2,
            msg="Full-time CP302 with 3 complete months should receive 250*3/12 = 62.50 €")

    def test_eco_voucher_cp302_part_time_single_month(self):
        """
        Part-time CP302 employee (19 h/week, Mon-Fri 5-day schedule) whose
        contract starts on 01/11/2025 with 100% attendance (no unpaid absences).
        November 2025 has 20 Mon-Fri working days (each day = 1 day regardless of hours worked).
        Expected: 250 * 20/260 ≈ 19.23 €
        """
        calendar_19h = self.env['resource.calendar'].create({
            'name': 'Test Calendar: 19h/Week (Mon-Fri)',
            'company_id': self.env.company.id,
            'full_time_required_hours': 38.0,
            'attendance_ids': [Command.create({
                'dayofweek': str(day),
                'hour_from': 8.0,
                'hour_to': 11.8,  # 3.8h * 5 days = 19h/week
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_attendance').id,
            }) for day in range(5)],
        })

        employee = self.env['hr.employee'].sudo().create({
            'name': 'BE Part-Time Eco Voucher Test',
            'resource_calendar_id': calendar_19h.id,
            'company_id': self.env.company.id,
            'country_id': self.env.ref('base.be').id,
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'contract_date_start': date(2025, 11, 1),
            'date_version': date(2025, 11, 1),
            'wage': 1000.0,
        }).sudo(False)
        employee.sudo().version_id.write({
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_302').id,
            'l10n_be_worker_code_id': self.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00015').id,
        })

        payslip = self._generate_payslip(
            date_from=date(2025, 12, 1),
            date_to=date(2025, 12, 31),
            employee_id=employee.id,
            version_id=employee.version_id.id,
        )

        # November 2025: 20 Mon-Fri working days (Nov 1 = Saturday, so first
        # working day is Nov 3; last is Nov 28).
        eco_voucher = payslip.line_ids.filtered_domain([('code', '=', 'ECOVOUCHERS')]).total
        self.assertAlmostEqual(eco_voucher, 250 * 20 / 260, places=2,
            msg="Part-time CP302 with 20 working days in Nov should receive 250*20/260 ≈ 19.23 €")

    def test_worker_termination_payslip_generation_conditions(self):
        """
        Verify that a termination payslip is generated for workers when:
        1. Worker does not have to work during notice period (l10n_be_notice_respect != 'with')
        2. Worker leaves not on the last day of the month
        3. End of year bonus has to be paid partially
        4. Eco vouchers are due
        """
        worker = self._create_worker('CP302 Worker Termination Test', 2500.0, eco_checks=250)
        _, payslip = self._generate_worker_termination_payslip(
            worker, date(2026, 7, 15), date(2026, 6, 15), reason_code=342,
        )

        nd_week = payslip._get_input_line_amount('ND_WEEK')
        nd_day = payslip._get_input_line_amount('ND_DAY')
        yearend_bonus = payslip._get_input_line_amount('YEAREND_BONUS')
        eco_voucher = payslip._get_input_line_amount('ECO_VOUCHER') or payslip.version_id.eco_checks

        self.assertGreater(nd_week, 0, "Should have notice weeks")
        self.assertGreater(nd_day, 0, "Should have remaining days (2026-07-15 is not end of month)")
        self.assertGreater(yearend_bonus, 0, "Should have a year-end bonus (fixed one month's wage)")
        self.assertEqual(eco_voucher, 250, "Should have eco vouchers configured")

        term_salary = payslip.line_ids.filtered(lambda line: line.code == 'TERM_SALARY')
        self.assertGreater(
            term_salary.total,
            0,
            "Termination salary should be calculated with weekly salary x notice weeks + daily salary x remaining days",
        )

    def test_worker_termination_fees_comprehensive_calculation(self):
        """
        Verify that worker termination fees include all required components,
        each computed as a plain yearly figure - the exact same formula used
        for employees:
        1. Base salary (contract_wage x 12.92)
        2. Benefits in kind (mobile phone, internet, laptop, etc.)
        3. End of year bonus (prorated per Joint Committee)
        4. Employer's hospitalization insurance contribution
        5. Eco-vouchers
        6. Company car benefit

        REFERENCE_SALARY_REVALUED is the single place where the yearly package
        is divided by 52 for workers (they are paid weekly, employees yearly).

        Formula: Weekly package (REFERENCE_SALARY_REVALUED) x Number of weeks
        = Gross Termination Fees

        MEAL_VOUCHER and PAY_VARIABLE_SALARY are intentionally not covered here -
        their worker-vs-employee treatment is still unconfirmed with the PO.
        """
        brand = self.env['fleet.vehicle.model.brand'].create({'name': 'Test Brand'})
        model = self.env['fleet.vehicle.model'].create({'brand_id': brand.id, 'name': 'Test Model'})
        car = self.env['fleet.vehicle'].create({
            'model_id': model.id,
            'license_plate': 'TEST-CP302-001',
            'company_id': self.env.company.id,
            'car_value': 25000.0,
            'fuel_type': 'diesel',
            'co2': 120.0,
            'co2_emission_unit': 'g/km',
            'acquisition_date': date(2022, 1, 1),
        })

        worker = self._create_worker(
            'Worker Full Benefits', 2600.0,
            internet=50.0, mobile=40.0, laptop=30.0, tablet=20.0,
            eco_checks=250, transport_mode_car=True, car_id=car.id,
            has_hospital_insurance=True, hospital_insurance_amount_per_adult=25.0,
        )

        car.driver_id = worker.work_contact_id.id

        version = worker.sudo().version_id
        self.env.flush_all()

        _, payslip = self._generate_worker_termination_payslip(
            worker, date(2026, 5, 1), date(2026, 3, 20),
        )

        hours_per_week = version.resource_calendar_id.hours_per_week
        normalized_wage = version._get_normalized_wage()

        cost_inflated_weekly_salary = normalized_wage * hours_per_week
        expected_basic2 = version._get_contract_wage() * 12.92

        basic_salary_line = payslip.line_ids.filtered(lambda line: line.code == 'BASIC2')
        self._validate_payslip(
            payslip,
            {'BASIC2': expected_basic2},
            skip_lines=True,
        )
        self.assertNotAlmostEqual(
            basic_salary_line.total, cost_inflated_weekly_salary, places=2,
            msg="BASIC2 must not equal normalized_wage x hours_per_week - that figure includes "
                "the employer's ONSS cost, not the worker's own gross wage.",
        )

        bik_lines = payslip.line_ids.filtered(lambda line: line.code == 'ADVANTAGE_ANY_KIND')
        self.assertGreater(bik_lines.total, 0, "Should include benefits in kind (mobile, internet, etc.)")

        eco_voucher_lines = payslip.line_ids.filtered(lambda line: line.code == 'ECO_VOUCHER')
        self.assertGreater(eco_voucher_lines.total, 0, "Should include eco-vouchers (weekly value)")

        car_benefit_lines = payslip.line_ids.filtered(lambda line: line.code == 'ATN_CAR_TERM')
        self.assertGreater(car_benefit_lines.total, 0, "Should include company car benefit (weekly value)")

        hospital_lines = payslip.line_ids.filtered(lambda line: line.code == 'HOSPITAL_INSURANCE')
        self.assertGreater(hospital_lines.total, 0, "Should include employer hospitalization insurance")

        yearend_bonus_lines = payslip.line_ids.filtered(lambda line: line.code == 'YEAREND_BONUS')
        self.assertGreater(yearend_bonus_lines.total, 0, "Should include the year-end bonus (fixed one month's wage)")

        term_salary = payslip.line_ids.filtered(lambda line: line.code == 'TERM_SALARY')
        self.assertGreater(term_salary.total, 0, "TERM_SALARY should be sum of all components")

        nd_week = payslip._get_input_line_amount('ND_WEEK')

        self.assertGreater(nd_week, 0, "Should have notice weeks")

        annual_salary_revalued_lines = payslip.line_ids.filtered(lambda line: line.code == 'REFERENCE_SALARY_REVALUED')
        self.assertGreater(annual_salary_revalued_lines.total, 0, "REFERENCE_SALARY_REVALUED should be > 0")

        expected_yearly_base = (
            basic_salary_line.total +
            bik_lines.total +
            yearend_bonus_lines.total +
            eco_voucher_lines.total +
            car_benefit_lines.total +
            hospital_lines.total
        )

        self.assertAlmostEqual(
            annual_salary_revalued_lines.total,
            expected_yearly_base / 52,
            places=2,
            msg="REFERENCE_SALARY_REVALUED must be the yearly package (sum of all benefit "
                "components, each computed the same way as for employees) divided by 52 for "
                "workers - that /52 is the only place the yearly-vs-weekly split happens now.",
        )

        self.assertGreater(
            term_salary.total,
            0,
            "Gross termination fees = Weekly salary x weeks + Daily salary x days",
        )

    def test_worker_termination_partial_weeks_calculation(self):
        """
        Verify that worker termination fees correctly handle partial weeks.
        When notice period does not correspond to whole weeks, the remaining days
        are paid at (REFERENCE_SALARY_REVALUED / 7) x remaining_days - i.e. the same
        full weekly package (base wage + eco-vouchers, bonuses, insurance, etc.)
        used for whole weeks, prorated to a daily rate. It must NOT fall back to
        base wage alone for the day remainder while whole weeks get the full package.
        """
        worker = self._create_worker('Worker Partial Weeks Test', 3040.0, eco_checks=250)

        _, payslip = self._generate_worker_termination_payslip(
            worker, date(2026, 5, 29), date(2026, 4, 6),
        )

        version = worker.sudo().version_id
        hours_per_week = version.resource_calendar_id.hours_per_week

        self.assertEqual(hours_per_week, 38.0, "Hours per week should be 38")

        nd_week = payslip._get_input_line_amount('ND_WEEK')
        nd_day = payslip._get_input_line_amount('ND_DAY')

        self.assertGreater(nd_week, 0, "Should have notice weeks")
        self.assertGreater(nd_day, 0, "Should have remaining days (not end of week)")

        annual_salary_revalued_line = payslip.line_ids.filtered(lambda line: line.code == 'REFERENCE_SALARY_REVALUED')
        weekly_package = annual_salary_revalued_line.total

        basic2_line = payslip.line_ids.filtered(lambda line: line.code == 'BASIC2')
        wage_only_daily_rate = (basic2_line.total / 52) / 7
        wage_and_benefits_daily_rate = weekly_package / 7

        self.assertGreater(
            wage_and_benefits_daily_rate, wage_only_daily_rate,
            "Weekly package (base wage + eco-vouchers) should exceed base wage alone, "
            "otherwise this test can't distinguish the fixed day-rate formula from a "
            "wage-only one.",
        )

        nd_week_line = payslip.line_ids.filtered(lambda line: line.code == 'ND_WEEK')
        nd_day_line = payslip.line_ids.filtered(lambda line: line.code == 'ND_DAY')

        self.assertGreater(
            nd_week_line.total,
            0,
            f"ND_WEEK total should be: weekly_salary x {nd_week} weeks",
        )

        self.assertAlmostEqual(
            nd_day_line.total,
            wage_and_benefits_daily_rate * nd_day,
            places=2,
            msg="ND_DAY should be (REFERENCE_SALARY_REVALUED / 7) x remaining days, "
                "so benefits like eco-vouchers are prorated into the day remainder too, "
                "not just the base wage.",
        )

        self.assertNotAlmostEqual(
            nd_day_line.total,
            wage_only_daily_rate * nd_day,
            places=2,
            msg="ND_DAY must not fall back to base-wage-only for the day remainder "
                "while ND_WEEK includes the full weekly package for whole weeks.",
        )

        term_salary = payslip.line_ids.filtered(lambda line: line.code == 'TERM_SALARY')

        expected_total = nd_week_line.total + nd_day_line.total
        self.assertAlmostEqual(
            term_salary.total,
            expected_total,
            places=2,
            msg=f"TERM_SALARY should be sum of weekly ({nd_week_line.total:.2f}) and daily ({nd_day_line.total:.2f}) = {expected_total:.2f}",
        )

        self.assertGreater(
            term_salary.total,
            0,
            "Gross termination fees = (weekly package x weeks) + (weekly package / 7 x remaining days)\n"
            f"= ({weekly_package:.2f} x {nd_week}) + ({wage_and_benefits_daily_rate:.2f} x {nd_day})\n"
            f"= {nd_week_line.total:.2f} + {nd_day_line.total:.2f}\n"
            f"= {term_salary.total:.2f}€",
        )
