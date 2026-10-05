# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'AI Sale Stock',
    'category': 'AI',
    'summary': "Augment Sale Stock with AI Agents.",
    'depends': ['ai', 'sale_stock'],
    'data': [
        'data/ai_prompt_button_data.xml',
    ],
    'author': 'Odoo S.A.',
    'auto_install': True,
    'license': 'OEEL-1',
}
