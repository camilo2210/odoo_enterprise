# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Website Visits Lead Generation Enterprise',
    'summary': 'Enterprise counterpart of Visits -> Leads',
    'description': 'Enterprise counterpart of Visits -> Leads',
    'category': 'Sales/CRM',
    'depends': [
        'crm_enterprise',
        'website_crm_iap_reveal',
    ],
    'data': [
        'views/crm_lead_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
