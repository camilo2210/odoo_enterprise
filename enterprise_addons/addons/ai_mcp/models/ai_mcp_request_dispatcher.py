# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json

from odoo import models
from odoo.tools.json import json_default

from odoo.addons.ai_mcp.utils.exceptions import McpMethodNotFoundError
from odoo.addons.ai_mcp.utils.utils import _mcp_get_allowed_tools


class AiMcpRequestDispatcher(models.AbstractModel):
    _name = "ai.mcp.request.dispatcher"
    _description = "MCP Request Dispatcher"

    def _mcp_dispatch(self, mcp_request):
        # A notification from the MCP client doesn't have an 'id'. We ignore notifications and return immediately.
        if 'id' not in mcp_request:
            return None

        method = mcp_request.get('method')
        params = mcp_request.get('params', {})

        if method == 'initialize':
            return self._mcp_initialize(params)
        if method == 'ping':
            return {}
        if method == 'tools/list':
            return self._mcp_tools_list(params)
        if method == 'tools/call':
            return self._mcp_tools_call(params)
        raise McpMethodNotFoundError()

    def _mcp_initialize(self, params):
        return {
            'protocolVersion': params['protocolVersion'],
            'capabilities': {'tools': {}},
            'serverInfo': {'name': 'Odoo', 'version': '1.0.0'},
        }

    def _mcp_tools_list(self, params):
        return {
            'tools': [self._mcp_build_tool_definition(tool) for tool in _mcp_get_allowed_tools(self.env)]
        }

    def _mcp_build_tool_definition(self, tool):
        # sudo => internal users should be able to access tools' fields.
        tool = tool.sudo()
        schema = json.loads(tool.ai_tool_schema) if tool.ai_tool_schema else {}
        schema.setdefault('type', 'object')
        schema.setdefault('properties', {})

        return {
            'name': tool.ai_tool_name,
            'title': tool.ai_tool_name,
            'description': tool.ai_tool_description or tool.ai_tool_name,
            'inputSchema': schema,
            'annotations': {
                'title': tool.ai_tool_name,
                'readOnlyHint': tool.is_readonly,
                'destructiveHint': not tool.is_readonly,
            },
            'execution': {
                'taskSupport': 'forbidden'
            }
        }

    def _mcp_tools_call(self, params):
        name = params['name']
        arguments = params.get('arguments', {})
        # sudo => internal users should be able to read tools. The sudo is immediately dropped.
        # Also the access rights to execute the tool will be checked using _can_execute_action_on_records
        tool = self.env['ir.actions.server'].sudo().search([('ai_tool_name', '=', name), ('use_in_mcp', '=', True)]).sudo(False)
        if not tool:
            raise ValueError(f"The tool '{name}' doesn't exist")
        model_name = tool.sudo().model_id.model
        tool._can_execute_action_on_records(self.env[model_name])
        # sudo => internal users should be able to execute tools and access was checked using _can_execute_action_on_records
        result = tool.sudo()._ai_tool_run(self.env[model_name], arguments, {'tool_request_confirmed': True})
        return {'content': [{'type': 'text', 'text': json.dumps(result or "The operation has been executed successfully.", default=json_default, ensure_ascii=False)}], 'isError': False}
