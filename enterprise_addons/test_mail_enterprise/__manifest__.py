
{
    'name': 'Mail Tests (Enterprise)',
    'category': 'Hidden',
    'sequence': 9876,
    'summary': 'Mail Tests: performances and tests specific to mail with all sub-modules',
    'description': """This module contains tests related to mail. Those are
present in a separate module as it contains models used only to perform
tests independently to functional aspects of other models. Moreover most of
modules build on mail (sms, snailmail, mail_enterprise) are set as dependencies
in order to test the whole mail codebase. """,
    'depends': [
        'ai',
        'documents',
        'mail',
        'mail_bot',
        'mail_enterprise',
        'mass_mailing',
        'mass_mailing_sms',
        'marketing_automation',
        'marketing_automation_sms',
        'mail_mobile',
        'portal',
        'rating',
        'snailmail',
        'sms',
        'test_mail',
        'test_mail_full',
        'test_mass_mailing',
        'test_mail_sms',
        'test_base',
        'voip',
        'test_whatsapp',
    ],
    'data': [
        'security/ir.access.csv',
    ],
    'assets': {
        'web.assets_unit_tests': [
            'test_mail_enterprise/static/tests/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
