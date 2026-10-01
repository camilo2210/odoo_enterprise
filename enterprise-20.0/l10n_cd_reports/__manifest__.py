{
    'name': 'Democratic Republic of the Congo - Accounting Reports',
    'description': """
Accounting reports for Democratic Republic of the Congo
=======================================================
- Corporate tax report
    """,
    'depends': [
        'account_reports',
        'l10n_cd',
    ],
    'data': [
        'data/account_return_data.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
