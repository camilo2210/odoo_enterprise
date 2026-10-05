# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Mass mailing on sale subscriptions',
    'category': 'Marketing/Email Marketing',
    'summary': 'Add sale subscription support in mass mailing',
    'description': """Mass mailing on sale subscriptions""",
    'depends': [
        'mass_mailing_sale',
        'sale_subscription',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
