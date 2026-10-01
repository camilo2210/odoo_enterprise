# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestPayrollDependencies(TransactionCase):

    def test_l10n_xx_hr_payroll_no_account(self):
        for module in self.env['ir.module.module'].search([('name', '=like', 'l10n____hr_payroll')]):
            dependencies = module.upstream_dependencies(exclude_states=()).mapped('name')
            self.assertTrue('hr_payroll' in dependencies, f"The payroll localization {module.name} should depend on payroll")
            self.assertFalse('account' in dependencies, f"The payroll localization {module.name} shouldn't depend on accounting")

        for module in self.env['ir.module.module'].search([('name', '=like', 'l10n____hr_payroll_account')]):
            dependencies = module.upstream_dependencies(exclude_states=()).mapped('name')
            self.assertTrue(module.name[:18] in dependencies, f"The payroll localization {module.name} should depend on {module.name[:18]}")
            self.assertTrue('account' in dependencies, f"The payroll localization {module.name} shouldn't depend on accounting")

    def test_l10n_xx_hr_payroll_no_countries_in_dependencies(self):
        l10n_xx_hr_modules = (
            self.env["ir.module.module"]
            .search([("name", "=like", "%l10n____hr%")])
            .filtered(lambda m: m.country_ids)
        )
        for l10n_xx_hr_module in l10n_xx_hr_modules:
            auto_install_names = l10n_xx_hr_module.dependencies_id.filtered('auto_install_required').mapped('name')
            auto_install_modules = self.env['ir.module.module'].search([('name', 'in', auto_install_names)])
            for auto_install_module in auto_install_modules:
                self.assertFalse(
                    auto_install_module.country_ids & l10n_xx_hr_module.country_ids,
                    "Module %s should not have countries (%s) since its auto-install dependency %s is already country-specific"
                    % (l10n_xx_hr_module.name, ', '.join(l10n_xx_hr_module.country_ids.mapped('code')), auto_install_module.name),
                )

    def test_l10n_xx_existing_post_install_hook(self):
        for module in self.env['ir.module.module'].search([('name', '=like', 'l10n____hr_payroll')]):
            expected_method_name = f"_l10n_{module.name[5:7]}_hr_payroll_post_install"
            self.assertEqual(
                module.get_module_info(module.name).get('post_init_hook'),
                expected_method_name,
                f"Missing post init hook {expected_method_name} to adapt work entry types to country")


@tagged('post_install', '-at_install')
class TestPayrollDataConfiguration(TransactionCase):

    def test_hr_payroll_data_updatable(self):
        updatable_data_models = [
            ("hr.salary.rule", "salary rules"),
            ("hr.payroll.warning", "payroll warnings"),
            ("hr.salary.rule.category", "salary rule categories"),
            ("hr.payroll.structure", "payroll structures"),
        ]
        for model_name, model_desc in updatable_data_models:
            all_records = self.env[model_name].search([])
            all_xmlids = self.env["ir.model.data"].search(
                [("model", "=", model_name), ("res_id", "in", all_records.ids)]
            )
            noupdate_xmlids = all_xmlids.filtered("noupdate")
            self.assertFalse(
                noupdate_xmlids,
                "Following %s shouldn't be noupdate\n%s"
                % (model_desc, "\n".join(noupdate_xmlids.mapped("complete_name"))),
            )
