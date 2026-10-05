from odoo.exceptions import AccessError


def _mcp_get_allowed_tools(env):
    # sudo => internal users should be able to read available tools. The actual access
    # check is done after retrieving the tools using _can_execute_action_on_records
    tools = env['ir.actions.server'].sudo().search([('use_in_mcp', '=', True)])
    allowed_tools = env['ir.actions.server']
    for tool in tools:
        model_name = tool.model_id.model
        tool = tool.sudo(False)
        try:
            tool._can_execute_action_on_records(env[model_name])
            allowed_tools |= tool
        except AccessError:
            continue
    return allowed_tools
