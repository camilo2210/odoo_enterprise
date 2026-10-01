# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    @api.model
    def _get_assistant_calendar_resolve_models_project(self, res_ids_by_model):
        resolve_models_project = super()._get_assistant_calendar_resolve_models_project(res_ids_by_model)
        ticket_ids = res_ids_by_model.get("helpdesk.ticket")
        if ticket_ids:
            tickets = self.env["helpdesk.ticket"].browse(ticket_ids).exists()
            resolve_models_project["helpdesk.ticket"] = {
                ticket.id: ticket.project_id.id
                for ticket in tickets
                if ticket.project_id
            }

        return resolve_models_project
