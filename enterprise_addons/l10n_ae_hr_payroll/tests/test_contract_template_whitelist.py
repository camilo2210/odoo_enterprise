# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date

from freezegun import freeze_time

from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestWhitelistFromTemplate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company_ae = self.env['res.company'].create({
            'name': 'AE Co',
            'country_id': self.env.ref('base.ae').id,
            'l10n_ae_probation_period_duration': 3,
        })
        self.employee_ae = self.env['hr.employee'].create({
            'name': 'AE Employee',
            'company_id': self.company_ae.id,
            'contract_date_start': date(2025, 11, 5),
            'hr_responsible_id': self.env.ref('base.user_admin').id,
        })

    def test_ae_contract_template_loading(self):
        Version = self.env['hr.version'].with_company(self.company_ae)

        template = Version.create({
            'name': 'AE Template',
            'l10n_ae_housing_allowance': 2000.0,
            'l10n_ae_transportation_allowance': 500.0,
            'l10n_ae_other_allowances': 300.0,
            'l10n_ae_is_dews_applied': True,
            'l10n_ae_number_of_leave_days': 25,
            'l10n_ae_is_computed_based_on_daily_salary': True,
            'l10n_ae_eos_daily_salary': 150.0,
        })

        contract = self.employee_ae.version_id

        self.assertEqual(contract.l10n_ae_housing_allowance, 0.0)
        self.assertEqual(contract.l10n_ae_transportation_allowance, 0.0)
        self.assertFalse(contract.l10n_ae_is_dews_applied)

        self.employee_ae.contract_template_id = template
        self.employee_ae._onchange_contract_template_id()

        for field in Version._get_whitelist_fields_from_template():
            self.assertEqual(contract[field], template[field])

    def test_contract_end_reminder_to_hr(self):
        activity_type = self.env.ref('l10n_ae_hr_payroll.mail_activity_data_l10n_ae_probation_action', raise_if_not_found=False)
        with freeze_time("2026-01-30"):
            self.assertFalse(activity_type in self.employee_ae.activity_ids.activity_type_id, "There should be no probation end mail activity as probation ends on 2026-01-01")
            self.env['hr.employee'].notify_expiring_contract_work_permit()
            self.assertTrue(activity_type in self.employee_ae.activity_ids.activity_type_id, "There should be reminder activity as employee probation ended")
