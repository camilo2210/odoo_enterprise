{
    'name': 'Ivory Coast - Accounting Reports',
    'description': """
Accounting reports for Ivory Coast
============================================
- Corporate tax report
    """,
    'depends': [
        'account_reports',
        'l10n_ci',
    ],
    'data': [
        'data/account_return_data.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
