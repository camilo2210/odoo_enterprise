# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Sign itsme',
    'category': 'Sales/Sign',
    'summary': "Sign documents with itsme® identification",
    'description': "Add support for itsme® identification when signing documents (Belgium and Netherlands only)",
    'depends': ['sign', 'iap'],
    'data': [
        'data/iap_service_data.xml',
        'data/mail_template.xml',
        'report/sign_itsme_log_reports.xml',
        'views/sign_request_templates.xml',
    ],
    'assets': {
        'sign.assets_public_sign': [
            'sign_itsme/static/src/**/*',
        ],
        'web.assets_backend': [
            'sign_itsme/static/src/**/*',
        ],
        'web.assets_frontend': [
            'sign_itsme/static/src/**/*',
        ],
        'web.assets_unit_tests': [
            'sign_itsme/static/tests/itsme_dialog.test.js',
        ],
    },
    'iap_paid_service': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
