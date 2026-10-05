# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Live Currency Exchange Rate',
    'category': 'Accounting/Accounting',
    'description': """Import exchange rates from the Internet.
""",
    'depends': [
        'account',
    ],
    'data': [
        'views/res_config_settings_views.xml',
        'views/service_cron_data.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
