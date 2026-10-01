{
    'name': 'WhatsApp Planning',
    'category': 'WhatsApp',
    'description': """This module Integrates Planning with WhatsApp""",
    'depends': ['planning', 'whatsapp'],
    'data': [
        'wizard/whatsapp_planning_template_configure_views.xml',
        'data/whatsapp_template_data.xml',
        'views/res_config_settings_views.xml',
        "views/hr_employee_public_views.xml",
        'wizard/planning_send_views.xml',
        'security/ir.access.csv',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'auto_install': True,
    'post_init_hook': '_post_init_hook',
}
