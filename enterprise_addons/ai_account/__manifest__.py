# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "AI Text Draft - Accounting",
    'category': 'Hidden',
    'summary': "AI text draft integration with accounting",
    'depends': ['ai', 'account'],
    'data': [
        'wizard/account_move_send_wizard.xml',
        'data/ai_prompt_button_data.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
