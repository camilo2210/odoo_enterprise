# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from freezegun import freeze_time
from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon
from odoo.addons.l10n_be_hr_payroll.tests.common import TestBelgiumCommon
from odoo.tests import tagged
from odoo.tools import float_round


@tagged('post_install_l10n', 'post_install', '-at_install', 'apprenticeship')
class TestApprenticeshipMinWage(TestPayslipValidationCommon, TestBelgiumCommon):
    """
    Test minimum wage calculations for all apprenticeship contract types
    as defined in Section 9 - FORMATIONS PERMANENTES DES CLASSES MOYENNES
    (Tableau E - prestations sociales et plafonds divers, updated 01.04.2026)
    """

    @classmethod
    @TestPayslipValidationCommon.setup_country('be')
    def setUpClass(cls):
        super().setUpClass()

        cls.env.user.group_ids |= cls.env.ref('hr.group_hr_user') | cls.env.ref('hr_payroll.group_hr_payroll_user')

        # Reference RMMM (Revenu Minimum Mensuel Moyen) as of 01/04/2026
        with freeze_time('2026-04-01'):
            cls.RMMM = cls.env['hr.rule.parameter']._get_parameter_from_code('l10n_be_apprenticeship_min_wage_ref', raise_if_not_found=False)

        # Create employee type for apprenticeship
        cls.employee_type_apprenticeship = cls.env.ref('hr.contract_type_apprenticeship')

    def _create_apprentice(self, birthday, contract_start, apprenticeship_type, apprenticeship_subtype=False, has_certificate=False):
        """Helper to create an apprentice employee with contract"""
        employee = self.env['hr.employee'].create({
            'name': 'Jean-Pol Apprenticeship',
            'birthday': birthday,
            'certificate': 'bachelor' if has_certificate else False,
            'company_id': self.env.company.id,
            'date_version': contract_start,
            'contract_date_start': contract_start,
            'wage': 0,
            'employee_type_id': self.employee_type_apprenticeship.id,
            'l10n_be_apprenticeship_contract_type': apprenticeship_type,
            'l10n_be_apprenticeship_contract_number': 'TEST123',
        })

        version = employee.version_id
        if apprenticeship_subtype:
            version.l10n_be_apprenticeship_contract_subtype = apprenticeship_subtype

        return employee, version

    # =====================================================================
    # 9.1 - APPRENTIS AGRÉÉS (Approved Apprentices - Middle Classes Training)
    # =====================================================================
    @freeze_time('2026-03-15')  # First half of year (month <= 6)
    def test_approved_apprentice_year1_first_half(self):
        """
        Test approved apprentice - 1st year, first half (Jan-Jun)
        Expected: 478,37 € (from Communauté germanophone 2026)
        """
        _employee, version = self._create_apprentice(
            birthday='2010-01-01',
            contract_start='2026-01-01',
            apprenticeship_type='approved',
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        self.assertAlmostEqual(min_wage, 478.37, places=2, msg="Approved apprentice 1st year (first half) minimum wage incorrect")

    @freeze_time('2026-09-15')  # Second half of year (month > 6)
    def test_approved_apprentice_year1_second_half(self):
        """
        Test approved apprentice - 1st year, second half (Jul-Dec)
        Expected: 418,57 € (from Communauté germanophone 2026)
        """
        _employee, version = self._create_apprentice(
            birthday='2010-01-01',
            contract_start='2026-01-01',
            apprenticeship_type='approved',
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        self.assertAlmostEqual(min_wage, 418.57, places=2, msg="Approved apprentice 1st year (second half) minimum wage incorrect")

    @freeze_time('2027-03-15')
    def test_approved_apprentice_year2_first_half(self):
        """
        Test approved apprentice - 2nd year, first half
        Expected: 717,56 € (from Communauté germanophone 2026)
        """
        _employee, version = self._create_apprentice(
            birthday='2009-01-01',
            contract_start='2026-01-01',
            apprenticeship_type='approved',
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        self.assertAlmostEqual(min_wage, 717.56, places=2, msg="Approved apprentice 2nd year (first half) minimum wage incorrect")

    @freeze_time('2027-09-15')
    def test_approved_apprentice_year2_second_half(self):
        """
        Test approved apprentice - 2nd year, second half
        Expected: 538,17 € (from Communauté germanophone 2026)
        """
        _employee, version = self._create_apprentice(
            birthday='2009-01-01',
            contract_start='2026-01-01',
            apprenticeship_type='approved',
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        self.assertAlmostEqual(min_wage, 538.17, places=2, msg="Approved apprentice 2nd year (second half) minimum wage incorrect")

    @freeze_time('2028-03-15')
    def test_approved_apprentice_year3_first_half(self):
        """
        Test approved apprentice - 3rd year, first half
        Expected: 837,15 € (from Communauté germanophone 2026)
        """
        _employee, version = self._create_apprentice(
            birthday='2008-01-01',
            contract_start='2026-01-01',
            apprenticeship_type='approved',
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        self.assertAlmostEqual(min_wage, 837.15, places=2, msg="Approved apprentice 3rd year (first half) minimum wage incorrect")

    @freeze_time('2028-09-15')
    def test_approved_apprentice_year3_second_half(self):
        """
        Test approved apprentice - 3rd year, second half
        Expected: 777,35 € (from Communauté germanophone 2026)
        """
        _employee, version = self._create_apprentice(
            birthday='2008-01-01',
            contract_start='2026-01-01',
            apprenticeship_type='approved',
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        self.assertAlmostEqual(min_wage, 777.35, places=2, msg="Approved apprentice 3rd year (second half) minimum wage incorrect")

    @freeze_time('2029-03-15')
    def test_approved_apprentice_year4(self):
        """
        Test approved apprentice - 4th year
        Expected: 837,15 € (from Communauté germanophone 2026)
        """
        _employee, version = self._create_apprentice(
            birthday='2007-01-01',
            contract_start='2026-01-01',
            apprenticeship_type='approved',
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        self.assertAlmostEqual(min_wage, 837.15, places=2, msg="Approved apprentice 4th year minimum wage incorrect")

    # =====================================================================
    # 9.2 - STAGIAIRES EN FORMATION DE CHEF D'ENTREPRISE
    # (Business Manager Trainees)
    # =====================================================================
    @freeze_time('2026-04-15')
    def test_business_manager_new_with_certificate_year1(self):
        """
        Test business manager trainee (new regime, with certificate) - 1st year
        For contracts starting after 01.09.2023 (Wallonia) or 01.09.2024 (Brussels)
        Expected: 1.017,39 € (46.46% of RMMM = 46.46% of 2189.81)
        """
        _employee, version = self._create_apprentice(
            birthday='2000-01-01',
            contract_start='2026-01-01',
            apprenticeship_type='business_manager',
            has_certificate=True,
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        expected_wage = float_round(0.4646 * self.RMMM, 2)
        self.assertAlmostEqual(min_wage, expected_wage, places=2, msg="Business manager trainee (new, with cert) year 1 minimum wage incorrect")

    @freeze_time('2027-04-15')
    def test_business_manager_new_with_certificate_year2_plus(self):
        """
        Test business manager trainee (new regime, with certificate) - 2nd+ years
        Expected: 1.202,42 € (54.91% of RMMM = 54.91% of 2189.81)
        """
        _employee, version = self._create_apprentice(
            birthday='2000-01-01',
            contract_start='2026-01-01',
            apprenticeship_type='business_manager',
            has_certificate=True,
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        expected_wage = float_round(0.5491 * self.RMMM, 2)
        self.assertAlmostEqual(min_wage, expected_wage, places=2, msg="Business manager trainee (new, with cert) year 2+ minimum wage incorrect")

    @freeze_time('2026-04-15')
    def test_business_manager_new_no_certificate_year1(self):
        """
        Test business manager trainee (new regime, no certificate) - 1st year
        Expected: 700,74 € (32% of RMMM = 32% of 2189.81)
        """
        _employee, version = self._create_apprentice(
            birthday='2000-01-01',
            contract_start='2026-01-01',
            apprenticeship_type='business_manager',
            has_certificate=False,
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        expected_wage = float_round(0.32 * self.RMMM, 2)
        self.assertAlmostEqual(min_wage, expected_wage, places=2, msg="Business manager trainee (new, no cert) year 1 minimum wage incorrect")

    @freeze_time('2027-04-15')
    def test_business_manager_new_no_certificate_year2(self):
        """
        Test business manager trainee (new regime, no certificate) - 2nd year
        Expected: 1.017,39 € (46.46% of RMMM)
        """
        _employee, version = self._create_apprentice(
            birthday='2000-01-01',
            contract_start='2026-01-01',
            apprenticeship_type='business_manager',
            has_certificate=False,
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        expected_wage = float_round(0.4646 * self.RMMM, 2)
        self.assertAlmostEqual(min_wage, expected_wage, places=2, msg="Business manager trainee (new, no cert) year 2 minimum wage incorrect")

    @freeze_time('2028-04-15')
    def test_business_manager_new_no_certificate_year3(self):
        """
        Test business manager trainee (new regime, no certificate) - 3rd year
        Expected: 1.202,42 € (54.91% of RMMM)
        """
        _employee, version = self._create_apprentice(
            birthday='2000-01-01',
            contract_start='2026-01-01',
            apprenticeship_type='business_manager',
            has_certificate=False,
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        expected_wage = float_round(0.5491 * self.RMMM, 2)
        self.assertAlmostEqual(min_wage, expected_wage, places=2, msg="Business manager trainee (new, no cert) year 3 minimum wage incorrect")

    # =====================================================================
    # 9.3 - CONVENTION D'APPRENTISSAGE INDUSTRIEL
    # (Industrial Apprenticeship Agreement)
    # =====================================================================
    @freeze_time('2026-04-15')
    def test_industrial_apprentice_age_15(self):
        """
        Test industrial apprenticeship - age 15
        Expected: 700,74 € (64% of 50% of RMMM = 64% of 1094.91)
        """
        _employee, version = self._create_apprentice(
            birthday='2011-01-01',  # Will be 15 in 2026
            contract_start='2026-01-01',
            apprenticeship_type='industrial',
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        expected_wage = float_round(0.64 * 0.5, 2) * self.RMMM
        self.assertAlmostEqual(min_wage, expected_wage, places=2, msg="Industrial apprentice age 15 minimum wage incorrect")

    @freeze_time('2026-04-15')
    def test_industrial_apprentice_age_16(self):
        """
        Test industrial apprenticeship - age 16
        Expected: 766,44 € (70% of 50% of RMMM)
        """
        _employee, version = self._create_apprentice(
            birthday='2010-01-01',  # Will be 16 in 2026
            contract_start='2026-01-01',
            apprenticeship_type='industrial',
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        expected_wage = float_round(0.70 * 0.5, 2) * self.RMMM
        self.assertAlmostEqual(min_wage, expected_wage, places=2, msg="Industrial apprentice age 16 minimum wage incorrect")

    @freeze_time('2026-04-15')
    def test_industrial_apprentice_age_17(self):
        """
        Test industrial apprenticeship - age 17
        Expected: 832,12 € (76% of 50% of RMMM)
        """
        _employee, version = self._create_apprentice(
            birthday='2009-01-01',  # Will be 17 in 2026
            contract_start='2026-01-01',
            apprenticeship_type='industrial',
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        expected_wage = float_round(0.76 * 0.5, 2) * self.RMMM
        self.assertAlmostEqual(min_wage, expected_wage, places=2, msg="Industrial apprentice age 17 minimum wage incorrect")

    @freeze_time('2026-04-15')
    def test_industrial_apprentice_age_18(self):
        """
        Test industrial apprenticeship - age 18
        Expected: 897,83 € (82% of 50% of RMMM)
        """
        _employee, version = self._create_apprentice(
            birthday='2008-01-01',  # Will be 18 in 2026
            contract_start='2026-01-01',
            apprenticeship_type='industrial',
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        expected_wage = float_round(0.82 * 0.5, 2) * self.RMMM
        self.assertAlmostEqual(min_wage, expected_wage, places=2, msg="Industrial apprentice age 18 minimum wage incorrect")

    @freeze_time('2026-04-15')
    def test_industrial_apprentice_age_19(self):
        """
        Test industrial apprenticeship - age 19
        Expected: 963,52 € (88% of 50% of RMMM)
        """
        _employee, version = self._create_apprentice(
            birthday='2007-01-01',  # Will be 19 in 2026
            contract_start='2026-01-01',
            apprenticeship_type='industrial',
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        expected_wage = float_round(0.88 * 0.5, 2) * self.RMMM
        self.assertAlmostEqual(min_wage, expected_wage, places=2, msg="Industrial apprentice age 19 minimum wage incorrect")

    @freeze_time('2026-04-15')
    def test_industrial_apprentice_age_20(self):
        """
        Test industrial apprenticeship - age 20
        Expected: 1.029,22 € (94% of 50% of RMMM)
        """
        _employee, version = self._create_apprentice(
            birthday='2006-01-01',  # Will be 20 in 2026
            contract_start='2026-01-01',
            apprenticeship_type='industrial',
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        expected_wage = float_round(0.94 * 0.5, 2) * self.RMMM
        self.assertAlmostEqual(min_wage, expected_wage, places=2, msg="Industrial apprentice age 20 minimum wage incorrect")

    @freeze_time('2026-04-15')
    def test_industrial_apprentice_age_21_plus(self):
        """
        Test industrial apprenticeship - age 21 or more
        Expected: 1.094,91 € (100% of 50% of RMMM)
        """
        _employee, version = self._create_apprentice(
            birthday='2004-01-01',  # Will be 22 in 2026
            contract_start='2026-01-01',
            apprenticeship_type='industrial',
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        expected_wage = float_round(1.00 * 0.5 * self.RMMM, 2)
        self.assertAlmostEqual(min_wage, expected_wage, places=2, msg="Industrial apprentice age 21+ minimum wage incorrect")

    # =====================================================================
    # 9.4 - CONVENTION D'IMMERSION PROFESSIONNELLE
    # (Professional Immersion Agreement)
    # =====================================================================
    @freeze_time('2026-04-15')
    def test_professional_immersion_age_15(self):
        """
        Test professional immersion - age 15
        Expected: 700,80 € (64% of 50% of RMMM, rounded to 0.1)
        """
        _employee, version = self._create_apprentice(
            birthday='2011-01-01',
            contract_start='2026-01-01',
            apprenticeship_type='professional_immersion',
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        # Rounded to nearest 10 cents
        self.assertAlmostEqual(min_wage, 700.80, places=1, msg="Professional immersion age 15 minimum wage incorrect")

    @freeze_time('2026-04-15')
    def test_professional_immersion_age_16(self):
        """
        Test professional immersion - age 16
        Expected: 766,50 € (70% of 50% of RMMM, rounded to 0.1)
        """
        _employee, version = self._create_apprentice(
            birthday='2010-01-01',
            contract_start='2026-01-01',
            apprenticeship_type='professional_immersion',
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        self.assertAlmostEqual(min_wage, 766.50, places=1, msg="Professional immersion age 16 minimum wage incorrect")

    @freeze_time('2026-04-15')
    def test_professional_immersion_age_17(self):
        """
        Test professional immersion - age 17
        Expected: 832,20 € (76% of 50% of RMMM, rounded to 0.1)
        """
        _employee, version = self._create_apprentice(
            birthday='2009-01-01',
            contract_start='2026-01-01',
            apprenticeship_type='professional_immersion',
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        self.assertAlmostEqual(min_wage, 832.20, places=1, msg="Professional immersion age 17 minimum wage incorrect")

    @freeze_time('2026-04-15')
    def test_professional_immersion_age_18(self):
        """
        Test professional immersion - age 18
        Expected: 897,90 € (82% of 50% of RMMM, rounded to 0.1)
        """
        _employee, version = self._create_apprentice(
            birthday='2008-01-01',
            contract_start='2026-01-01',
            apprenticeship_type='professional_immersion',
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        self.assertAlmostEqual(min_wage, 897.90, places=1, msg="Professional immersion age 18 minimum wage incorrect")

    @freeze_time('2026-04-15')
    def test_professional_immersion_age_19(self):
        """
        Test professional immersion - age 19
        Expected: 963,60 € (88% of 50% of RMMM, rounded to 0.1)
        """
        _employee, version = self._create_apprentice(
            birthday='2007-01-01',
            contract_start='2026-01-01',
            apprenticeship_type='professional_immersion',
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        self.assertAlmostEqual(min_wage, 963.60, places=1, msg="Professional immersion age 19 minimum wage incorrect")

    @freeze_time('2026-04-15')
    def test_professional_immersion_age_20(self):
        """
        Test professional immersion - age 20
        Expected: 1.029,30 € (94% of 50% of RMMM, rounded to 0.1)
        """
        _employee, version = self._create_apprentice(
            birthday='2006-01-01',
            contract_start='2026-01-01',
            apprenticeship_type='professional_immersion',
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        self.assertAlmostEqual(min_wage, 1029.30, places=1, msg="Professional immersion age 20 minimum wage incorrect")

    @freeze_time('2026-04-15')
    def test_professional_immersion_age_21_plus(self):
        """
        Test professional immersion - age 21 or more
        Expected: 1.095,00 € (100% of 50% of RMMM, rounded to 0.1)
        """
        _employee, version = self._create_apprentice(
            birthday='2004-01-01',
            contract_start='2026-01-01',
            apprenticeship_type='professional_immersion',
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        self.assertAlmostEqual(min_wage, 1095.00, places=1, msg="Professional immersion age 21+ minimum wage incorrect")

    # =====================================================================
    # 9.5 - DUAAL LEREN (Dual Learning - Flemish Region & Brussels)
    # =====================================================================
    @freeze_time('2026-04-15')
    def test_dual_learning_level_no_secondary_2(self):
        """
        Test dual learning - did not complete 2nd degree secondary education
        Expected: 635,10 € (29% of RMMM)
        """
        _employee, version = self._create_apprentice(
            birthday='2008-01-01',
            contract_start='2026-01-01',
            apprenticeship_type='dual_learning',
            apprenticeship_subtype='basic',
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        expected_wage = float_round(0.29 * self.RMMM, 2)
        self.assertAlmostEqual(min_wage, expected_wage, places=2, msg="Dual learning (no 2nd degree) minimum wage incorrect")

    @freeze_time('2026-04-15')
    def test_dual_learning_level_year1_or_has_secondary_2(self):
        """
        Test dual learning - completed 1st training year or has 2nd degree
        Expected: 700,80 € (32% of RMMM)
        """
        _employee, version = self._create_apprentice(
            birthday='2008-01-01',
            contract_start='2026-01-01',
            apprenticeship_type='dual_learning',
            apprenticeship_subtype='intermediate',
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        expected_wage = float_round(0.32 * self.RMMM, 2)
        self.assertAlmostEqual(min_wage, expected_wage, places=2, msg="Dual learning (year 1 or 2nd degree) minimum wage incorrect")

    @freeze_time('2026-04-15')
    def test_dual_learning_level_year2_or_qualification(self):
        """
        Test dual learning - completed 2nd training year, 1st year 3rd degree,
        or qualification phase special education
        Expected: 755,50 € (34.5% of RMMM)
        """
        _employee, version = self._create_apprentice(
            birthday='2008-01-01',
            contract_start='2026-01-01',
            apprenticeship_type='dual_learning',
            apprenticeship_subtype='advanced',
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        expected_wage = float_round(0.345 * self.RMMM, 2)
        self.assertAlmostEqual(min_wage, expected_wage, places=2, msg="Dual learning (year 2 or qualification) minimum wage incorrect")

    # =====================================================================
    # 9.6 - CONTRAT D'ALTERNANCE (Work-Study Contract - Walloon Region & Brussels)
    # =====================================================================
    @freeze_time('2026-04-15')
    def test_work_study_level_a(self):
        """
        Test work-study contract - Level A
        Expected: 372,27 € (17% of RMMM)
        """
        _employee, version = self._create_apprentice(
            birthday='2008-01-01',
            contract_start='2026-01-01',
            apprenticeship_type='work_study',
            apprenticeship_subtype='basic',
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        expected_wage = float_round(0.17 * self.RMMM, 2)
        self.assertAlmostEqual(min_wage, expected_wage, places=2, msg="Work-study Level A minimum wage incorrect")

    @freeze_time('2026-04-15')
    def test_work_study_level_b(self):
        """
        Test work-study contract - Level B
        Expected: 525,55 € (24% of RMMM)
        """
        _employee, version = self._create_apprentice(
            birthday='2008-01-01',
            contract_start='2026-01-01',
            apprenticeship_type='work_study',
            apprenticeship_subtype='intermediate',
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        expected_wage = float_round(0.24 * self.RMMM, 2)
        self.assertAlmostEqual(min_wage, expected_wage, places=2, msg="Work-study Level B minimum wage incorrect")

    @freeze_time('2026-04-15')
    def test_work_study_level_c(self):
        """
        Test work-study contract - Level C
        Expected: 700,74 € (32% of RMMM)
        """
        _employee, version = self._create_apprentice(
            birthday='2008-01-01',
            contract_start='2026-01-01',
            apprenticeship_type='work_study',
            apprenticeship_subtype='advanced',
        )

        min_wage, wage_type, _ = version._get_l10n_be_min_wage()
        self.assertEqual(wage_type, 'monthly')
        expected_wage = float_round(0.32 * self.RMMM, 2)
        self.assertAlmostEqual(min_wage, expected_wage, places=2,
                              msg="Work-study Level C minimum wage incorrect")

    # =====================================================================
    # EDGE CASES AND CROSS-CHECKS
    # =====================================================================
    @freeze_time('2026-04-15')
    def test_apprentice_without_type_returns_zero(self):
        """Test that an apprentice without a valid type returns 0 minimum wage"""
        employee = self.env['hr.employee'].create({
            'name': 'Invalid Apprentice',
            'birthday': '2008-01-01',
            'country_id': self.env.ref('base.be').id,
            'contract_date_start': '2026-01-01',
            'date_version': '2026-01-01',
            'wage': 0,
            'employee_type_id': self.employee_type_apprenticeship.id,
            'l10n_be_apprenticeship_contract_number': 'TEST123',
        })

        version = employee.version_id

        min_wage, _, _ = version._get_l10n_be_min_wage()
        self.assertEqual(min_wage, 0, msg="Apprentice without type should return 0 minimum wage")

    @freeze_time('2026-04-15')
    def test_training_years_calculation(self):
        """Test that training years are calculated correctly from first contract date"""
        _employee, version = self._create_apprentice(
            birthday='2008-01-01',
            contract_start='2024-01-01',  # Started 2 years ago
            apprenticeship_type='approved',
        )

        training_years = version._get_apprenticeship_years(date(2026, 4, 15))
        self.assertEqual(training_years, 3,
                        msg="Training years calculation incorrect")

    @freeze_time('2026-12-15')  # Second half of year
    def test_approved_apprentice_half_year_switch(self):
        """
        Test that approved apprentice wages switch correctly at mid-year
        (tests the month <= 6 vs month > 6 logic)
        """
        _employee, version = self._create_apprentice(
            birthday='2010-01-01',
            contract_start='2026-01-01',
            apprenticeship_type='approved',
        )

        min_wage, _, _ = version._get_l10n_be_min_wage()
        # In December (month > 6), should use second half rate
        self.assertAlmostEqual(min_wage, 418.57, places=2,
                              msg="Approved apprentice should use second half rate in December")

    @freeze_time('2026-06-30')  # Last day of first half
    def test_approved_apprentice_june_30(self):
        """Test June 30 (month <= 6) uses first half rate"""
        _employee, version = self._create_apprentice(
            birthday='2010-01-01',
            contract_start='2026-01-01',
            apprenticeship_type='approved',
        )

        min_wage, _, _ = version._get_l10n_be_min_wage()
        self.assertAlmostEqual(min_wage, 478.37, places=2,
                              msg="June 30 should use first half rate")

    @freeze_time('2026-07-01')  # First day of second half
    def test_approved_apprentice_july_1(self):
        """Test July 1 (month > 6) uses second half rate"""
        _employee, version = self._create_apprentice(
            birthday='2010-01-01',
            contract_start='2026-01-01',
            apprenticeship_type='approved',
        )

        min_wage, _, _ = version._get_l10n_be_min_wage()
        self.assertAlmostEqual(min_wage, 418.57, places=2,
                              msg="July 1 should use second half rate")
