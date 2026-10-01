# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Payment Follow-up Management',
    'version': '1.1',
    'category': 'Accounting/Accounting',
    'description': """
Module to automate letters for unpaid invoices, with multi-level recalls.
=========================================================================

You can define your multiple levels of recall through the invoicing settings:
-----------------------------------------------------------------------------
    Configuration / Settings / Customer Invoices / Automatic Invoice Reminders

Features:
---------
    - Automatic multi-level reminders based on overdue duration.
    - Send & Print integration:
        If Send & Print is executed again on an overdue invoice, the system
        automatically switches to the appropriate reminder template and attaches
        the follow-up report.
    - Batch reminders:
        Users can select multiple invoices from the list view and send reminders
        to multiple customers at once using the 'Send Reminders' action.
""",
    'website': 'https://www.odoo.com/app/invoicing',
    'depends': ['mail', 'sms', 'account_reports'],
    'data': [
        'data/mail_template_data.xml',
        'data/account_followup_data.xml',
        'data/cron.xml',
        'wizard/followup_manual_reminder_views.xml',
        'wizard/followup_missing_information.xml',
        'wizard/mail_compose_message_views.xml',
        'views/account_followup_views.xml',
        'views/account_followup_line_views.xml',
        'views/partner_view.xml',
        'views/report_followup.xml',
        'views/account_move_views.xml',
        'views/res_config_settings_views.xml',
        'security/ir.access.csv',
        ],
    'demo': [
        'demo/account_followup_demo.xml'
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'account_followup.assets_followup_report': [
            ('include', 'web._assets_helpers'),
            'web/static/src/scss/pre_variables.scss',
            'web/static/lib/bootstrap/scss/_variables.scss',
            'web/static/lib/bootstrap/scss/_variables-dark.scss',
            'web/static/lib/bootstrap/scss/_maps.scss',
            ('include', 'web._assets_bootstrap_backend'),
            'web/static/fonts/fonts.scss',
        ],
        'web.assets_backend': [
            'account_followup/static/src/components/**/*.js',
        ],
    }
}
