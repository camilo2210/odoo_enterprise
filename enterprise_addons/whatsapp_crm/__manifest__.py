{
    'name': 'WhatsApp CRM',
    'category': 'WhatsApp',
    'summary': 'Continue WhatsApp conversations directly from CRM leads',
    'description': """
This module integrates WhatsApp with CRM leads, allowing users to easily
continue ongoing WhatsApp conversations directly from the lead form.
""",
    'depends': ['crm', 'whatsapp'],
    'data': [
        'views/crm_lead_views.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'auto_install': True
}
