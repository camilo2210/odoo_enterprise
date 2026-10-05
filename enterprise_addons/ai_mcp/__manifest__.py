# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'AI MCP Server',
    'category': 'Technical',
    'summary': 'Connect Odoo to any external server via the MCP',
    'description': """
    - To connect to your Odoo MCP Server:
        1. Set the URL of the MCP server as the Odoo URL with the suffix /mcp. For example if the Odoo URL 'https://example.odoo.com', the MCP Server URL would be 'https://example.odoo.com/mcp'.
        2. Generate an API Key to use it as the authentication token with your favourite MCP client:
            a. Login into Odoo.
            b. Click on the user avatar.
            c. Go to the security tab.
            d. Generate an API key. Set the scope as MCP.
    - Important:
        1. NEVER share your token. Anyone who gets access to your token can use the MCP server as if it was you.
        2. NEVER add your token in a text field on your MCP client. ALWAYS use fields of type Credential or Password as they are encrypted.
    """,
    'depends': ['ai'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'data': [
        'security/ir.access.csv',
        'data/ir_config_parameter_data.xml',
        'views/ir_actions_server_views.xml',
        'views/res_users_views.xml',
        'views/res_config_settings_views.xml',
        'views/oauth_client_views.xml',
        'views/oauth_consent_templates.xml',
        'data/ir_actions_server_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ai_mcp/static/src/scss/res_config_settings.scss',
        ],
    },
    'auto_install': True,
}
