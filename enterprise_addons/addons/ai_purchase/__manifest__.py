# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'AI Purchase',
    'category': 'AI',
    'summary': "Augment Purchase with AI Agents.",
    'depends': ['ai', 'purchase'],
    'data': [
        'data/ai_prompt_button_data.xml',
    ],
    'author': 'Odoo S.A.',
    'auto_install': True,
    'license': 'OEEL-1',
}
