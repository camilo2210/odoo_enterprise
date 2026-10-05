from odoo import models


class AIComposer(models.Model):
    _inherit = "ai.composer"

    def _get_initial_context(
        self,
        res_model=None,
        res_id=None,
        text_selection=None,
        text_of_editable=None,
        reference_image_path=None,
    ):
        """Get the initial context (list of message parts) for the session based on the composer's
        interface_key, topics and current record.
        """
        self.ensure_one()
        context_parts = super()._get_initial_context(
            res_model,
            res_id,
            text_selection,
            text_of_editable,
            reference_image_path,
        )

        def add_text_part(text):
            context_parts.append({"type": "text", "text": text})

        if self.interface_key == "chatter_ai_button" and res_model == "helpdesk.ticket":
            ticket = self.env[res_model].search([("id", "=", res_id)])
            if not ticket:
                raise ValueError(
                    "Model should be set when using `chatter_ai_button` interface key.",
                )

            if ticket.team_id.use_ai:
                similar_tickets = ticket._get_similar_tickets(limit=20)
                tickets_str = ""
                for similar_ticket in similar_tickets:
                    tickets_str += f"<similar_ticket id={similar_ticket.id}>{similar_ticket._get_embedding_content()}</similar_ticket>\n"

                if len(similar_tickets) > 0:
                    add_text_part(f"## Similar Tickets\n\n{tickets_str}")
        return context_parts

    def _get_agent(self, res_model=None, res_id=None):
        self.ensure_one()
        if res_model == "helpdesk.ticket" and res_id:
            helpdesk_team = self.env[res_model].browse(res_id).team_id
            if helpdesk_team.use_ai and helpdesk_team.ai_agent_id:
                return helpdesk_team.ai_agent_id
        return super()._get_agent(res_model, res_id)
