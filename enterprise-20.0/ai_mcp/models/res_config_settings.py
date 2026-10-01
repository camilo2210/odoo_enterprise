# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    mcp_enable_dcr = fields.Boolean(
        string="Dynamic Client Registration",
        config_parameter='enable_dcr',
        groups='base.group_system',
        help="Allow MCP clients to register automatically.",
    )
    mcp_allowed_cimd_urls = fields.Char(
        string="Allowed Client ID Metadata Document (CIMD)",
        config_parameter='cimd_allowed_urls',
        groups='base.group_system',
        help="One client ID metadata document URL per line.",
    )
