# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date

from freezegun import freeze_time

from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestWhitelistFromTemplate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company_sa = self.env['res.company'].create({
            'name': 'SA Co',
            'country_id': self.env.ref('base.sa').id,
            'l10n_sa_probation_period_duration': 3,
        })
        self.employee_sa = self.env['hr.employee'].create({
            'name': 'SA Employee',
            'company_id': self.company_sa.id,
            'contract_date_start': date(2025, 11, 5),
            'hr_responsible_id': self.env.ref('base.user_admin').id,
        })

    def test_sa_contract_template_loading(self):
        Version = self.env['hr.version'].with_company(self.company_sa)

        template = Version.create({
            'name': 'SA Template',
            'l10n_sa_housing_allowance': 1500.0,
            'l10n_sa_transportation_allowance': 500.0,
            'l10n_sa_other_allowances': 300.0,
            'l10n_sa_number_of_days': 30,
        })

        contract = self.employee_sa.version_id

        self.assertEqual(contract.l10n_sa_housing_allowance, 0.0)
        self.assertEqual(contract.l10n_sa_transportation_allowance, 0.0)
        self.assertEqual(contract.l10n_sa_other_allowances, 0.0)
        self.assertEqual(contract.l10n_sa_number_of_days, 21)

        self.employee_sa.contract_template_id = template
        self.employee_sa._onchange_contract_template_id()

        for field in Version._get_whitelist_fields_from_template():
            self.assertEqual(contract[field], template[field])

    def test_contract_end_reminder_to_hr(self):
        activity_type = self.env.ref('l10n_sa_hr_payroll.mail_activity_data_l10n_sa_probation_action', raise_if_not_found=False)
        with freeze_time("2026-01-30"):
            self.assertFalse(activity_type in self.employee_sa.activity_ids.activity_type_id, "There should be no probation end mail activity as probation ends on 2026-01-01")
            self.env['hr.employee'].notify_expiring_contract_work_permit()
            self.assertTrue(activity_type in self.employee_sa.activity_ids.activity_type_id, "There should be reminder activity as employee probation ended")
