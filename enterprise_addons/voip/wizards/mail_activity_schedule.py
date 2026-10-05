from odoo import api, fields, models
from odoo.fields import Domain


class MailActivitySchedule(models.TransientModel):
    _inherit = "mail.activity.schedule"

    # voip log activity related fields
    call_id = fields.Many2one("voip.call", export_string_translation=False)
    is_in_call = fields.Boolean(compute="_compute_is_in_call", export_string_translation=False)
    res_model_selection = fields.Selection(
        selection="_selection_res_model",
        string="Related Model",
        inverse="_inverse_res_model_selection",
        store=False,
    )
    contact_id = fields.Many2one(
        "res.partner",
        compute="_compute_contact_id",
        store=False,
        readonly=False,
    )
    contact_id_domain = fields.Char(
        compute="_compute_contact_id_domain",
        export_string_translation=False,
    )
    activity_type_id_domain = fields.Char(
        compute="_compute_activity_type_id_domain",
        export_string_translation=False,
    )

    @api.depends("res_model_selection")
    def _compute_activity_type_id_domain(self):
        for activity in self:
            # activity.res_model is not reliable, compute it from res_model_selection instead
            res_model = activity._get_res_model_from_selection(
                activity.res_model_selection,
            )
            activity.activity_type_id_domain = Domain([("category", "=", "phonecall")]) & (
                Domain([("res_model", "=", res_model)]) |
                Domain([("res_model", "=", False)])
            )

    @api.depends_context("voip_log_contact_id")
    def _compute_contact_id(self):
        self.contact_id = self.env.context.get("voip_log_contact_id")

    @api.depends_context("voip_log_contact_id")
    def _compute_contact_id_domain(self):
        if contact := self.env["res.partner"].browse(self.env.context.get("voip_log_contact_id")):
            domain = [("id", "in", contact._search_commercial_partners().ids)]
        else:
            domain = []
        self.contact_id_domain = domain

    @api.depends(lambda self: ("res_model_selection", *self._get_res_model_fields().values()))
    def _compute_res_ids(self):
        super()._compute_res_ids()
        fields_map = self._get_res_model_fields()
        for activity in self:
            field_name = fields_map.get(activity.res_model_selection)
            if not field_name:
                continue
            record = activity[field_name]
            activity.res_ids = f"{[record.id]}" if record else False

    def _get_res_model_fields(self):
        """Return the mapping {res_model_selection: field_name} used to
        populate res_ids from the corresponding many2one field.

        Extension modules override this method to register their own field,
        e.g. ``{"crm.lead": "lead_id"}`` in voip_crm.
        """
        return {"res.partner": "contact_id"}

    @api.depends("call_id.state")
    def _compute_is_in_call(self):
        for activity in self:
            call = activity.call_id
            activity.is_in_call = call and (call.state == "ongoing" or call.state == "calling")

    def _inverse_res_model_selection(self):
        """Sync res_model when the user changes res_model_selection"""
        for activity in self:
            if not activity.res_model_selection:
                continue
            activity.res_model = activity._get_res_model_from_selection(
                activity.res_model_selection,
            )

    def _selection_res_model(self):
        return [("res.partner", self.env._("Contact"))]

    def _action_schedule_activities(self):
        activity = super()._action_schedule_activities()
        if self.call_id and not self.env.context.get("voip_schedule_activity"):
            self.call_id.sudo().activity_id = activity
            if not self.call_id.sudo().partner_id and (
                partner := self._get_partner_from_target()
            ):
                self.call_id.sudo().partner_id = partner.id
            self.env.user._bus_send(
                "voip.call/update", {
                    "store_data": self.call_id._get_store_data(),
                },
            )
        return activity

    def _get_partner_from_target(self):
        record = self._get_applied_on_records()
        if self.res_model == "res.partner":
            return record
        if "partner_id" in record._fields:
            return record.partner_id
        return self.env["res.partner"]

    def _get_res_model_from_selection(self, selection_key):
        """Map a res_model_selection key to an actual model name.
        Override for special mappings (e.g. sale.subscription -> sale.order)."""
        return selection_key
