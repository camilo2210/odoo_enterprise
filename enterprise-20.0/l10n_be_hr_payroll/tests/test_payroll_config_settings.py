# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from freezegun import freeze_time
from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import TestBelgiumCommon


@tagged('post_install_l10n', 'post_install', '-at_install', 'payroll_config_settings')
class TestL10nBePayrollConfigSettings(TestBelgiumCommon):
    """Belgian specific tests for the versioned ``payroll.config.settings`` model.

    Only the configuration model itself is exercised here (constraints, computed
    and related fields, versioning). The effect of the configuration on payslips
    and on ``hr.version`` is tested in ``test_l10n_be_hr_payroll_account``.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.be_company = cls.env['res.company'].create({
            'name': 'BE Config Test Company',
            'country_id': cls.env.ref('base.be').id,
        })
        cls.config = cls.be_company.current_payroll_config_id
        cls.category_00010 = cls.env.ref('l10n_be_hr_payroll.l10n_be_employer_category_00010')

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    def test_company_number_valid(self):
        """A well formed company number (10 digits, 0/1 prefix, valid checksum) is accepted."""
        self.config.l10n_be_company_number = '0477472701'
        self.assertEqual(self.config.l10n_be_company_number, '0477472701')

        # The company number must be exactly 10 digits long.
        with self.assertRaises(ValidationError):
            self.config.l10n_be_company_number = '047747270'

        # The company number must start with 0 or 1.
        with self.assertRaises(ValidationError):
            self.config.l10n_be_company_number = '2477472701'

        # The company number must have a valid checksum (modulo 97 equals 0).
        with self.assertRaises(ValidationError):
            self.config.l10n_be_company_number = '0477472702'

    def test_onss_registration_number_valid(self):
        """A 9-digit number whose value mod 97 equals 96 is accepted."""
        self.config.onss_registration_number = '125482497'
        self.assertEqual(self.config.onss_registration_number, '125482497')

        # The ONSS registration number must be exactly 9 digits long.
        with self.assertRaises(ValidationError):
            self.config.onss_registration_number = '12548249'

        # The ONSS Checksum must be valid (modulo 97 equals 96).
        with self.assertRaises(ValidationError):
            self.config.onss_registration_number = '125482498'

    def test_hospital_insurance_contribution_negative(self):
        """The hospital insurance employee contribution cannot be negative (DB CHECK)."""
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            self.config.hospital_insurance_employee_contribution = -1
            self.config.flush_recordset()

    # ------------------------------------------------------------------
    # Computed / related fields
    # ------------------------------------------------------------------
    def test_allowed_joint_committee_with_category(self):
        """With an employer category, the allowed committees are the category's ones."""
        self.config.l10n_be_employer_category_id = self.category_00010
        self.assertEqual(
            self.config.allowed_joint_committee_ids,
            self.category_00010.allowed_joint_committee_ids,
        )

    def test_allowed_joint_committee_without_category(self):
        """Without an employer category, every selectable committee is allowed."""
        self.config.l10n_be_employer_category_id = False
        self.assertEqual(
            self.config.allowed_joint_committee_ids,
            self.env['l10n.be.joint.committee'].with_context(active_test=False).search([('selectable', '=', True)]),
        )

    def test_employer_category_related_fields(self):
        """Code and allowed worker codes are mirrored from the employer category."""
        self.config.l10n_be_employer_category_id = self.category_00010
        self.assertEqual(self.config.l10n_be_employer_category_code, self.category_00010.egov3_code)
        self.assertEqual(
            self.config.l10n_be_allowed_worker_code_ids,
            self.category_00010.allowed_worker_code_ids,
        )

    # ------------------------------------------------------------------
    # Versioning
    # ------------------------------------------------------------------
    def test_be_fields_resolved_by_date(self):
        """``_get_payroll_config(date)`` returns the date-effective version with its BE values."""
        self.config.write({
            'date_version': date(2020, 1, 1),
            'l10n_be_revenue_code': '1111',
        })
        new_config = self.env['payroll.config.settings'].create({
            'company_id': self.be_company.id,
            'date_version': date(2023, 1, 1),
            'l10n_be_revenue_code': '2222',
        })

        self.assertEqual(
            self.be_company._get_payroll_config(date(2022, 12, 31)).l10n_be_revenue_code,
            '1111',
        )
        self.assertEqual(
            self.be_company._get_payroll_config(date(2023, 1, 1)).l10n_be_revenue_code,
            '2222',
        )
        self.assertEqual(
            self.be_company._get_payroll_config(date(2024, 6, 1)),
            new_config,
        )

    @freeze_time("2023-03-15")
    def test_copy_carries_be_fields(self):
        """Copying a configuration keeps the Belgian fields."""
        self.config.write({
            'date_version': date(2020, 1, 1),
            'l10n_be_employer_category_id': self.category_00010.id,
            'l10n_be_revenue_code': '1293',
            'l10n_be_ffe_employer_type': 'B',
        })
        copy = self.config.copy()
        self.assertNotEqual(copy.date_version, self.config.date_version)
        self.assertEqual(copy.date_version, date(2023, 3, 1))
        self.assertEqual(copy.l10n_be_employer_category_id, self.category_00010)
        self.assertEqual(copy.l10n_be_revenue_code, '1293')
        self.assertEqual(copy.l10n_be_ffe_employer_type, 'B')

    # ------------------------------------------------------------------
    # Side effects
    # ------------------------------------------------------------------
    def test_employer_category_change_triggers_onss_cron(self):
        """Setting the employer category schedules the ONSS rates fetch cron."""
        cron = self.env.ref('l10n_be_hr_payroll.ir_cron_fetch_onss_rates')
        triggers_before = self.env['ir.cron.trigger'].search_count([('cron_id', '=', cron.id)])
        self.config.l10n_be_employer_category_id = self.category_00010
        self.env.flush_all()
        triggers_after = self.env['ir.cron.trigger'].search_count([('cron_id', '=', cron.id)])
        self.assertGreater(triggers_after, triggers_before)

    def test_subcompany_inherits_company_level_fields(self):
        """Company payroll fields are inherited by a subcompany that hasn't set its own."""
        self.be_company.write({
            'first_payrun_date': date(2024, 1, 1),
        })
        self.config.write({
            'onss_registration_number': '125482497',
            'l10n_be_revenue_code': 'RC001',
            'l10n_be_ffe_employer_type': 'B',
            'onss_importance_code': '3',
            'l10n_be_sector': 'private',
            'l10n_be_declaration_frequency': 'quarterly',
            'hospital_insurance_amount_child': 15.0,
            'hospital_insurance_amount_adult': 25.0,
            'hospital_insurance_employee_contribution': 5.0,
            'ambulatory_insurance_amount_child': 8.0,
            'ambulatory_insurance_amount_adult': 12.0,
            'l10n_be_in_difficulty': True,
            'l10n_be_at_risk_groups_contribution': True,
            'l10n_be_ipa_reduction': True,
        })

        sub = self.env['res.company'].create({
            'name': 'BE Branch - Company Fields',
            'country_id': self.env.ref('base.be').id,
            'parent_id': self.be_company.id,
        })
        self.assertEqual(sub.first_payrun_date, date(2024, 1, 1))

        sub_config = sub.current_payroll_config_id
        self.assertEqual(sub_config.parent_id, self.config)
        self.assertEqual(sub_config.onss_registration_number, '125482497')
        self.assertEqual(sub_config.l10n_be_revenue_code, 'RC001')
        self.assertEqual(sub_config.l10n_be_ffe_employer_type, 'B')
        self.assertEqual(sub_config.onss_importance_code, '3')
        self.assertEqual(sub_config.l10n_be_sector, 'private')
        self.assertEqual(sub_config.l10n_be_declaration_frequency, 'quarterly')
        self.assertAlmostEqual(sub_config.hospital_insurance_amount_child, 15.0)
        self.assertAlmostEqual(sub_config.hospital_insurance_amount_adult, 25.0)
        self.assertAlmostEqual(sub_config.hospital_insurance_employee_contribution, 5.0)
        self.assertAlmostEqual(sub_config.ambulatory_insurance_amount_child, 8.0)
        self.assertAlmostEqual(sub_config.ambulatory_insurance_amount_adult, 12.0)
        self.assertTrue(sub_config.l10n_be_in_difficulty)
        self.assertTrue(sub_config.l10n_be_at_risk_groups_contribution)
        self.assertTrue(sub_config.l10n_be_ipa_reduction)

    def test_parent_config_update_propagates_to_unset_children(self):
        """Writing a shared field on a parent config propagates the value to child configs that haven't set their own."""
        sub = self.env['res.company'].create({
            'name': 'BE Branch - Propagation',
            'country_id': self.env.ref('base.be').id,
            'parent_id': self.be_company.id,
        })
        sub_config = sub.current_payroll_config_id
        self.assertFalse(sub_config.l10n_be_revenue_code)
        self.config.write({'l10n_be_revenue_code': 'RC002'})
        self.assertEqual(sub_config.l10n_be_revenue_code, 'RC002')

    def test_new_parent_version_creates_branch_version_same_date(self):
        """Creating a new version for a parent company also creates a branch version at the same date."""
        self.config.date_version = date(2024, 1, 1)
        sub = self.env['res.company'].create({
            'name': 'BE Branch - Version Sync',
            'country_id': self.env.ref('base.be').id,
            'parent_id': self.be_company.id,
        })
        sub_config = sub.current_payroll_config_id
        sub_config.date_version = date(2024, 1, 1)

        vals = self.config.copy_data(default={
            'company_id': self.be_company.id,
            'date_version': date(2025, 1, 1),
        })[0]
        vals['l10n_be_revenue_code'] = 'RC100'
        new_parent_config = self.env['payroll.config.settings'].create(vals)

        new_branch_config = sub._get_payroll_config(date(2025, 1, 1))
        self.assertEqual(new_branch_config.company_id, sub)
        self.assertEqual(new_branch_config.date_version, date(2025, 1, 1))
        self.assertEqual(new_branch_config.parent_id, new_parent_config)

    def test_new_branch_version_keeps_overrides_on_branch_editable_fields(self):
        """Branch-editable fields keep branch overrides, while non-editable fields follow parent changes."""
        self.config.write({
            'date_version': date(2024, 1, 1),
            'l10n_be_revenue_code': 'RC001',
            'employee_accident_insurance_name': 'Parent Previous Insurance',
            'employee_accident_insurance_number': 'P-001',
        })

        sub = self.env['res.company'].create({
            'name': 'BE Branch - Override Carry Over',
            'country_id': self.env.ref('base.be').id,
            'parent_id': self.be_company.id,
        })
        previous_branch_config = sub.current_payroll_config_id
        previous_branch_config.write({
            'date_version': date(2024, 1, 1),
            'employee_accident_insurance_name': 'Branch Custom Insurance',
            # Keep this one aligned with parent previous value to verify it follows parent new value.
            'employee_accident_insurance_number': 'P-001',
        })

        vals = self.config.copy_data(default={
            'company_id': self.be_company.id,
            'date_version': date(2025, 1, 1),
        })[0]
        vals.update({
            'l10n_be_revenue_code': 'RC999',
            'employee_accident_insurance_name': 'Parent New Insurance',
            'employee_accident_insurance_number': 'P-999',
        })
        self.env['payroll.config.settings'].create(vals)

        new_branch_config = sub._get_payroll_config(date(2025, 1, 1))
        self.assertEqual(new_branch_config.date_version, date(2025, 1, 1))
        self.assertEqual(new_branch_config.l10n_be_revenue_code, 'RC999')
        self.assertEqual(new_branch_config.employee_accident_insurance_name, 'Branch Custom Insurance')
        self.assertEqual(new_branch_config.employee_accident_insurance_number, 'P-001')
