# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Marketing Automation",
    'summary': "Build automated mailing campaigns",
    'website': 'https://www.odoo.com/app/marketing-automation',
    'category': "Marketing/Marketing Automation",
    'sequence': 195,
    'depends': ['mass_mailing', 'resource'],
    'data': [
        'security/marketing_automation_security.xml',
        'views/ir_actions_server_views.xml',
        'views/ir_actions_views.xml',
        'views/ir_model_views.xml',
        'views/mailing_mailing_views.xml',
        'wizard/marketing_campaign_test_views.xml',
        'views/link_tracker_views.xml',
        'views/mailing_trace_views.xml',
        'views/marketing_activity_views.xml',
        'views/marketing_participant_views.xml',
        'views/marketing_trace_views.xml',
        'views/marketing_campaign_views.xml',
        'views/marketing_automation_menus.xml',
        'data/ir_cron_data.xml',
        'security/ir.access.csv',
    ],
    'demo': [
        'data/res_groups_demo.xml',
    ],
    'other_files': [
        'data/templates/mail_template_body_confirmation_template.xml',
        'data/templates/mail_template_body_free_trial_template.xml',
        'data/templates/mail_template_body_join_partnership_template.xml',
        'data/templates/mail_template_body_welcome_template.xml',
        'data/templates/mail_template_body_yellow_discount_template.xml',
    ],
    'application': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'uninstall_hook': 'uninstall_hook',
    'assets': {
        'web._assets_primary_variables': [
            'marketing_automation/static/src/scss/variables.scss',
        ],
        'web.assets_backend': [
            'marketing_automation/static/src/js/**/*',
            'marketing_automation/static/src/scss/*.scss',
            'marketing_automation/static/src/plugins/**/*',
            'marketing_automation/static/src/components/**/*',
            'marketing_automation/static/src/controllers/**/*',
            'marketing_automation/static/src/views/**/*',

            # Don't include dark mode files in light mode
            ('remove', 'marketing_automation/static/src/scss/*.dark.scss'),
        ],
        "web.assets_web_dark": [
            'marketing_automation/static/src/scss/*.dark.scss',
        ],
        'web.assets_unit_tests': [
            'marketing_automation/static/tests/**/*',
        ],
    },
}
