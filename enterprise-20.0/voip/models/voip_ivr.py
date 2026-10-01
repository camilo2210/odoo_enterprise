import re

from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError

from .pbx_service import PBX_DESTINATION_MODELS
from .voip_sound import PBX_AUDIO_SYNC_FIELDS

IVR_DIGIT_RE = re.compile(r"^[0-9*#]{1,255}$")
# Every key a caller could press skips a "Play Audio" node's message ahead --
# there is no invalid input to report -- so its wrapper Menu is given one
# option per key, all routed to the same "Skip" destination.
AUDIO_MESSAGE_SKIP_DIGITS = ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "#")
PBX_IVR_SYNC_FIELDS = {
    "abort_destination_ref",
    "abort_sound_id",
    "greeting_sound_id",
    "invalid_destination_ref",
    "invalid_sound_id",
    "max_tries",
    "menu_sound_id",
    "name",
    "option_ids",
    "timeout",
    "timeout_destination_ref",
}
IVR_DESTINATION_FIELDS = {
    "abort_destination_ref",
    "invalid_destination_ref",
    "timeout_destination_ref",
}


class VoipIvr(models.Model):
    _name = "voip.ivr"
    _inherit = [
        "voip.call.flow.member.mixin",
        "voip.pbx.destination.mixin",
    ]
    _inherits = {"voip.sound": "menu_sound_id"}
    _description = "PBX IVR"

    _call_flow_destination_fields = frozenset(IVR_DESTINATION_FIELDS)

    pbx_ivr_id = fields.Integer(string="PBX IVR ID", copy=False, groups="base.group_system")
    menu_sound_id = fields.Many2one(
        "voip.sound",
        string="Menu Sound",
        required=True,
        ondelete="cascade",
        help=(
            "Prompts callers to choose an input. Callers can enter an input while this sound "
            "is playing; the timeout starts after it finishes."
        ),
    )
    greeting_sound_id = fields.Many2one(
        "voip.sound",
        string="Greeting Sound",
        help=(
            "Optional introduction played once before the menu sound. Callers cannot enter a "
            "menu input while it is playing and must wait for the menu sound to start."
        ),
    )
    max_tries = fields.Integer(default=3, required=True)
    invalid_destination_ref = fields.Reference(
        selection=PBX_DESTINATION_MODELS,
        string="Invalid Destination",
    )
    invalid_sound_id = fields.Many2one("voip.sound", string="Invalid Sound")
    timeout = fields.Integer(default=5, required=True)
    timeout_destination_ref = fields.Reference(
        selection=PBX_DESTINATION_MODELS,
        string="Timeout Destination",
    )
    abort_destination_ref = fields.Reference(
        selection=PBX_DESTINATION_MODELS,
        string="Abort Destination",
    )
    abort_sound_id = fields.Many2one("voip.sound", string="Abort Sound")
    option_ids = fields.One2many("voip.ivr.option", "ivr_id", string="Inputs")
    input_count = fields.Integer(string="Input Count", compute="_compute_input_count")
    # A "Play Audio" node's wrapper Menu: every option routes to the same
    # "Skip" destination, so it is synced and pushed to the PBX differently
    # from a real Menu -- see _sync_graph_ivrs and _get_pbx_sync_values.
    is_audio_message = fields.Boolean(readonly=True, copy=False)
    callflow_id = fields.Many2one(
        "voip.call.flow",
        string="Call Flow",
        copy=False,
        index=True,
        ondelete="set null",
        readonly=True,
    )

    _menu_sound_unique = models.Constraint(
        "unique(menu_sound_id)",
        "A menu sound can only belong to one Menu.",
    )

    @api.depends("option_ids")
    def _compute_input_count(self):
        for ivr in self:
            ivr.input_count = len(ivr.option_ids)

    @api.constrains("max_tries", "timeout")
    def _check_positive_values(self):
        for ivr in self:
            if ivr.max_tries <= 0:
                raise ValidationError(_("The maximum number of tries must be positive."))
            if ivr.timeout < 0:
                raise ValidationError(_("The timeout cannot be negative."))

    def action_generate_tts(self):
        return self.menu_sound_id.action_generate_tts()

    @api.model
    def get_or_create_audio_message_wrapper(self, sound_id):
        """Return the Menu wrapping ``sound_id`` for a "Play Audio" node.

        Not prefixed with an underscore: the flow editor calls this over
        RPC when a "Play Audio" node's sound is picked, and Odoo refuses to
        dispatch remote calls to private methods.

        A "Play Audio" node needs a real PBX destination to have an output
        at all, and the only PBX primitive that plays a sound and then
        keeps routing is a Menu (IVR), via its timeout branch -- there is
        no bare "play sound then continue". A Menu can only ever wrap one
        sound (see ``_menu_sound_unique``), so a sound already wrapped
        elsewhere is duplicated rather than reused: two "Play Audio" nodes
        playing "the same" message each get their own dedicated Menu.

        Every key the caller could press is given its own option (all
        routed the same way, see ``_sync_graph_ivrs``), so "Skip" fires
        regardless of which one is pressed -- there is no invalid input to
        report.

        ``name`` is left untouched (delegated to the sound's own, see
        ``_inherits``): prefixing it with the call flow's name here would
        double up every time an already-wrapped sound is duplicated below,
        since ``copy()`` already appends " (copy)" to it on its own.
        """
        sound = self.env["voip.sound"].browse(sound_id).exists()
        if not sound:
            raise ValidationError(self.env._("The selected audio message no longer exists."))
        if self.search_count([("menu_sound_id", "=", sound.id)], limit=1):
            sound = sound.copy()
        wrapper = self.with_context(voip_call_flow_node_configuration=True).create({
            "menu_sound_id": sound.id,
            "is_audio_message": True,
            "max_tries": 1,
            "timeout": max(1, round(sound._get_duration_seconds())),
            "option_ids": [
                Command.create({"digit": digit}) for digit in AUDIO_MESSAGE_SKIP_DIGITS
            ],
        })
        return wrapper.id

    @api.model_create_multi
    def create(self, vals_list):
        ivrs = super(VoipIvr, self.with_context(voip_skip_pbx_sync=True)).create(vals_list)
        if not (
            self.env.context.get("voip_skip_pbx_sync")
            or self.env.context.get("voip_call_flow_node_configuration")
        ):
            ivrs.with_context(voip_skip_pbx_sync=False)._sync_pbx()
        return ivrs.with_context(self.env.context)

    def write(self, vals):
        vals = dict(vals)
        sound_vals = {
            field_name: vals.pop(field_name)
            for field_name in tuple(vals)
            if self._fields[field_name].inherited
            and self._fields[field_name].related_field.model_name == "voip.sound"
        }
        if (
            "option_ids" in vals
            and self.callflow_id
            and not (
                self.env.context.get("voip_call_flow_node_configuration")
                or self.env.context.get("voip_call_flow_sync")
            )
        ):
            raise ValidationError(self.env._(
                "The options of an IVR used in a Call Flow "
                "can only be modified from that Call Flow."
            ))
        if sound_vals:
            self.menu_sound_id.with_context(voip_skip_pbx_sync=True).write(sound_vals)
        res = super(VoipIvr, self.with_context(voip_skip_pbx_sync=True)).write(vals)
        if (
            (PBX_IVR_SYNC_FIELDS | PBX_AUDIO_SYNC_FIELDS | {"callflow_id"})
            & (vals.keys() | sound_vals.keys())
            and not self.env.context.get("voip_skip_pbx_sync")
            and not self.env.context.get("voip_call_flow_node_configuration")
        ):
            self._sync_pbx()
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_pbx_resources(self):
        if not self.env.context.get("voip_skip_pbx_sync"):
            pbx_ivr_id_by_id = {
                ivr.id: ivr.pbx_ivr_id
                for ivr in self.sudo().filtered("pbx_ivr_id")
            }
            if pbx_ivr_id_by_id:
                def _delete(env, ivr_id):
                    env["voip.pbx.service"]._delete_ivr(ivr_id=pbx_ivr_id_by_id[ivr_id])

                self.env["voip.pbx.service"]._call_after_commit_for_deleted(
                    "voip.ivr", list(pbx_ivr_id_by_id), _delete,
                )
        self.menu_sound_id.unlink()

    def _sync_pbx(self, excluded_option_ids=()):
        if self.env.context.get("voip_skip_pbx_sync"):
            return
        for ivr in self.sudo():
            ivr._get_sounds()._sync_pbx()
            ivr._ensure_pbx_ivr()
            result = ivr.env["voip.pbx.service"]._sync_ivr(
                **ivr._get_pbx_sync_values(excluded_option_ids=excluded_option_ids)
            )
            ivr.with_context(voip_skip_pbx_sync=True).pbx_ivr_id = result["ivr_id"]

    def _get_sounds(self):
        self.ensure_one()
        sounds = (
            self.menu_sound_id
            | self.greeting_sound_id
            | self.invalid_sound_id
            | self.abort_sound_id
        )
        for option in self.option_ids:
            if (
                option.destination_ref
                and option.destination_ref._name == "voip.sound"
            ):
                sounds |= option.destination_ref
        return sounds

    def _ensure_pbx_ivr(self):
        self.ensure_one()
        if self.pbx_ivr_id:
            return
        result = self.env["voip.pbx.service"]._sync_ivr(
            ivr_id=None,
            ivr_name=self.name,
            description=None,
            menu_sound=self._get_pbx_sound_filename(self.menu_sound_id),
            greeting_sound=self._get_pbx_sound_filename(self.greeting_sound_id),
            max_tries=self.max_tries,
            invalid_destination=None,
            invalid_sound=self._get_pbx_sound_filename(self.invalid_sound_id),
            timeout=self.timeout,
            timeout_destination=None,
            abort_destination=None,
            abort_sound=self._get_pbx_sound_filename(self.abort_sound_id),
            choices=[],
        )
        self.with_context(voip_skip_pbx_sync=True).pbx_ivr_id = result["ivr_id"]

    def _get_pbx_sync_values(self, excluded_option_ids=()):
        self.ensure_one()
        service = self.env["voip.pbx.service"]
        options = self.option_ids.filtered(lambda option: option.id not in excluded_option_ids)
        # A "Play Audio" wrapper has no per-option output of its own to
        # resolve from the graph (see _sync_graph_ivrs): _get_record_output_
        # pbx_destinations would find no "option-N" port and drop every
        # choice. _sync_graph_ivrs already wrote each option's own
        # destination_ref directly, so read those like a callflow-less IVR.
        if self.callflow_id and not self.is_audio_message:
            output_ids = tuple(
                [f"option-{option.id}" for option in options]
                + ["invalid", "timeout", "abort"]
            )
            destinations = self.callflow_id._get_record_output_pbx_destinations(
                self, output_ids
            )
        else:
            options = options.filtered("destination_ref")
            destinations = {
                "abort": service._get_pbx_destination(self.abort_destination_ref),
                "invalid": service._get_pbx_destination(self.invalid_destination_ref),
                "timeout": service._get_pbx_destination(self.timeout_destination_ref),
                **{
                    f"option-{option.id}": service._get_pbx_destination(
                        option.destination_ref
                    )
                    for option in options
                },
            }
        return {
            "ivr_id": self.pbx_ivr_id,
            "ivr_name": self.name,
            "description": None,
            "menu_sound": self._get_pbx_sound_filename(self.menu_sound_id),
            "greeting_sound": self._get_pbx_sound_filename(self.greeting_sound_id),
            "max_tries": self.max_tries,
            "invalid_destination": destinations["invalid"],
            "invalid_sound": self._get_pbx_sound_filename(self.invalid_sound_id),
            "timeout": self.timeout,
            "timeout_destination": destinations["timeout"],
            "abort_destination": destinations["abort"],
            "abort_sound": self._get_pbx_sound_filename(self.abort_sound_id),
            "choices": [
                {
                    "digit": option.digit,
                    "destination": destinations[f"option-{option.id}"],
                }
                for option in options
                if destinations[f"option-{option.id}"]
            ],
        }

    def _get_pbx_sound_filename(self, sound):
        if not sound:
            return None
        return sound._get_pbx_sound_filename()


