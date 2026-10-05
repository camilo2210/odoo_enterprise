from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestPayrollAccountDynamicDispatch(TransactionCase):
    """
    _load_payroll_accounts() dispatches to
    _configure_payroll_account_<template_code>() via getattr(), so these
    methods are invisible to static "find usages". This test discovers
    every installed l10n_<xx>_hr_payroll_account module and checks that
    each chart template code registered for that country has a matching
    _configure_payroll_account_<code>() method, so deleting one as
    "unused" fails CI instead of silently breaking new-company setup.
    """

    def test_all_payroll_localizations_have_configure_method(self):
        modules = self.env['ir.module.module'].sudo().search([
            ('name', '=like', 'l10n\\_%\\_hr\\_payroll\\_account'),
            ('state', '=', 'installed'),
        ])
        if not modules:
            self.skipTest("No l10n_*_hr_payroll_account module installed")

        template_mapping = self.env['account.chart.template']._get_chart_template_mapping()

        missing = []
        for module in modules:
            country_code = module.name.split('_')[1]
            country = self.env['res.country'].search([('code', '=', country_code.upper())], limit=1)
            codes = [
                code for code, data in template_mapping.items()
                if data.get('country_id') and data['country_id'] == country.id
            ]
            for code in codes:
                if not callable(getattr(self.env['account.chart.template'], f'_configure_payroll_account_{code}', None)):
                    missing.append((module.name, code))

        self.assertFalse(
            missing,
            f"Missing _configure_payroll_account_<code>() for: {missing}. "
            "Called dynamically via getattr() - not visible to static search."
        )
