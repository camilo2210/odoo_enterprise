from odoo import fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools.translate import _


class VoipActivityMixin(models.AbstractModel):
    _name = 'voip.activity.mixin'
    _description = "VoIP multi-activity creation support"

    def create_call_activity(self):
        record_ids_with_activity = {
            res_id
            for res_id, in self.env["mail.activity"]._read_group(
                [
                    ("res_id", "in", self.ids),
                    ("res_model", "=", self._name),
                    ("user_id", "=", self.env.uid),
                    ("activity_type_id.category", "=", "phonecall"),
                    ("date_deadline", "<=", "today"),
                    ("phone", "!=", False),
                ],
                ["res_id"],
            )
        }
        records_to_add = self.filtered(lambda record: record.id not in record_ids_with_activity)
        if not records_to_add:
            return self.env["mail.activity"]

        # Ensure that a phonecall activity type exists beforehand, otherwise
        # create one. This is important because we rely on this type to retrieve
        # the activities to be displayed in the Next Activities tab.
        phonecall_activity_type_id = self.env["ir.model.data"]._xmlid_to_res_id(
            "mail.mail_activity_data_call", raise_if_not_found=False,
        )
        if not phonecall_activity_type_id:
            phonecall_activity_type_id = self.env["mail.activity.type"].search([
                Domain.OR([[("res_model", "=", False)], [("res_model", "=", self._name)]]), ("category", "=", "phonecall"),
            ], limit=1).id
        if not phonecall_activity_type_id:
            phonecall_activity_type_id = self.env["mail.activity.type"].sudo().create({
                "category": "phonecall",
                "delay_count": 2,
                "icon": "phone",
                "name": _("Call"),
                "sequence": 999,
            }).id
        date_deadline = fields.Date.context_today(self)
        res_model_id = self.env["ir.model"]._get_id(self._name)
        activities = self.env["mail.activity"].create([
            {
                "activity_type_id": phonecall_activity_type_id,
                "date_deadline": date_deadline,
                "res_id": record.id,
                "res_model_id": res_model_id,
                "user_id": self.env.uid,
            } for record in records_to_add
        ])
        failed_activities = activities.filtered(lambda activity: not activity.phone)
        if failed_activities:
            failed_records = self.browse(failed_activities.mapped("res_id"))
            raise UserError(
                _(
                    "No records were added to the activity queue because some selected records do not have a phone number: "
                    "%(record_names)s.\n"
                    "Let’s add the missing numbers and start the dialing party!",
                    record_names=_(", ").join(failed_records.mapped("display_name")),
                ),
            )
        return activities
