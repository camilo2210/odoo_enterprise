from freezegun import freeze_time
from datetime import date

from unittest.mock import patch

from dateutil.relativedelta import relativedelta
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('-at_install', 'post_install', 'post_install_l10n', 'cp302_seniority')
class TestPayrollCP302(TransactionCase):
    freeze_time = freeze_time('2026-04-1')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.belgian_company = cls.env['res.company'].create({
            'name': 'Belgian CP302 CDI Test Co',
            'country_id': cls.env.ref('base.be').id,
            'currency_id': cls.env.ref('base.EUR').id,
        })
        cls.env.user.company_ids |= cls.belgian_company
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.belgian_company.ids))
        cls.env['l10n.be.joint.committee'].with_context(active_test=False).search([('egov3_code', '=', '302')]).write({'active': True})

    def _make_cp302_version(self, contract_date_start, category_id, employee_type_ref=None, wage_type='monthly', jc_id=None):
        """Create a minimal CP302 employee version starting on contract_date_start."""
        vals = {
            'name': 'CP302 Test Employee',
            'company_id': self.belgian_company.id,
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'date_version': contract_date_start,
            'contract_date_start': contract_date_start,
            'wage': 2000.0,
            'wage_type': wage_type,
            'l10n_be_joint_committee_id': jc_id or self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_302').id,
            'l10n_be_salary_scale_id': category_id,
        }
        if employee_type_ref:
            vals['employee_type_id'] = self.env.ref(employee_type_ref).id
        return self.env['hr.employee'].create(vals).version_id

    def _make_cp302_cdi_version(self, contract_date_start, category_id, wage_type='monthly'):
        """Create a CP302 CDI version (no employee type); in-position seniority equals time since start."""
        return self._make_cp302_version(contract_date_start, category_id, wage_type=wage_type)

    def _make_cp302_crew_version(self, contract_date_start, initial_category_id=None):
        """Create a CP302 CREW version; category is auto-managed by the compute method."""
        return self._make_cp302_version(
            contract_date_start,
            initial_category_id or self.env.ref('l10n_be_hr_payroll.cp302_5').id,
            employee_type_ref='l10n_be_hr_payroll.l10n_be_contract_type_crew',
        )

    def _make_cp302_temporary_version(self):
        """Create a CP302 Temporary version starting one month ago; seniority is driven by work entries."""
        return self._make_cp302_version(
            date.today() - relativedelta(months=1),
            self.env.ref('l10n_be_hr_payroll.cp302_5').id,
            employee_type_ref='l10n_be_hr_payroll.l10n_be_contract_type_temporary',
        )

    def _make_cp302_seasonal_version(self):
        """Create a CP302 Seasonal version starting one month ago; seniority is driven by work entries."""
        return self._make_cp302_version(
            date.today() - relativedelta(months=1),
            self.env.ref('l10n_be_hr_payroll.cp302_5').id,
            employee_type_ref='l10n_be_hr_payroll.l10n_be_contract_type_seasonal',
        )

    def _make_cp302_version_for_bridge(self, category_ref, years_in_position, wage_type='monthly', jc_ref='l10n_be_hr_payroll.l10n_be_joint_committee_302'):
        """Create a CP302 version back-dated by years_in_position + 6 months so CDI gates are cleared."""
        start = date.today() - relativedelta(years=years_in_position, months=6)
        return self._make_cp302_version(
            start,
            self.env.ref(category_ref).id,
            wage_type=wage_type,
            jc_id=self.env.ref(jc_ref).id,
        )

    def _apply_category_change(self, v1, new_category_ref, new_jc_ref=None):
        """End v1 yesterday and create a new version today with the given category, returning v2."""
        v1.contract_date_end = date.today() - relativedelta(days=1)
        new_vals = {
            'l10n_be_salary_scale_id': self.env.ref(new_category_ref).id,
            'date_version': date.today(),
            'contract_date_start': date.today(),
            'contract_date_end': False,
        }
        if new_jc_ref:
            new_vals['l10n_be_joint_committee_id'] = self.env.ref(new_jc_ref).id
        return v1.employee_id.create_version(new_vals)

    def _assert_temporary_seniority(self, work_entry_count, expected_years):
        """Create a temporary version, mock work-entry count, and assert seniority (months always 0)."""
        version = self._make_cp302_temporary_version()
        with patch.object(self.env.registry['hr.version'], '_get_work_entries_count', return_value=work_entry_count):
            version._compute_l10n_be_computed_seniority()
        self.assertEqual(version.l10n_be_computed_seniority_years, expected_years)
        self.assertEqual(version.l10n_be_computed_seniority_months, 0)

    def _assert_seasonal_seniority(self, work_entry_count, hours_per_week, hours_per_day, expected_years):
        """Create a seasonal version, mock work-entry count, and assert seniority (months always 0)."""
        version = self._make_cp302_seasonal_version()
        # a flexible calendar keeps whatever hours_per_week/hours_per_day it's given instead
        # of recomputing them from attendance lines, so the test can pin the values it needs
        version.resource_calendar_id = self.env['resource.calendar'].create({
            'name': 'CP302 Seasonal Test Calendar',
            'company_id': self.belgian_company.id,
            'calendar_type': 'undefined',
            'hours_per_week': hours_per_week,
            'hours_per_day': hours_per_day,
        })
        with patch.object(self.env.registry['hr.version'], '_get_work_entries_count', return_value=work_entry_count):
            version._compute_l10n_be_computed_seniority()
        self.assertEqual(version.l10n_be_computed_seniority_years, expected_years)
        self.assertEqual(version.l10n_be_computed_seniority_months, 0)

    def check_warnings(self, warning_ids, warning_name, expected_employee, assertion):
        warning = self._get_related_warning(warning_ids, warning_name)
        if not warning:
            self.assertFalse(assertion)
        elif not expected_employee:
            self.assertEqual(warning, [])
        else:
            self.assertEqual(expected_employee in warning['warning_records'], assertion)

    def _get_related_warning(self, warning_ids, warning_name):
        all_warnings = []
        for warning_id in warning_ids:
            warnings = self.env['hr.payroll.warning'].get_payroll_dashboard_warning_cards([warning_id])
            for warning in warnings:
                if warning['name'] == warning_name:
                    all_warnings.append(warning)
        return next(iter(all_warnings), None)

    def _has_min_wage_issue(self, version):
        version.invalidate_recordset(['issues'])
        issues = version.issues or {}
        return any(
            issue.get('action', {}).get('name') == 'adjust_wage_to_minimum_scale'
            for issue in issues.values()
        )

    # -------------------------------------------------------------------------
    # CDI seniority
    # -------------------------------------------------------------------------

    def test_cdi_less_than_6_months_seniority_is_0(self):
        """Below the 6-month threshold, computed seniority is 0."""
        version = self._make_cp302_cdi_version(date.today() - relativedelta(months=3), self.env.ref('l10n_be_hr_payroll.cp302_5').id)
        self.assertEqual(version.l10n_be_computed_seniority_years, 0)
        self.assertEqual(version.l10n_be_computed_seniority_months, 0)

    def test_cdi_exactly_6_months_seniority_jumps_to_1(self):
        """At 6 months in position, seniority jumps to 1 year and months are frozen at 0."""
        version = self._make_cp302_cdi_version(date.today() - relativedelta(months=7), self.env.ref('l10n_be_hr_payroll.cp302_5').id)
        self.assertEqual(version.l10n_be_computed_seniority_years, 1)
        self.assertEqual(version.l10n_be_computed_seniority_months, 0)

    def test_cdi_between_6_and_24_months_seniority_stays_1(self):
        """Within the 6-to-24-month window, seniority stays frozen at 1 year."""
        version = self._make_cp302_cdi_version(date.today() - relativedelta(months=18), self.env.ref('l10n_be_hr_payroll.cp302_5').id)
        self.assertEqual(version.l10n_be_computed_seniority_years, 1)
        self.assertEqual(version.l10n_be_computed_seniority_months, 0)

    def test_cdi_over_24_months_seniority_increases_normally(self):
        """After 2 full years, seniority tracks in_position_years + base (base = 0 here)."""
        version = self._make_cp302_cdi_version(date.today() - relativedelta(months=27), self.env.ref('l10n_be_hr_payroll.cp302_5').id)
        self.assertEqual(version.l10n_be_computed_seniority_years, 2)
        self.assertEqual(version.l10n_be_computed_seniority_months, version.l10n_be_in_position_months)

    # -------------------------------------------------------------------------
    # CREW seniority
    # -------------------------------------------------------------------------

    def test_crew_less_than_6_months_category_forced_to_3_seniority_0(self):
        """Below 6 months in position, CREW category is forced to cp302_3 and seniority is 0."""
        version = self._make_cp302_crew_version(date.today() - relativedelta(months=3))
        self.assertEqual(version.l10n_be_computed_seniority_years, 0)
        self.assertEqual(version.l10n_be_computed_seniority_months, 0)
        self.assertEqual(version.l10n_be_salary_scale_id, self.env.ref('l10n_be_hr_payroll.cp302_3'))

    def test_crew_at_6_months_promoted_to_category_4_seniority_1(self):
        """At 6 months, CREW category is promoted to cp302_4 and seniority is frozen at 1."""
        version = self._make_cp302_crew_version(date.today() - relativedelta(months=7))
        self.assertEqual(version.l10n_be_computed_seniority_years, 1)
        self.assertEqual(version.l10n_be_computed_seniority_months, 0)
        self.assertEqual(version.l10n_be_salary_scale_id, self.env.ref('l10n_be_hr_payroll.cp302_4'))

    def test_crew_over_24_months_seniority_increases_normally_no_category_change(self):
        """After 2 full years, CREW seniority tracks in_position_years and category stays at cp302_4."""
        version = self._make_cp302_crew_version(
            date.today() - relativedelta(months=27),
            initial_category_id=self.env.ref('l10n_be_hr_payroll.cp302_4').id,
        )
        self.assertEqual(version.l10n_be_computed_seniority_years, 2)
        self.assertEqual(version.l10n_be_computed_seniority_months, version.l10n_be_in_position_months)
        self.assertEqual(version.l10n_be_salary_scale_id, self.env.ref('l10n_be_hr_payroll.cp302_4'))

    # -------------------------------------------------------------------------
    # Temporary seniority (work-entry based thresholds)
    # -------------------------------------------------------------------------

    def test_temporary_below_130_entries_seniority_is_0(self):
        """Below 130 work entries, seniority is 0."""
        self._assert_temporary_seniority(work_entry_count=100, expected_years=0)

    def test_temporary_at_130_entries_seniority_is_1(self):
        """At 130 entries the first threshold is crossed, seniority becomes 1."""
        self._assert_temporary_seniority(work_entry_count=130, expected_years=1)

    def test_temporary_at_390_entries_seniority_is_2(self):
        """At 130 + 260 = 390 entries the second threshold is crossed, seniority becomes 2."""
        self._assert_temporary_seniority(work_entry_count=390, expected_years=2)

    def test_temporary_at_650_entries_seniority_is_3(self):
        """At 130 + 260 + 260 = 650 entries the third threshold is crossed, seniority becomes 3."""
        self._assert_temporary_seniority(work_entry_count=650, expected_years=3)

    # -------------------------------------------------------------------------
    # Seasonal seniority (schedule-dependent thresholds)
    # -------------------------------------------------------------------------

    def test_seasonal_5day_week_at_130_entries_seniority_is_1(self):
        """5-day/week schedule uses a 130-entry first threshold; at 130 entries seniority is 1."""
        self._assert_seasonal_seniority(work_entry_count=130, hours_per_week=38.0, hours_per_day=7.6, expected_years=1)

    def test_seasonal_6day_week_at_156_entries_seniority_is_1(self):
        """6-day/week schedule shifts the first threshold to 156; at 156 entries seniority is 1."""
        self._assert_seasonal_seniority(work_entry_count=156, hours_per_week=45.6, hours_per_day=7.6, expected_years=1)

    def test_seasonal_6day_week_at_468_entries_seniority_is_2(self):
        """6-day/week second threshold is 156 + 312 = 468; at 468 entries seniority is 2."""
        self._assert_seasonal_seniority(work_entry_count=468, hours_per_week=45.6, hours_per_day=7.6, expected_years=2)

    # -------------------------------------------------------------------------
    # Seniority bridge (salary scale change)
    # -------------------------------------------------------------------------

    def test_seniority_bridge_cat5_to_cat4_monthly_sets_base_seniority(self):
        """cat5->cat4 downgrade: base seniority is set to the first cat4 monthly entry >= cat5 wage at seniority 2.
        cp302_salary_scales['4']['monthly'][7] = 2905.08 is the first entry >= 2877.04, so base = 7."""
        v1 = self._make_cp302_version_for_bridge('l10n_be_hr_payroll.cp302_5', years_in_position=2, wage_type='monthly')
        self.assertEqual(v1.l10n_be_computed_seniority_years, 2)
        v2 = self._apply_category_change(v1, 'l10n_be_hr_payroll.cp302_4')
        self.assertEqual(v2.l10n_be_base_computed_seniority, 7)

    def test_seniority_bridge_cat5_to_cat6_monthly_sets_base_seniority(self):
        """cat5->cat6 transition: base seniority is set to the first cat6 monthly entry >= cat5 wage at seniority 10.
        cp302_salary_scales['6']['monthly'][4] = 3069.71 is the first entry >= 3056.62, so base = 4."""
        v1 = self._make_cp302_version_for_bridge('l10n_be_hr_payroll.cp302_5', years_in_position=10, wage_type='monthly')
        self.assertEqual(v1.l10n_be_computed_seniority_years, 10)
        v2 = self._apply_category_change(v1, 'l10n_be_hr_payroll.cp302_6')
        self.assertEqual(v2.l10n_be_base_computed_seniority, 4)

    def test_seniority_bridge_category_above_9_skips_bridge(self):
        """Categories above 9 have no seniority scale; base seniority stays 0 after the change."""
        v1 = self._make_cp302_version_for_bridge('l10n_be_hr_payroll.cp302_5', years_in_position=3)
        v2 = self._apply_category_change(v1, 'l10n_be_hr_payroll.cp302_cat_10')
        self.assertEqual(v2.l10n_be_base_computed_seniority, 0)

    def test_seniority_bridge_previous_cp200_no_bridge(self):
        """When the previous version is CP200, the bridge is skipped and base seniority stays 0."""
        v1 = self._make_cp302_version_for_bridge(
            'l10n_be_hr_payroll.cp200_b',
            years_in_position=3,
            jc_ref='l10n_be_hr_payroll.l10n_be_joint_committee_200',
        )
        v2 = self._apply_category_change(
            v1,
            'l10n_be_hr_payroll.cp302_5',
            new_jc_ref='l10n_be_hr_payroll.l10n_be_joint_committee_302',
        )
        self.assertEqual(v2.l10n_be_base_computed_seniority, 0)

    def test_seniority_bridge_uses_hourly_when_previous_cat_le_3(self):
        """When the previous category code is <= 3, the bridge uses the hourly scale regardless of wage_type.
        cat3 seniority 5 = 16.7318/h; first cat4 hourly entry >= that is [3] = 17.0347, so base = 3."""
        v1 = self._make_cp302_version_for_bridge('l10n_be_hr_payroll.cp302_3', years_in_position=5, wage_type='monthly')
        self.assertEqual(v1.l10n_be_computed_seniority_years, 5)
        v2 = self._apply_category_change(v1, 'l10n_be_hr_payroll.cp302_4')
        self.assertEqual(v2.l10n_be_base_computed_seniority, 3)

    # -------------------------------------------------------------------------
    # Wage adjustment and dashboard warnings
    # -------------------------------------------------------------------------

    def test_wage_under_category_minimum(self):
        """The issue action creates a new version at the monthly minimum wage."""
        version = self._make_cp302_cdi_version(date.today() - relativedelta(months=27), self.env.ref('l10n_be_hr_payroll.cp302_5').id)
        self.assertEqual(version.l10n_be_computed_seniority_years, 2)
        min_wage_cat5_2years = 2940.02
        original_start = version.contract_date_start
        dashboard_data = self.env['hr.payroll.warning'].get_payroll_dashboard_data()['warning_ids']
        self.check_warnings(dashboard_data, 'Employees Under Minimum Wage', version.employee_id, True)
        self.assertTrue(self._has_min_wage_issue(version))
        version.employee_id.adjust_wage_to_minimum_scale(min_wage_cat5_2years, 'monthly', version.l10n_be_computed_seniority_years, is_cp302=True)
        new_version = version.employee_id.version_ids.sorted('date_version', reverse=True)[0]
        self.assertNotEqual(new_version.id, version.id)
        self.assertEqual(new_version.wage, min_wage_cat5_2years)
        self.assertEqual(new_version.contract_date_start, original_start)
        dashboard_data = self.env['hr.payroll.warning'].get_payroll_dashboard_data()['warning_ids']
        self.check_warnings(dashboard_data, 'Employees Under Minimum Wage', version.employee_id, False)
        self.assertFalse(self._has_min_wage_issue(new_version))

    def test_cp302_above_minimum_scale_no_warning(self):
        """cat5 CDI at seniority 2 with wage exactly at 2940.02 must not appear in the minimum wage warning or issue."""
        version = self._make_cp302_cdi_version(
            date.today() - relativedelta(months=27),
            self.env.ref('l10n_be_hr_payroll.cp302_5').id,
        )
        self.assertEqual(version.l10n_be_computed_seniority_years, 2)
        version.wage = 2940.02
        dashboard_data = self.env['hr.payroll.warning'].get_payroll_dashboard_data()['warning_ids']
        self.check_warnings(dashboard_data, 'Employees Under Minimum Wage', version.employee_id, False)
        self.assertFalse(self._has_min_wage_issue(version))

    def test_adjust_wage_hourly_cp302_creates_new_version_with_correct_wage(self):
        """For cat1 (always hourly), the action sets hourly_wage to the scale minimum on a new version within the active contract.
        cat1 at seniority 2: cp302_salary_scales['1']['hourly'][2] = 16.21"""
        version = self._make_cp302_cdi_version(
            date.today() - relativedelta(months=28),
            self.env.ref('l10n_be_hr_payroll.cp302_1').id,
            wage_type='hourly',
        )
        self.assertEqual(version.l10n_be_computed_seniority_years, 2)
        min_wage_cat1_2years = 16.21
        original_start = version.contract_date_start
        dashboard_data = self.env['hr.payroll.warning'].get_payroll_dashboard_data()['warning_ids']
        self.check_warnings(dashboard_data, 'Employees Under Minimum Wage', version.employee_id, True)
        self.assertTrue(self._has_min_wage_issue(version))
        version.employee_id.adjust_wage_to_minimum_scale(min_wage_cat1_2years, 'hourly', version.l10n_be_computed_seniority_years, is_cp302=True)
        new_version = version.employee_id.version_ids.sorted('date_version', reverse=True)[0]
        self.assertNotEqual(new_version.id, version.id)
        self.assertEqual(new_version.hourly_wage, min_wage_cat1_2years)
        self.assertEqual(new_version.contract_date_start, original_start)
        dashboard_data = self.env['hr.payroll.warning'].get_payroll_dashboard_data()['warning_ids']
        self.check_warnings(dashboard_data, 'Employees Under Minimum Wage', version.employee_id, False)
        self.assertFalse(self._has_min_wage_issue(new_version))

    # -------------------------------------------------------------------------
    # _get_seniority_change_date for CP302 CDI (time-based)
    # -------------------------------------------------------------------------

    def _adjusted_start(self, contract_date_start):
        """Return the adjusted start date as computed by _difference_years_months."""
        if contract_date_start.day != 1:
            return (contract_date_start + relativedelta(months=1)).replace(day=1)
        return contract_date_start

    def test_seniority_change_date_cdi_seniority_0_returns_false(self):
        """CP302 CDI with seniority 0 (< 6 months in position): change date is False."""
        version = self._make_cp302_cdi_version(
            date.today() - relativedelta(months=3),
            self.env.ref('l10n_be_hr_payroll.cp302_5').id,
        )
        self.assertEqual(version.l10n_be_computed_seniority_years, 0)
        self.assertFalse(version._get_seniority_change_date())

    def test_seniority_change_date_cdi_seniority_1_is_adjusted_start_plus_6_months(self):
        """CP302 CDI seniority 1 (6-month trigger): change date = adjusted_start + 6 months."""
        contract_date_start = date.today() - relativedelta(months=7)
        version = self._make_cp302_cdi_version(contract_date_start, self.env.ref('l10n_be_hr_payroll.cp302_5').id)
        self.assertEqual(version.l10n_be_computed_seniority_years, 1)
        expected = self._adjusted_start(contract_date_start) + relativedelta(months=6)
        self.assertEqual(version._get_seniority_change_date(), expected)

    def test_seniority_change_date_cdi_seniority_2_is_adjusted_start_plus_2_years(self):
        """CP302 CDI seniority 2 (normal annual increment): change date = adjusted_start + 2 years."""
        contract_date_start = date.today() - relativedelta(months=27)
        version = self._make_cp302_cdi_version(contract_date_start, self.env.ref('l10n_be_hr_payroll.cp302_5').id)
        self.assertEqual(version.l10n_be_computed_seniority_years, 2)
        expected = self._adjusted_start(contract_date_start) + relativedelta(years=2)
        self.assertEqual(version._get_seniority_change_date(), expected)

    def test_seniority_change_date_cdi_seniority_5_is_adjusted_start_plus_5_years(self):
        """CP302 CDI seniority 5 years: change date = adjusted_start + 5 years."""
        contract_date_start = date.today() - relativedelta(years=5, months=6)
        version = self._make_cp302_cdi_version(contract_date_start, self.env.ref('l10n_be_hr_payroll.cp302_5').id)
        self.assertEqual(version.l10n_be_computed_seniority_years, 5)
        expected = self._adjusted_start(contract_date_start) + relativedelta(years=5)
        self.assertEqual(version._get_seniority_change_date(), expected)

    def test_seniority_change_date_cdi_with_base_seniority_zero_in_position(self):
        """With base_seniority > 0 and no time in new position (in_position = 0),
        change date falls back to adjusted_start of the current version."""
        # cat5->cat4 bridge: base_seniority becomes 7, in_position_years starts at 0
        v1 = self._make_cp302_version_for_bridge('l10n_be_hr_payroll.cp302_5', years_in_position=2, wage_type='monthly')
        v2 = self._apply_category_change(v1, 'l10n_be_hr_payroll.cp302_4')
        self.assertEqual(v2.l10n_be_base_computed_seniority, 7)
        # in_position = 0 (just created today) → in_position_at_change = seniority - base <= 0
        change_date = v2._get_seniority_change_date()
        expected = self._adjusted_start(v2.contract_date_start)
        self.assertEqual(change_date, expected, "Must return adjusted_start, which is the 1st of the current month")

    # -------------------------------------------------------------------------
    # _get_seniority_change_date for CP302 Temporary (work-entry based)
    # -------------------------------------------------------------------------

    def test_seniority_change_date_temporary_seniority_0_returns_false(self):
        """CP302 Temporary with seniority 0: change date is False (no threshold crossed)."""
        version = self._make_cp302_temporary_version()
        with patch.object(self.env.registry['hr.version'], '_get_work_entries_count', return_value=100):
            version._compute_l10n_be_computed_seniority()
        self.assertEqual(version.l10n_be_computed_seniority_years, 0)
        self.assertFalse(version._get_seniority_change_date())

    def test_seniority_change_date_temporary_seniority_1_is_130th_entry_date(self):
        """CP302 Temporary seniority 1: change date is the date of the 130th work entry (index 129)."""
        version = self._make_cp302_temporary_version()
        with patch.object(self.env.registry['hr.version'], '_get_work_entries_count', return_value=130):
            version._compute_l10n_be_computed_seniority()
        self.assertEqual(version.l10n_be_computed_seniority_years, 1)

        start = date(2025, 1, 1)
        fake_entries = [{'date': start + relativedelta(days=i)} for i in range(200)]
        with patch.object(self.env.registry['hr.version'], 'generate_work_entries', return_value=fake_entries):
            result = version._get_seniority_change_date()
        self.assertEqual(result, fake_entries[129]['date'])  # index = first_threshold - 1 = 129

    def test_seniority_change_date_temporary_seniority_2_is_390th_entry_date(self):
        """CP302 Temporary seniority 2: change date is the date of the 390th work entry (index 389)."""
        version = self._make_cp302_temporary_version()
        with patch.object(self.env.registry['hr.version'], '_get_work_entries_count', return_value=390):
            version._compute_l10n_be_computed_seniority()
        self.assertEqual(version.l10n_be_computed_seniority_years, 2)

        start = date(2025, 1, 1)
        fake_entries = [{'date': start + relativedelta(days=i)} for i in range(400)]
        with patch.object(self.env.registry['hr.version'], 'generate_work_entries', return_value=fake_entries):
            result = version._get_seniority_change_date()
        # index = first_threshold + (seniority - 1) * subsequent_threshold - 1 = 130 + 260 - 1 = 389
        self.assertEqual(result, fake_entries[389]['date'])

    # -------------------------------------------------------------------------
    # adjust_wage_to_minimum_scale - seniority change date integration
    # -------------------------------------------------------------------------

    def test_adjust_wage_new_version_dated_at_seniority_change_date(self):
        """When no version exists after the seniority change date, a new version is
        created with date_version equal to the computed seniority change date."""
        contract_date_start = date.today() - relativedelta(months=27)
        version = self._make_cp302_cdi_version(contract_date_start, self.env.ref('l10n_be_hr_payroll.cp302_5').id)
        self.assertEqual(version.l10n_be_computed_seniority_years, 2)

        expected_change_date = version._get_seniority_change_date()
        self.assertTrue(expected_change_date)

        min_wage = 2877.04
        version.employee_id.adjust_wage_to_minimum_scale(min_wage, 'monthly', 2, is_cp302=True)

        new_version = version.employee_id.version_ids.sorted('date_version', reverse=True)[0]
        self.assertNotEqual(new_version.id, version.id)
        self.assertEqual(new_version.date_version, expected_change_date)
        self.assertEqual(new_version.wage, min_wage)

    def test_adjust_wage_updates_later_version_when_one_exists_after_change_date(self):
        """When a version already exists after the seniority change date, adjust_wage
        updates that later version's wage instead of creating a new one."""
        contract_date_start = date.today() - relativedelta(months=27)
        version = self._make_cp302_cdi_version(contract_date_start, self.env.ref('l10n_be_hr_payroll.cp302_5').id)
        self.assertEqual(version.l10n_be_computed_seniority_years, 2)

        seniority_change_date = version._get_seniority_change_date()
        self.assertTrue(seniority_change_date)

        later_version = version.employee_id.create_version({
            'date_version': date.today(),
            'contract_date_start': version.contract_date_start,
            'contract_date_end': False,
            'wage': 2500.0,
        })
        version.employee_id.version_id = later_version
        initial_version_count = len(version.employee_id.version_ids)

        min_wage = 2877.04
        version.employee_id.adjust_wage_to_minimum_scale(min_wage, 'monthly', 2, is_cp302=True)

        self.assertEqual(len(version.employee_id.version_ids), initial_version_count)
        self.assertEqual(later_version.wage, min_wage)
