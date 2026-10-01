# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'WhatsApp Follow-Up',
    'category': 'Marketing/WhatsApp',
    'summary': 'Send Follow-Up to your Contacts on WhatsApp',
    'depends': ['account_followup', 'whatsapp'],
    'data': [
        'data/whatsapp_template_data.xml',
        'views/account_followup_line_views.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'auto_install': True,
}
