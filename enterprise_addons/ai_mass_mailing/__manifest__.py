# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'AI Mass Mailing',
    'category': 'AI',
    'summary': "Augment Mass Mailing with AI Agents.",
    'depends': ['ai', 'mass_mailing'],
    'data': [
        'data/ai_prompt_button_data.xml',
    ],
    'assets': {
        'mass_mailing.assets_builder': [
            'ai_mass_mailing/static/src/builder/**/*',
        ],
        'web.assets_backend': [
            'ai_mass_mailing/static/src/scss/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'auto_install': True,
    'license': 'OEEL-1',
}
