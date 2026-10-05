# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'AI Portal',
    'summary': 'Portal integration for AI services',
    'description': """
This module integrates AI functionality with the portal user experience.

It provides the foundation for AI-related access management through the portal,
including the generation and handling of MCP keys for authenticated portal users.
    """,
    'category': 'Hidden/Tools',
    'depends': ['ai_mcp', 'portal'],
    'assets': {
        'web.assets_frontend': [
            'ai_portal/static/src/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'auto_install': True,
}