class VoipIvrOption(models.Model):
    _name = "voip.ivr.option"
    _description = "PBX IVR Option"
    _order = "digit, id"

    ivr_id = fields.Many2one("voip.ivr", required=True, ondelete="cascade")
    digit = fields.Char(required=True)
    destination_ref = fields.Reference(
        selection=PBX_DESTINATION_MODELS,
        string="Destination",
    )

    _ivr_digit_unique = models.Constraint(
        "unique(ivr_id, digit)",
        "Each digit can only be configured once per IVR.",
    )

    @api.constrains("digit")
    def _check_digit(self):
        for option in self:
            if not IVR_DIGIT_RE.fullmatch(option.digit or ""):
                raise ValidationError(
                    _("The IVR option must contain only digits, '*' or '#'.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        ivrs = self.env["voip.ivr"].browse(
            vals["ivr_id"]
            for vals in vals_list
            if vals.get("ivr_id")
        )
        if (
            ivrs.callflow_id
            and not (
                self.env.context.get("voip_call_flow_node_configuration")
                or self.env.context.get("voip_call_flow_sync")
            )
        ):
            raise ValidationError(self.env._(
                "The options of an IVR used in a Call Flow "
                "can only be modified from that Call Flow."
            ))
        options = super().create(vals_list)
        if not self.env.context.get("voip_skip_pbx_sync"):
            options.ivr_id._sync_pbx()
        return options

    def write(self, vals):
        if (
            self.ivr_id.callflow_id
            and not (
                self.env.context.get("voip_call_flow_node_configuration")
                or self.env.context.get("voip_call_flow_sync")
            )
        ):
            raise ValidationError(self.env._(
                "The options of an IVR used in a Call Flow "
                "can only be modified from that Call Flow."
            ))
        ivrs = self.ivr_id
        res = super().write(vals)
        if not self.env.context.get("voip_skip_pbx_sync"):
            (ivrs | self.ivr_id)._sync_pbx()
        return res

    @api.ondelete(at_uninstall=False)
    def _sync_pbx_before_unlink(self):
        if self.env.context.get("voip_skip_pbx_sync"):
            return
        for ivr, options in self.grouped("ivr_id").items():
            ivr._sync_pbx(excluded_option_ids=options.ids)
