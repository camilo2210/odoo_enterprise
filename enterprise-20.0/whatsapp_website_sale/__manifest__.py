# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'WhatsApp-eCommerce',
    'category': 'WhatsApp',
    'summary': 'This module integrates website sale with WhatsApp',
    'description': """This module integrates website sale with WhatsApp""",
    'depends': ['website_sale', 'whatsapp'],
    'data': [
        'data/whatsapp_template_data.xml',
        'data/ir_cron_data.xml',
        'views/res_config_settings_views.xml',
        'views/sale_order_views.xml',
    ],
    'demo': [
        'data/demo.xml'
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'auto_install': True,
}
