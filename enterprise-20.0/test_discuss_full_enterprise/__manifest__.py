# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Test Discuss Full Enterprise',
    'category': 'Hidden',
    'summary': 'Test Suite for Discuss Enterprise',
    'auto_install': ['test_discuss_full', 'web_enterprise'],
    'depends': [
        'account_accountant',
        'account_invoice_extract',
        "ai_livechat",
        "ai_website_livechat",
        "ai",
        'approvals',
        'documents',
        'knowledge',
        'mail_enterprise',
        'sign',
        'test_discuss_full',
        'voip_ai',
        "voip",
        'web_enterprise',
        'web_studio',
        "website_helpdesk_livechat",
        'whatsapp',
    ],
    'assets': {
        'web.assets_tests': [
            'test_discuss_full_enterprise/static/tests/tours/**/*',
        ],
        'web.assets_unit_tests': [
            'test_discuss_full_enterprise/static/tests/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
