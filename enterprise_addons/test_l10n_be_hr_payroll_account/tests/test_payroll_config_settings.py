# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests import tagged

from .common import TestPayrollAccountCommon


@tagged('post_install_l10n', 'post_install', '-at_install', 'payroll_config_settings')
class TestPayrollConfigSettingsFlow(TestPayrollAccountCommon):
    """Tests the effect of the ``payroll.config.settings`` values on the payroll flow.

    Each test asserts either:
      * a *numerical* effect (the configuration changes an amount on a computed
        payslip or a default value on ``hr.version``), or
      * a *conditional* effect (the configuration toggles whether a salary rule /
        contribution applies, or which value a computed field resolves to).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.company_id.current_payroll_config_id

        attendance_work_entry_type = cls.env['hr.work.entry.type'].search(
            [('code', '=', '002.00'), ('country_code', '=', 'BE')], limit=1)
        cls.be_calendar = cls.env['resource.calendar'].create({
            'name': 'BE Calendar 38h',
            'company_id': cls.company_id.id,
            'hours_per_day': 7.6,
            'hours_per_week': 38,
            'full_time_required_hours': 38,
            'attendance_ids': [
                (0, 0, {
                    'dayofweek': str(weekday),
                    'hour_from': hour,
                    'hour_to': hour + 4,
                    'work_entry_type_id': attendance_work_entry_type.id,
                })
                for weekday in range(5)
                for hour in [8, 13]
            ],
        })
        cls.employee = cls.create_employee({
            'name': 'Config Flow Employee',
            'date_version': date(2020, 1, 1),
            'contract_date_start': date(2020, 1, 1),
            'contract_date_end': False,
            'resource_calendar_id': cls.be_calendar.id,
        })
        cls.cp200_struct = cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary')

    def _compute_payslip(self):
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.employee.version_id.id,
            'date_from': date(2024, 1, 1),
            'date_to': date(2024, 1, 31),
            'struct_id': self.cp200_struct.id,
        })
        payslip.compute_sheet()
        return payslip

    def _line_total(self, payslip, code):
        return payslip._get_line_values([code], compute_sum=True)[code]['sum']['total']

    # ------------------------------------------------------------------
    # Conditional effects
    # ------------------------------------------------------------------
    def test_ffe_employer_type_drives_closure_fund_rule(self):
        """``l10n_be_ffe_employer_type`` selects between the commercial (809) and
        non-commercial (811) closure fund employer contributions."""
        # Commercial closure fund: rule 809 applies, 811 does not.
        self.config.l10n_be_ffe_employer_type = 'C'
        payslip = self._compute_payslip()
        self.assertTrue(payslip._should_apply_onss_contribution('809'))
        self.assertFalse(payslip._should_apply_onss_contribution('811'))
        self.assertNotEqual(self._line_total(payslip, 'ONSSEMPLOYER_809'), 0)

        # Non-commercial closure fund: rule 811 applies, 809 does not.
        self.config.l10n_be_ffe_employer_type = 'B'
        payslip = self._compute_payslip()
        self.assertFalse(payslip._should_apply_onss_contribution('809'))
        self.assertTrue(payslip._should_apply_onss_contribution('811'))
        self.assertEqual(self._line_total(payslip, 'ONSSEMPLOYER_809'), 0)

    def test_main_joint_committee_fallback(self):
        """A version with no employee type falls back to the configured main joint committee."""
        self.config.l10n_be_main_joint_committee = self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_302')
        version = self.env['hr.version'].with_company(self.company_id).create({
            'name': 'JC Fallback Version',
            'wage': 2500,
            'date_version': date(2020, 1, 1),
            'company_id': self.company_id.id,
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
        })
        self.assertEqual(
            version.l10n_be_joint_committee_id,
            self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_302'),
        )

    # ------------------------------------------------------------------
    # Numerical effects
    # ------------------------------------------------------------------
    def test_onss_importance_code_changes_closure_fund_amount(self):
        """The company size (``onss_importance_code``) changes the closure fund rate:
        a large company (code >= 4) pays a higher amount than a small one (code <= 3)."""
        self.config.l10n_be_ffe_employer_type = 'C'

        self.config.onss_importance_code = '1'
        small_amount = abs(self._line_total(self._compute_payslip(), 'ONSSEMPLOYER_809'))

        self.config.onss_importance_code = '4'
        large_amount = abs(self._line_total(self._compute_payslip(), 'ONSSEMPLOYER_809'))

        self.assertGreater(large_amount, small_amount)

    def test_insurance_amount_defaults_from_config(self):
        """Hospital insurance amounts configured on the company flow as defaults
        onto a new ``hr.version`` and drive the computed insurance amount."""
        self.config.write({
            'hospital_insurance_amount_child': 10.0,
            'hospital_insurance_amount_adult': 25.0,
        })
        version = self.env['hr.version'].with_company(self.company_id).create({
            'name': 'Insurance Version',
            'wage': 2500,
            'date_version': date(2020, 1, 1),
            'company_id': self.company_id.id,
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
        })
        self.assertEqual(version.hospital_insurance_amount_per_child, 10.0)
        self.assertEqual(version.hospital_insurance_amount_per_adult, 25.0)

        version.write({
            'has_hospital_insurance': True,
            'insured_relative_children': 2,
            'insured_relative_adults': 0,
        })
        # children: 2 * 10 = 20 ; adults: (employee himself) 1 * 25 = 25 ; total = 45
        self.assertEqual(version.insurance_amount, 45.0)
