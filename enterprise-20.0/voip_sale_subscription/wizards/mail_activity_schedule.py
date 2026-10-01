from ast import literal_eval

from odoo import api, fields, models


class MailActivitySchedule(models.TransientModel):
    _inherit = "mail.activity.schedule"

    subscription_id = fields.Many2one(
        "sale.order",
        compute="_compute_subscription_id",
        store=False,
        readonly=False,
    )
    subscription_id_domain = fields.Char(
        compute="_compute_subscription_id_domain",
        export_string_translation=False,
    )

    @api.depends_context("voip_log_contact_id")
    def _compute_subscription_id_domain(self):
        if contact := self.env["res.partner"].browse(self.env.context.get("voip_log_contact_id")):
            subscription_id_domain = [
                ("partner_id", "in", contact._search_commercial_partners(active_test=False).ids),
                ("is_subscription", "=", True),
                ("subscription_state", "in", ["3_progress", "6_churn", "4_paused"]),
            ]
        else:
            subscription_id_domain = []
        self.subscription_id_domain = subscription_id_domain

    def _get_res_model_fields(self):
        return {**super()._get_res_model_fields(), "sale.subscription": "subscription_id"}

    def _selection_res_model(self):
        res = super()._selection_res_model()
        if self.env.user.has_group("sales_team.group_sale_salesman"):
            res += [("sale.subscription", self.env._("Subscription"))]
        return res

    def _get_res_model_from_selection(self, selection_key):
        """Map sale.subscription to the actual sale.order model"""
        if selection_key == "sale.subscription":
            return "sale.order"
        return super()._get_res_model_from_selection(selection_key)

    @api.depends("res_model_selection", "subscription_id_domain")
    def _compute_subscription_id(self):
        for activity in self:
            if activity.subscription_id or activity.res_model_selection != "sale.subscription":
                continue
            domain = literal_eval(activity.subscription_id_domain)
            activity.subscription_id = activity.env["sale.order"].search(domain, limit=1, order="id desc")
