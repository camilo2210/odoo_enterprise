{
    'name': 'Comoros - Accounting Reports',
    'description': """
Accounting reports for Comoros
============================================
- Corporate tax report
    """,
    'depends': [
        'account_reports',
        'l10n_km',
    ],
    'data': [
        'data/account_return_data.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
