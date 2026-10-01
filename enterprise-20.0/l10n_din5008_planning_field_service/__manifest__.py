# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'DIN 5008 - Field Service',
    'category': 'Accounting/Localizations',
    'author': 'Odoo S.A.',
    'depends': [
        'l10n_din5008',
        'planning_field_service',
    ],
    'assets': {
        'web.report_assets_common': [
            'l10n_din5008_planning_field_service/static/src/**/*',
        ],
    },
    'data': [
        'report/worksheet_custom_report_templates.xml',
    ],
    'auto_install': True,
    'license': 'OEEL-1',
}
