# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class AiTool(models.AbstractModel):
    _inherit = 'ai.tool'

    def _ai_tool_mcp_retrieve_initial_context(self):
        context = "<odoo_current_context>\n"
        context += f"## Timezone\n{self.env.user.tz}"
        user_info = {k: v for k, v in self.env.user._ai_read(['name', 'function', 'partner_id'])[0][0].items() if v}
        user_info['user_id'] = user_info.pop('id')
        context += f"\n## User info\n{user_info}"

        # Active companies are passed through context from the web client. However, in mcp, there is no web client. So, we use
        # the user's default company as the active company. We insist on using 'active' because topics instructions mention
        # active companies like create_records topic.
        company = self.env.user.company_id
        active_company_info = {"model": "res.company", "id": company.id, "name": company.name}
        if company.country_id.code:
            active_company_info["country_code"] = company.country_id.code
            if company.city:
                active_company_info["country_city"] = company.city
        context += f"\n## Active company\n{active_company_info}"

        available_companies_info = [{"model": "res.company", "id": company.id, "name": company.name} for company in self.env.user.company_ids]
        context += f"\n## companies available for the current user \n{available_companies_info}"
        context += "\n## General Notes \n"
        context += """
            All the date/time values retrieved from the database are in UTC format.
            Always provide the date/time in UTC format when using any tool.
            Only convert date/time to the user's timezone when displaying date/time to the user.\n
        """
        context += "</odoo_current_context>"
        return context
