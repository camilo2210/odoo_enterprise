# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Website Appointment Lead Enrichment',
    'category': 'Services/Appointment',
    'sequence': 2160,
    'summary': 'Enrich lead created automatically through an appointment with gathered website visitor information',
    'website': 'https://www.odoo.com/app/appointments',
    'description': """
Enrich lead created automatically through an appointment with gathered website visitor information such as language,
country and detailed information like pages browsed by the lead (through a link to website visitor).
""",
    'depends': ['appointment_crm', 'website_crm'],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
