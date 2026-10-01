from ast import literal_eval

from odoo import api, fields, models


class MailActivitySchedule(models.TransientModel):
    _inherit = "mail.activity.schedule"

    ticket_id = fields.Many2one(
        "helpdesk.ticket",
        compute="_compute_ticket_id",
        store=False,
        readonly=False,
    )
    ticket_id_domain = fields.Char(
        compute="_compute_ticket_id_domain",
        export_string_translation=False,
    )

    @api.depends_context("voip_log_contact_id")
    def _compute_ticket_id_domain(self):
        if contact := self.env["res.partner"].browse(self.env.context.get("voip_log_contact_id")):
            domain = [("partner_id", "in", contact._search_commercial_partners(active_test=False).ids)]
        else:
            domain = []
        self.ticket_id_domain = domain

    def _get_res_model_fields(self):
        return {**super()._get_res_model_fields(), "helpdesk.ticket": "ticket_id"}

    def _selection_res_model(self):
        res = super()._selection_res_model()
        if self.env.user.has_group("helpdesk.group_helpdesk_user"):
            res += [("helpdesk.ticket", self.env._("Ticket"))]
        return res

    @api.depends("res_model_selection", "ticket_id_domain")
    def _compute_ticket_id(self):
        for activity in self:
            if activity.ticket_id or activity.res_model_selection != "helpdesk.ticket":
                continue
            domain = literal_eval(activity.ticket_id_domain)
            activity.ticket_id = self.env.context.get("default_ticket_id") or activity.env["helpdesk.ticket"].search(
                domain, limit=1, order="id desc",
            )
