from collections import defaultdict

from odoo import api, fields, models
from odoo.addons.mail.tools.discuss import Store


class MailActivity(models.Model):
    _name = "mail.activity"
    _inherit = ["mail.activity", "voip.phone.country.mixin"]

    call_ids = fields.One2many("voip.call", "activity_id")  # Technically One2one

    @api.model
    def create(self, vals_list):
        activities = super().create(vals_list)
        call_activities = activities.filtered(
            lambda activity: activity.phone and activity.user_id and activity.activity_category == "phonecall",
        )
        call_activities.user_id._bus_send("refresh_call_activities", {})
        return activities

    def write(self, vals):
        if "date_deadline" in vals and self.user_id:
            call_activities = self.filtered(
                lambda activity: activity.phone and activity.user_id and activity.activity_category == "phonecall",
            )
            call_activities.user_id._bus_send("refresh_call_activities", {})
        return super().write(vals)

    def action_done(self):
        if self.call_ids:
            self.call_ids.ensure_one()
            self.env.user._bus_send("voip.call/update", {
                "store_data": self.call_ids._get_store_data(),
            })
        return super().action_done()

    @api.model
    @api.readonly
    def get_today_call_activities(self):
        """Retrieve the list of activities that:
          * have the type “phonecall”
          * have a phone number
          * are overdue
          * are assigned to the current user
          * are in the current company or free of document

        The resulting list is intended for display in the “Activities” tab.
        """
        overdue_call_activities_of_current_user = self.search(
            [
                ("activity_type_id.category", "=", "phonecall"),
                ("user_id", "=", self.env.uid),
                ("date_deadline", "<=", "today"),
                ("phone", "!=", False),
            ],
        )
        record_ids_by_model_name = defaultdict(set)
        for activity in overdue_call_activities_of_current_user.filtered("res_model"):
            record_ids_by_model_name[activity.res_model].add(activity.res_id)

        allowed_record_ids_by_model_name = defaultdict(list)
        for model_name, record_ids in record_ids_by_model_name.items():
            if not self.env[model_name].has_access("read"):
                continue
            # calling search will filter out records that are irrelevant to the current company / unlinked
            allowed_record_ids_by_model_name[model_name] = self.env[model_name].search([("id", "in", list(record_ids))]).ids
        activities = overdue_call_activities_of_current_user.filtered(
            lambda activity: (
                not activity.res_model
                or activity.res_id in allowed_record_ids_by_model_name[activity.res_model]
            )
            and activity.activity_type_id.category == "phonecall"
        )
        return Store().add(activities, "_store_voip_fields")

    def _action_done(self, feedback=False, attachment_ids=None):
        """Extends _action_done to notify the user assigned to a phonecall
        activity that it has been marked as done. This is useful to trigger the
        refresh of the "Next Activities" tab. Also links the feedback message
        to the activity's voip.call by zipping returned messages with the
        surviving activities.
        """
        phonecall_activities = self.filtered(
            lambda activity: activity.activity_type_id.category == "phonecall",
        )
        phonecall_activities.user_id._bus_send("refresh_call_activities", {})
        # Capture ongoing activities before calling super, as _action_done will
        # archive them (setting date_done) before returning.
        ongoing = self.filtered(lambda a: not a.date_done)
        messages = super()._action_done(feedback=feedback, attachment_ids=attachment_ids)
        if not phonecall_activities:
            return messages
        # Drop activities that were unlinked during _action_done (their record
        # was cascade-deleted) — they won't have a message in the result.
        ongoing = ongoing.exists()
        # Rebuild the same activity ordering as _action_done's internal loop
        # (_classify_by_model) to ensure correct 1-to-1 pairing with messages.
        ordered_activities = self.env["mail.activity"]
        for data in ongoing.filtered("res_model")._classify_by_model().values():
            ordered_activities |= data["activities"]
        for activity, message in zip(ordered_activities, messages, strict=True):
            if activity.activity_type_id.category == "phonecall" and activity.call_ids:
                activity.call_ids.sudo().activity_mail_message_id = message.id
        return messages

    def _store_voip_fields(self, res: Store.FieldList):
        partner_by_record = defaultdict(self.env["res.partner"].browse)
        for res_model, activities in self.filtered("res_model").grouped("res_model").items():
            records = activities.env[res_model].browse(id_ for id_ in activities.mapped("res_id") if id_)
            for record, partners in records._mail_get_partners(introspect_fields=True).items():
                partner_by_record[record] = partners[:1]
        all_partner_ids = [partner.id for partner in partner_by_record.values()]
        res.extend(["activity_category", "date_deadline"])
        res.many("mail_template_ids", [])
        res.attr("phone")
        res.one("phone_country_id", "_store_voip_fields")
        res.extend(["res_id", "res_model", "res_name", "state", "summary"])
        res.one("user_id", "_store_voip_fields")
        res.one(
            "partner",
            "_store_voip_fields",
            predicate=lambda a: a.res_model and a.res_id,
            value=lambda a: partner_by_record[a.res_id].with_prefetch(all_partner_ids),
        )
