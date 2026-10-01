# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'AI Helpdesk',
    'category': 'AI',
    'summary': "Augment Helpdesk with AI Agents.",
    'depends': ['ai', 'helpdesk'],
    'data': [
        'data/ai_composer_data.xml',
        'data/ai_prompt_button_data.xml',
        'views/helpdesk_ticket_views.xml',
        'views/helpdesk_team_views.xml',
    ],
    'author': 'Odoo S.A.',
    'auto_install': True,
    'license': 'OEEL-1',
}
