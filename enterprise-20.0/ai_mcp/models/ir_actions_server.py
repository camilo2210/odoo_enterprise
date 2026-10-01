# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import _


class IrActionsServer(models.Model):
    _inherit = "ir.actions.server"

    use_in_mcp = fields.Boolean(
        "Available in MCP",
        store=True,
        readonly=False,
        compute="_compute_use_in_mcp",
    )
    is_readonly = fields.Boolean("Readonly Tool", help="Does the tool only perform read operations? Required for MCP clients to differentiate between read and write tools.")

    @api.depends("state")
    def _compute_use_in_mcp(self):
        for action in self:
            if not action.ai_tool_is_candidate:
                action.use_in_mcp = False

    @api.constrains("state", "use_in_mcp")
    def _check_use_in_mcp(self):
        for action in self:
            if action.use_in_mcp and not action.ai_tool_is_candidate:
                raise ValidationError(_("The action '%s' cannot be used as an MCP tool.", action.name))
