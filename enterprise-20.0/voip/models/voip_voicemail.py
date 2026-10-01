from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.voip.models.res_users_settings import PROVISIONED_NO_ANSWER_TIMEOUT


PBX_VOICEMAIL_GREETING = "unavailable"
PBX_VOICEMAIL_SYNC_FIELDS = {
    "audio_message_id",
    "name",
    "pbx_voicemail_number",
}
PBX_VOICEMAIL_NUMBER_PREFIX = "90"


class VoipVoicemail(models.Model):
    _name = "voip.voicemail"
    _inherit = "voip.pbx.destination.mixin"
    _description = "VoIP Mailbox"
    _order = "name"

    name = fields.Char(required=True)
    mailbox_type = fields.Selection(
        [
            ("personal", "Personal Mailbox"),
            ("shared", "Shared Mailbox"),
        ],
        compute="_compute_mailbox_type",
        string="Type",
    )
    audio_message_id = fields.Many2one(
        "voip.sound",
        string="Sound",
        ondelete="set null",
    )
    email = fields.Char(
        string="Send by Email",
        help=(
            "New recordings are sent to this address. If a personal mailbox "
            "has no address, the user's email is used."
        ),
    )
    user_id = fields.Many2one(
        "res.users",
        string="User",
        copy=False,
        help=(
            "Each Phone user has one personal mailbox, accessible by "
            "long-pressing 1 in Odoo Phone."
        ),
        ondelete="cascade",
        readonly=True,
    )
    pbx_voicemail_id = fields.Integer(
        string="PBX Voicemail ID",
        copy=False,
        groups="base.group_system",
    )
    pbx_voicemail_number = fields.Char(
        string="Mailbox Number",
        copy=False,
        groups="voip.group_voip_admin",
        help="Long-press 1 in Odoo Phone to access your personal mailbox.",
        readonly=True,
    )
    message_ids = fields.One2many("voip.voicemail.message", "voicemail_id", string="Messages")
    message_count = fields.Integer(compute="_compute_message_count")

    _unique_user_id = models.UniqueIndex(
        "(user_id) WHERE user_id IS NOT NULL",
        message="A user can only have one personal mailbox.",
    )

    @api.depends("user_id")
    def _compute_mailbox_type(self):
        for mailbox in self:
            mailbox.mailbox_type = "personal" if mailbox.user_id else "shared"

    @api.depends("message_ids")
    def _compute_message_count(self):
        for mailbox in self:
            mailbox.message_count = len(mailbox.message_ids)

    def action_open_messages(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Messages"),
            "res_model": "voip.voicemail.message",
            "view_mode": "list",
            "views": [(self.env.ref("voip.voip_voicemail_message_view_list").id, "list")],
            "domain": [("voicemail_id", "=", self.id)],
        }

    @api.constrains("user_id")
    def _check_unique_shared_mailbox(self):
        # Wazo only allows a single "global" voicemail per context, and every
        # mailbox in a tenant shares the same one - see _op_sync_voicemail in
        # phone_service.
        for voicemail in self.filtered(lambda record: not record.user_id):
            if voicemail.search_count([
                ("id", "!=", voicemail.id),
                ("user_id", "=", False),
            ], limit=1):
                raise ValidationError(_("Only one shared mailbox is allowed."))

    @api.constrains("pbx_voicemail_number")
    def _check_pbx_voicemail_number(self):
        for voicemail in self:
            if not voicemail.pbx_voicemail_number:
                continue
            if not voicemail.pbx_voicemail_number.isdigit():
                raise ValidationError(_("The mailbox number must contain only digits."))
            if voicemail.search_count([
                ("id", "!=", voicemail.id),
                ("pbx_voicemail_number", "=", voicemail.pbx_voicemail_number),
            ], limit=1):
                raise ValidationError(_("The mailbox number must be unique."))

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and any(vals.get("user_id") for vals in vals_list):
            raise ValidationError(_(
                "Personal mailboxes are created automatically for Phone users.",
            ))
        new_shared_count = sum(1 for vals in vals_list if not vals.get("user_id"))
        if new_shared_count and self.search_count([("user_id", "=", False)], limit=1):
            raise ValidationError(_("Only one shared mailbox is allowed."))
        if new_shared_count > 1:
            raise ValidationError(_("Only one shared mailbox is allowed."))
        voicemails = super().create(vals_list)
        for voicemail in voicemails.filtered(lambda record: not record.pbx_voicemail_number):
            voicemail.with_context(
                voip_skip_pbx_sync=True,
            ).pbx_voicemail_number = voicemail._get_default_pbx_voicemail_number()
        if not self.env.context.get("voip_skip_pbx_sync"):
            voicemails._sync_pbx()
        return voicemails

    def write(self, vals):
        if "user_id" in vals and any(
            mailbox.user_id.id != vals["user_id"] for mailbox in self
        ):
            raise ValidationError(_("A mailbox cannot be changed between personal and shared."))
        res = super().write(vals)
        if (
            PBX_VOICEMAIL_SYNC_FIELDS & vals.keys()
            and not self.env.context.get("voip_skip_pbx_sync")
        ):
            self._sync_pbx()
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_pbx_resources(self):
        if self.filtered("user_id"):
            raise ValidationError(_("Personal mailboxes cannot be deleted."))
        if self.env.context.get("voip_skip_pbx_sync"):
            return
        pbx_voicemail_id_by_id = {
            voicemail.id: voicemail.pbx_voicemail_id
            for voicemail in self.sudo().filtered("pbx_voicemail_id")
        }
        if not pbx_voicemail_id_by_id:
            return

        def _delete(env, voicemail_id):
            env["voip.pbx.service"]._delete_voicemail(
                voicemail_id=pbx_voicemail_id_by_id[voicemail_id],
            )

        self.env["voip.pbx.service"]._call_after_commit_for_deleted(
            "voip.voicemail", list(pbx_voicemail_id_by_id), _delete,
        )

    def _sync_pbx(self):
        for voicemail in self.sudo():
            service = voicemail.env["voip.pbx.service"]
            voicemail_id = voicemail._sync_pbx_voicemail(service)
            voicemail._sync_pbx_greeting(service, voicemail_id)

    def _sync_pbx_voicemail(self, service):
        self.ensure_one()
        result = service._sync_voicemail(
            voicemail_id=self.pbx_voicemail_id,
            voicemail_name=self.name,
            voicemail_number=self.pbx_voicemail_number
            or self._get_default_pbx_voicemail_number(),
            email=None,
            attach_audio=True,
            user_id=self.user_id.voip_pbx_user_id or None,
        )
        voicemail_id = result["voicemail_id"]
        self.with_context(voip_skip_pbx_sync=True).write({
            "pbx_voicemail_id": voicemail_id,
            "pbx_voicemail_number": self.pbx_voicemail_number
            or self._get_default_pbx_voicemail_number(),
        })
        return voicemail_id

    def _sync_pbx_greeting(self, service, voicemail_id):
        self.ensure_one()
        if self.audio_message_id:
            service._upload_voicemail_greeting(
                voicemail_id,
                PBX_VOICEMAIL_GREETING,
                self.audio_message_id._get_telephony_wav_content(),
            )
        else:
            service._delete_voicemail_greeting(
                voicemail_id,
                PBX_VOICEMAIL_GREETING,
            )

    def _get_default_pbx_voicemail_number(self):
        self.ensure_one()
        if self.user_id.routing_extension_id:
            return self.user_id.routing_extension_id.number
        return f"{PBX_VOICEMAIL_NUMBER_PREFIX}{self.id}"

    @api.model
    def _ensure_for_user(self, user):
        user.ensure_one()
        voicemail = self.sudo().search([("user_id", "=", user.id)], limit=1)
        if voicemail:
            voicemail_number = voicemail._get_default_pbx_voicemail_number()
            if voicemail_number and voicemail.pbx_voicemail_number != voicemail_number:
                voicemail.pbx_voicemail_number = voicemail_number
            elif not self.env.context.get("voip_skip_pbx_sync"):
                voicemail._sync_pbx()
            return voicemail
        voicemail = self.sudo().create({
            "email": user.email,
            "name": user.name,
            "pbx_voicemail_number": user.routing_extension_id.number,
            "user_id": user.id,
        })
        settings = user.env["res.users.settings"].sudo()._find_or_create_for_user(user)
        vals = {}
        if not settings.voip_no_answer_destination_type:
            if not settings.voip_no_answer_timeout:
                vals["voip_no_answer_timeout"] = PROVISIONED_NO_ANSWER_TIMEOUT
            vals.update({
                "voip_no_answer_destination_type": "forward",
                "voip_no_answer_destination_kind": "voip.voicemail",
                "voip_no_answer_destination_ref": f"voip.voicemail,{voicemail.id}",
            })
        if vals:
            settings.write(vals)
        return voicemail

    def _get_recipient_email(self):
        self.ensure_one()
        return self.email or self.user_id.email
