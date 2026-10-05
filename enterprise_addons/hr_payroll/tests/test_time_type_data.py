# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import HttpCase, new_test_user, tagged


@tagged('post_install_l10n')
class TestWorkEntryTypeLocalizations(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.payroll_user = new_test_user(
            cls.env, login='stream_payroll_user', password='stream_payroll_user',
            groups='base.group_user,hr_payroll.group_hr_payroll_manager',
        )

    def test_all_localizations_override_work_entry_get_data_files_to_update(self):
        # Get all installed l10n_XX_hr_payroll modules
        installed_modules = self.env["ir.module.module"].search([
            ("name", "=like", "l10n_%_hr_payroll"),
            ("state", "=", "installed"),
        ])

        # Filter to only modules that have hr.work.entry.type data files
        # Localization modules override work entry types from hr_work_entry module,
        # so we need to check for the data file existence in the module's manifest
        locas_with_work_entry_data = set()
        for module in installed_modules:
            module_name = module.name
            # Check if the module has hr_work_entry_type_data.xml in its data files
            manifest = module.get_module_info(module_name)
            data_files = manifest.get('data', [])
            if any('hr_work_entry_type_data.xml' in data_file for data_file in data_files):
                locas_with_work_entry_data.add(module_name)

        res = self.env['hr.work.entry.type']._get_data_files_to_update()
        registered_locas = {module_name for module_name, _ in res}

        missing_override = locas_with_work_entry_data - registered_locas

        self.assertFalse(
            missing_override,
            f"The following localization modules must be included in '_get_data_files_to_update()' for work entry types:\n"
            f"{', '.join(missing_override)}"
        )

    def test_only_payroll_data_is_updated(self):
        paid_time_off = self.env['hr.work.entry.type'].with_user(self.payroll_user).search([('code', '=', '016.00')], limit=1)
        paid_time_off.with_user(self.payroll_user).count_as = 'working_time'
        self.assertFalse(paid_time_off.modified_by_user)

        paid_time_off.with_user(self.payroll_user).requires_allocation = False
        self.assertFalse(paid_time_off.modified_by_user)

        paid_time_off.with_user(self.payroll_user).round_days_type = 'UP'
        self.assertTrue(paid_time_off.modified_by_user)

        paid_time_off.action_reset_rule()
        self.assertFalse(paid_time_off.modified_by_user)
        self.assertFalse(paid_time_off.requires_allocation)
        self.assertEqual(paid_time_off.count_as, 'working_time')
        self.assertEqual(paid_time_off.round_days_type, 'DOWN')
