# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'AI Accounting Reports',
    'category': 'Hidden',
    'summary': 'AI-assisted accounting report analysis and audit review',
    'depends': ['ai', 'account_reports'],
    'data': [
        'data/ir_actions_server_tools.xml',
        'data/ai_skill_data.xml',
        'data/ai_audit_agents.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ai_account_reports/static/src/**/*',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
