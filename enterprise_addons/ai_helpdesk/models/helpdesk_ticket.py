# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools.mail import html_to_inner_content

TICKET_DISTANCE_THESHOLD = 0.3  # Defines the maximum distance that a ticket must be from another (in vector space) in order to be considered similar


class HelpdeskTicket(models.Model):
    _name = "helpdesk.ticket"
    _inherit = ["helpdesk.ticket", "ai.embedding.mixin"]

    use_ai = fields.Boolean(related="team_id.use_ai")
    similar_tickets_count = fields.Integer(
        "Amount of similar tickets",
        compute="_compute_similar_tickets_count",
    )
    similar_closed_tickets_count = fields.Integer(
        "Amount of similar closed tickets",
        compute="_compute_similar_tickets_count",
    )

    def _compute_similar_tickets_count(self):
        for ticket in self:
            if not ticket.use_ai:
                ticket.similar_tickets_count = 0
                ticket.similar_closed_tickets_count = 0
            else:
                similar_tickets = ticket._get_similar_tickets()
                ticket.similar_tickets_count = len(similar_tickets)
                ticket.similar_closed_tickets_count = len(
                    similar_tickets.filtered(lambda ticket: ticket.fold),
                )

    @api.model_create_multi
    def create(self, vals_list):
        created_records = super().create(vals_list)
        tickets_to_embed = created_records.filtered(lambda t: t.use_ai)

        ticket_per_model: dict[str, HelpdeskTicket] = {}
        for ticket in tickets_to_embed:
            for model in ticket._get_embedding_models():
                if not ticket_per_model.get(model):
                    ticket_per_model[model] = ticket
                else:
                    ticket_per_model[model] |= ticket
        for model, tickets in ticket_per_model.items():
            tickets._create_embedding_records({model})
        self.env.ref("ai.ir_cron_generate_embedding")._trigger()
        return created_records

    def write(self, vals):
        result = super().write(vals)
        if "name" in vals or "description" in vals:
            self.filtered("use_ai").embedding_status = "dirty"
        return result

    def _message_post_after_hook(self, message):
        result = super()._message_post_after_hook(message)
        if self.use_ai and message.body and message.message_type in ("comment", "email"):
            self.embedding_status = "dirty"
        return result

    def action_open_similar_tickets(self):
        self.ensure_one()
        tickets = self | self._get_similar_tickets()
        return {
            "type": "ir.actions.act_window",
            "res_model": "helpdesk.ticket",
            "name": "Similar tickets",
            "view_mode": "kanban",
            "views": [[False, "kanban"], [False, "list"], [False, "form"]],
            "domain": [("id", "in", tickets.ids)],
            "context": {
                "search_default_is_open": False,
                "create": False,
                "group_by": "stage_id",
            },
        }

    def action_recompute_ticket_embeddings(self):
        self.ensure_one()
        if self.use_ai:
            self.embedding_status = "processing"
            self._recreate_embeddings()

    def action_refresh_similarity_status(self):
        self.ensure_one()
        return {"type": "ir.actions.client", "tag": "soft_reload"}

    @api.model
    def _get_records_to_embed_domain(self):
        teams = self.env["helpdesk.team"].search([("use_ai", "=", True)])
        domain = Domain.FALSE
        for team in teams:
            team_domain = Domain("team_id", "=", team.id)
            if team.ticket_similarity_time_range and team.ticket_similarity_time_range != "forever":
                team_domain &= Domain("create_date", ">", f"-{team.ticket_similarity_time_range}")
            domain |= team_domain
        return super()._get_records_to_embed_domain() & domain

    def _get_embedding_content(self):
        self.ensure_one()
        parts = f"Name: {self.name}\n"
        if self.description:
            parts += f"Description: {html_to_inner_content(self.description)}\n"
        messages = self.message_ids.filtered(
            lambda m: m.message_type in ("comment", "email") and m.body,
        )
        if messages:
            parts += "Chatter messages:\n" + "\n".join(
                f"- {html_to_inner_content(m.body)}" for m in messages
            )
        return parts

    def _get_embedding_models(self) -> set[str]:
        self.ensure_one()
        return {self.team_id.ai_agent_id.embedding_model}

    def _get_similar_tickets(self, limit: int | None = None):
        """Retrieves a set of ids of similar tickets.

        :return: a set of the ids of the similar tickets
        :rtype: set[int]
        """
        self.ensure_one()
        if not self.embedding_ids or not all(emb.embedding_vector for emb in self.embedding_ids):
            return self.env["helpdesk.ticket"]

        if not self.team_id.ai_agent_id:
            raise UserError(
                self.env._("Default agent not found, cannot find similar records."),
            )

        embedding_model = self.team_id.ai_agent_id.embedding_model

        scaled_distance_threshold = (
            TICKET_DISTANCE_THESHOLD * self.team_id.ticket_similarity_threshold
        )
        return self.env["ai.embedding"]._get_similar_documents(
            query_model=self,
            target_models=self.team_id.ticket_ids - self,
            embedding_model=embedding_model,
            max_distance=TICKET_DISTANCE_THESHOLD - scaled_distance_threshold,
            limit=limit,
        )
