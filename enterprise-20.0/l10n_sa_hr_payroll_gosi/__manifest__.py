# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Saudi Arabia - Payroll with GOSI Integration',
    'author': 'Odoo S.A.',
    'category': 'Human Resources/Payroll',
    'description': """
Saudi Arabia Payroll Integration with GOSI
===========================================================
- Fetches & updates GOSI contributions automatically.
- GOSI contribution salary rules.
    """,
    "license": "OEEL-1",
    "depends": ["l10n_sa_hr_payroll", "certificate"],
    "auto_install": True,
    "data": [
        'security/ir.access.csv',
        'data/ir_cron_data.xml',
        'data/hr_payroll_warning_data.xml',
        'views/res_config_settings_views.xml',
        'views/hr_employee_views.xml',
        'views/l10n_sa_gosi_wage_update_views.xml'
    ],
}
