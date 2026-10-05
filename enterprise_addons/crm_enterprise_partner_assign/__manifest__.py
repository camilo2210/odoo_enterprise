# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Enterprise Resellers',
    'summary': 'Enterprise counterpart for Resellers',
    'description': 'Enterprise counterpart for Resellers',
    'category': 'Website/Website',
    'depends': [
        'crm_enterprise',
        'website_crm_partner_assign',
    ],
    'data': [
        'views/crm_lead_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
