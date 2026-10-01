import base64
import logging

from odoo import _, api, models
from odoo.exceptions import ValidationError
from odoo.modules.registry import Registry

from odoo.addons.voip.models.phone_service_api import CLIENT_UUID_PARAM, PhoneServiceAPI

_logger = logging.getLogger(__name__)

PBX_DEFAULT_RINGING_TIME = 32
PBX_SYNC_USER_TIMEOUT = 35
PBX_TENANT_RECOVERY_SCHEMA_VERSION = 1
PBX_DESTINATION_MODELS = [
    ("voip.extension", "Extension"),
    ("voip.call.group", "Group"),
    ("voip.ivr", "Menu"),
    ("voip.queue", "Queue"),
    ("voip.sound", "Sound"),
    ("res.users", "User"),
    ("res.partner", "Contact"),
    ("voip.voicemail", "Voice Mailbox"),
]
PBX_INCALL_DESTINATION_MODELS = [
    ("voip.call.flow", "Call Flow"),
    *PBX_DESTINATION_MODELS,
]
PBX_USER_FORWARD_DESTINATION_MODELS = [
    destination
    for destination in PBX_DESTINATION_MODELS
    if destination[0] != "res.partner"
]
PBX_USER_FORWARD_DESTINATION_KINDS = [
    *PBX_USER_FORWARD_DESTINATION_MODELS,
    ("external", "External"),
]
PBX_USER_FORWARD_DESTINATION_TYPES = [
    ("forward", "Forward"),
    ("none", "Don't Forward"),
]
# Destinations that represent an organizational identity a user could
# legitimately want to borrow as their outgoing caller ID (as opposed to a
# personal line, or a destination like a contact/voicemail/sound that isn't
# anyone's identity). These numbers are shown to every user, not just to
# whoever they happen to be linked to.
SHARED_DESTINATION_TYPE_BY_MODEL = {
    "voip.call.group": "call_group",
    "voip.queue": "queue",
    "voip.ivr": "ivr",
    "voip.call.flow": "call_flow",
}


class PBXService(models.AbstractModel):
    _name = "voip.pbx.service"
    _description = "PBX API Service"

    @property
    def voip_provider(self):
        return self.env["voip.provider"].get_or_create_odoo_provider()

    @api.model
    def _get_default_user_busy_destination(self):
        return {"type": "hangup", "cause": "busy", "timeout": 5}

    def _call_after_commit(self, func):
        """Run func(env) once this transaction has actually committed.

        Uses a fresh cursor/environment: by the time a postcommit callback
        runs, the current cursor may already be closed, and for a delete the
        records involved no longer exist in it (see Cursor.commit in
        odoo/sql_db.py: postcommit runs after the real commit, possibly
        after self._close()). A full rollback (e.g. an unhandled error, see
        retrying() in odoo/http/retrying.py) clears postcommit without ever
        running it, so func() never fires for a change that got discarded
        that way.

        That guarantee stops there, though: a savepoint rollback does not
        clear postcommit (Savepoint.rollback only clears precommit), so a
        caller catching a failure inside its own savepoint and still
        committing the outer transaction would still run func(). Callers
        for which that matters (anything that must not happen unless a
        specific row is actually gone) should use
        _call_after_commit_for_deleted instead, which re-checks that at run
        time rather than assuming it here.
        """
        dbname = self.env.cr.dbname
        uid = self.env.uid
        context = self.env.context

        @self.env.cr.postcommit.add
        def run_after_commit():
            try:
                with Registry(dbname).cursor() as cr:
                    env = api.Environment(cr, uid, context)
                    func(env)
            except Exception:
                # The try/except sits outside the `with`: catching inside it
                # would let a failed func() still exit the block cleanly, and
                # Cursor.__exit__ commits on a clean exit - persisting any
                # partial writes func() made before failing.
                _logger.exception("Deferred PBX call failed after commit")

    def _call_after_commit_for_deleted(self, model_name, ids, func):
        """Defer func(env, record_id) after commit, once per id in ids, but
        only for ids actually gone by then - and in isolation, so one id's
        PBX call failing doesn't stop the others from being attempted.

        This is the deferred-delete-safe version of _call_after_commit: a
        caller can catch this deletion failing (e.g. blocked by another
        record still referencing it) inside its own savepoint and still
        commit the outer transaction, and a savepoint rollback doesn't clear
        postcommit. Re-checking existence at the point func() actually runs -
        after the real commit, so this is the final, settled state - catches
        that regardless of why the row survived.
        """
        def _run(env):
            deleted_ids = set(ids) - set(env[model_name].sudo().browse(ids).exists().ids)
            for record_id in ids:
                if record_id not in deleted_ids:
                    continue
                try:
                    # Each id gets its own savepoint: if func() writes
                    # through env and then fails, only that id's writes are
                    # rolled back - the other ids' successful writes still
                    # reach the outer commit when this shared fresh cursor
                    # closes cleanly.
                    with env.cr.savepoint():
                        func(env, record_id)
                except Exception:
                    _logger.exception(
                        "Deferred PBX call failed for %s(%s)", model_name, record_id,
                    )

        self._call_after_commit(_run)

    def _get_pbx_destination(self, destination, visited_call_flow_ids=None):
        """Return the PBX routing payload for a supported destination."""
        if not destination:
            return None
        if destination._name == "voip.call.flow":
            return destination._get_pbx_destination(visited_call_flow_ids)
        if destination._name == "voip.extension":
            return {"type": "extension", "exten": destination.number}
        if destination._name == "voip.call.group":
            if not destination.pbx_group_id:
                destination._sync_pbx()
            return {"type": "group", "group_id": destination.pbx_group_id}
        if destination._name == "voip.ivr":
            destination._ensure_pbx_ivr()
            return {"type": "ivr", "ivr_id": destination.pbx_ivr_id}
        if destination._name == "voip.queue":
            if not destination.pbx_queue_id:
                destination._sync_pbx()
            return {"type": "queue", "queue_id": destination.pbx_queue_id}
        if destination._name == "voip.sound":
            return {
                "type": "sound",
                "filename": destination._get_pbx_sound_filename(),
            }
        if destination._name == "res.users":
            if not destination.voip_pbx_user_id:
                destination._sync_pbx_user()
            return {"type": "user", "user_id": destination.voip_pbx_user_id}
        if destination._name == "res.partner":
            phone_number = destination._phone_format(fname="phone")
            if not phone_number:
                raise ValidationError(_(
                    "The contact %(contact)s must have a valid phone number.",
                    contact=destination.display_name,
                ))
            return {"type": "outcall", "exten": phone_number.removeprefix("+")}
        if destination._name == "voip.voicemail":
            if not destination.pbx_voicemail_id:
                destination._sync_pbx()
            return {"type": "voicemail", "voicemail_id": destination.pbx_voicemail_id}
        raise ValidationError(_(
            "The %(model)s model is not a supported PBX destination.",
            model=destination._name,
        ))

    def _get_pbx_recovery_destination(self, destination, visited_call_flow_ids=None):
        """Return a destination independent from identifiers allocated by Wazo."""
        if not destination:
            return None
        if destination._name == "voip.call.flow":
            return destination._get_pbx_recovery_destination(visited_call_flow_ids)
        if destination._name == "voip.extension":
            return {"type": "extension", "exten": destination.number}
        reference_types = {
            "res.users": "user",
            "voip.call.group": "group",
            "voip.ivr": "ivr",
            "voip.queue": "queue",
            "voip.voicemail": "voicemail",
        }
        if destination._name in reference_types:
            return {
                "type": reference_types[destination._name],
                "odoo_id": destination.id,
            }
        if destination._name == "voip.sound":
            return {
                "type": "sound",
                "filename": destination._get_pbx_sound_filename(),
            }
        if destination._name == "res.partner":
            phone_number = destination._phone_format(fname="phone")
            if not phone_number:
                raise ValidationError(_(
                    "The contact %(contact)s must have a valid phone number.",
                    contact=destination.display_name,
                ))
            return {"type": "outcall", "exten": phone_number.removeprefix("+")}
        raise ValidationError(_(
            "The %(model)s model is not a supported PBX destination.",
            model=destination._name,
        ))

    def _get_user_recovery_destination(self, settings, fallback):
        if settings[f"voip_{fallback}_destination_type"] != "forward":
            if fallback == "busy":
                return self._get_default_user_busy_destination()
            return None
        if settings[f"voip_{fallback}_destination_kind"] == "external":
            number = settings[f"voip_{fallback}_outcall_number"]
            return {
                "type": "outcall",
                "exten": number.strip().removeprefix("+"),
            }
        return self._get_pbx_recovery_destination(
            settings[f"voip_{fallback}_destination_ref"],
        )

    def _get_user_recovery_routing(self, settings):
        immediate_forward = (
            settings.voip_no_answer_destination_type == "forward"
            and settings.voip_no_answer_timeout == 0
        )
        return {
            "no_answer_destination": (
                None
                if immediate_forward
                else self._get_user_recovery_destination(settings, "no_answer")
            ),
            "busy_destination": self._get_user_recovery_destination(settings, "busy"),
            "fail_destination": self._get_user_recovery_destination(settings, "disconnected"),
            "always_destination": (
                settings.voip_no_answer_immediate_destination
                if immediate_forward
                else None
            ),
            "no_answer_timeout": settings.voip_no_answer_timeout,
        }

    def _get_record_recovery_destinations(self, record, field_names):
        if record.callflow_id:
            return record.callflow_id._get_record_output_pbx_destinations(
                record, tuple(field_names), recovery=True,
            )
        return {
            name: self._get_pbx_recovery_destination(record[f"{name}_destination_ref"])
            for name in field_names
        }

    @staticmethod
    def _encode_recovery_content(content):
        return base64.b64encode(content).decode()

    def _get_tenant_recovery_payload(self):
        """Describe the complete desired PBX configuration using stable Odoo IDs."""
        env = self.env(su=True)
        provider = env.ref("voip.odoo_provider")
        user_settings = env["res.users.settings"].with_context(active_test=False).search([
            ("voip_provider_id", "=", provider.id),
        ])
        extensions = env["voip.extension"].search([])
        call_groups = env["voip.call.group"].search([])
        queues = env["voip.queue"].search([])
        ivrs = env["voip.ivr"].search([])
        time_conditions = env["voip.time.condition"].search([
            ("callflow_id", "!=", False),
        ])
        voicemails = env["voip.voicemail"].search([])
        sounds = env["voip.sound"].search([
            ("data", "!=", False),
        ])
        music_on_holds = env["voip.music.on.hold"].search([])
        did_numbers = env["voip.did.number"].search([
            ("state", "=", "active"),
            ("destination_ref", "!=", False),
        ])
        users = (
            user_settings.user_id
            | extensions._get_destination_users()
            | call_groups.user_ids
            | queues._get_all_resolved_agent_users()
            | voicemails.user_id
        )
        for records, field_names in (
            (user_settings, ("voip_no_answer_destination_ref", "voip_busy_destination_ref")),
            (call_groups, ("no_answer_destination_ref",)),
            (queues, ("no_answer_destination_ref", "busy_destination_ref")),
            (ivrs, ("invalid_destination_ref", "timeout_destination_ref", "abort_destination_ref")),
            (ivrs.option_ids, ("destination_ref",)),
            (did_numbers, ("destination_ref",)),
        ):
            for record in records:
                for field_name in field_names:
                    destination = record[field_name]
                    if destination and destination._name == "res.users":
                        users |= destination
        call_flows = env["voip.call.flow"].search([("active", "=", True)])
        graph_user_ids = set()
        for call_flow in call_flows:
            for node in (call_flow.graph_data or {}).get("nodes") or []:
                record = node.get("record") if isinstance(node, dict) else None
                if (
                    isinstance(record, dict)
                    and record.get("resModel") == "res.users"
                    and isinstance(record.get("resId"), int)
                ):
                    graph_user_ids.add(record["resId"])
        users |= env["res.users"].with_context(active_test=False).browse(
            graph_user_ids
        ).exists()

        users_payload = []
        for user in users.sorted("id"):
            settings = user.res_users_settings_id
            extension = user.routing_extension_id
            users_payload.append({
                "odoo_id": user.id,
                "name": user.name,
                "login": user.login,
                "sip_secret": settings.voip_secret,
                "extension_odoo_id": extension.id or None,
                "ring_seconds": (
                    extension._get_ring_seconds(settings)
                    if extension
                    else PBX_DEFAULT_RINGING_TIME
                ),
                "simultaneous_calls": settings._get_pbx_simultaneous_calls(),
                "outgoing_caller_id": (
                    extension._get_outgoing_caller_id() if extension else None
                ),
                "routing": self._get_user_recovery_routing(settings),
            })

        groups_payload = []
        for call_group in call_groups.sorted("id"):
            destinations = self._get_record_recovery_destinations(
                call_group, ("no_answer",),
            )
            groups_payload.append({
                "odoo_id": call_group.id,
                "name": call_group.name,
                "user_odoo_ids": call_group.user_ids.ids,
                "music_on_hold_odoo_id": call_group.music_on_hold_id.id or None,
                "timeout": call_group.timeout or None,
                "user_timeout": call_group.user_timeout,
                "no_answer_destination": destinations["no_answer"],
            })

        queues_payload = []
        for queue in queues.sorted("id"):
            destinations = self._get_record_recovery_destinations(
                queue, ("no_answer", "busy"),
            )
            agents = []
            for sequence, user in enumerate(queue._get_resolved_agent_users(), start=1):
                extension = user.routing_extension_id
                names = user._get_pbx_agent_names()
                agents.append({
                    "user_odoo_id": user.id,
                    "extension_number": extension.number or None,
                    "firstname": names["firstname"],
                    "lastname": names["lastname"],
                    "sequence": sequence,
                })
            queues_payload.append({
                "odoo_id": queue.id,
                "name": queue.name,
                "strategy": queue.strategy,
                "agent_timeout": queue.agent_timeout,
                "queue_timeout": queue.queue_timeout,
                "retry_delay": queue.retry_on_timeout,
                "max_waiting_calls": queue.max_waiting_calls,
                "music_on_hold_odoo_id": queue.music_on_hold_id.id or None,
                "agents": agents,
                "no_answer_destination": destinations["no_answer"],
                "busy_destination": destinations["busy"],
            })

        ivrs_payload = []
        for ivr in ivrs.sorted("id"):
            options = ivr.option_ids
            output_names = tuple(
                [f"option-{option.id}" for option in options]
                + ["invalid", "timeout", "abort"]
            )
            if ivr.callflow_id:
                destinations = ivr.callflow_id._get_record_output_pbx_destinations(
                    ivr, output_names, recovery=True,
                )
            else:
                options = options.filtered("destination_ref")
                destinations = {
                    "invalid": self._get_pbx_recovery_destination(
                        ivr.invalid_destination_ref,
                    ),
                    "timeout": self._get_pbx_recovery_destination(
                        ivr.timeout_destination_ref,
                    ),
                    "abort": self._get_pbx_recovery_destination(
                        ivr.abort_destination_ref,
                    ),
                    **{
                        f"option-{option.id}": self._get_pbx_recovery_destination(
                            option.destination_ref,
                        )
                        for option in options
                    },
                }
            ivrs_payload.append({
                "odoo_id": ivr.id,
                "name": ivr.name,
                "description": None,
                "menu_sound": ivr._get_pbx_sound_filename(ivr.menu_sound_id),
                "greeting_sound": ivr._get_pbx_sound_filename(ivr.greeting_sound_id),
                "max_tries": ivr.max_tries,
                "invalid_destination": destinations["invalid"],
                "invalid_sound": ivr._get_pbx_sound_filename(ivr.invalid_sound_id),
                "timeout": ivr.timeout,
                "timeout_destination": destinations["timeout"],
                "abort_destination": destinations["abort"],
                "abort_sound": ivr._get_pbx_sound_filename(ivr.abort_sound_id),
                "choices": [
                    {
                        "digit": option.digit,
                        "destination": destinations[f"option-{option.id}"],
                    }
                    for option in options
                    if destinations[f"option-{option.id}"]
                ],
            })

        schedules_payload = []
        for condition in time_conditions.sorted("id"):
            destinations = condition.callflow_id._get_time_condition_output_pbx_destinations(
                condition, recovery=True,
            )
            schedules_payload.append({
                "odoo_id": condition.id,
                "name": f"Odoo Time Condition {condition.id}: {condition.name}",
                "closed_destination": destinations["closed"],
                "open_periods": [
                    period._get_pbx_values()
                    for period in condition.period_ids.filtered(
                        lambda period: period.mode == "open"
                    )
                ],
                "exceptional_periods": [
                    {
                        **period._get_pbx_values(),
                        "destination": destinations["closed"],
                    }
                    for period in condition.period_ids.filtered(
                        lambda period: period.mode == "closed"
                    )
                ],
                "timezone": condition.timezone,
                "owner": (
                    {
                        "type": "group",
                        "odoo_id": condition.call_group_id.id,
                    }
                    if condition.call_group_id
                    else {
                        "type": "queue",
                        "odoo_id": condition.queue_id.id,
                    }
                    if condition.queue_id
                    else None
                ),
            })

        sounds_payload = [
            {
                "odoo_id": sound.id,
                "filename": sound._get_pbx_sound_filename(),
                "format": sound._get_pbx_sound_format(),
                "content_base64": self._encode_recovery_content(
                    sound._get_pbx_sound_content(),
                ),
            }
            for sound in sounds.sorted("id")
        ]
        music_on_holds_payload = []
        for music_on_hold in music_on_holds.sorted("id"):
            music_on_holds_payload.append({
                "odoo_id": music_on_hold.id,
                "name": music_on_hold.name,
                "sort": music_on_hold.sort,
                "files": [
                    {
                        "filename": (
                            f"{index:03d}_odoo_audio_{track.audio_message_id.id}.wav"
                        ),
                        "sound_odoo_id": track.audio_message_id.id,
                    }
                    for index, track in enumerate(
                        music_on_hold.track_ids.sorted("sequence"), start=1,
                    )
                ],
            })

        voicemails_payload = []
        for voicemail in voicemails.sorted("id"):
            voicemails_payload.append({
                "odoo_id": voicemail.id,
                "name": voicemail.name,
                "number": voicemail.pbx_voicemail_number
                or voicemail._get_default_pbx_voicemail_number(),
                "email": None,
                "attach_audio": True,
                "user_odoo_id": voicemail.user_id.id or None,
                "greeting": "unavailable",
                "greeting_sound_odoo_id": voicemail.audio_message_id.id or None,
            })

        incalls_payload = []
        for did in did_numbers.sorted("id"):
            destination = did.destination_ref
            schedule_odoo_id = None
            if destination._name == "voip.call.flow":
                first_node = destination._get_first_node()
                if first_node and first_node.get("type") == "time_condition":
                    schedule_odoo_id = first_node["record"]["resId"]
            incalls_payload.append({
                "odoo_id": did.id,
                "did_number": did.did_number,
                "destination": self._get_pbx_recovery_destination(destination),
                "schedule_odoo_id": schedule_odoo_id,
            })

        default_outgoing_number = env["voip.did.number"].search([
            ("is_default_outgoing_number", "=", True),
            ("state", "=", "active"),
        ], limit=1)
        return {
            "schema_version": PBX_TENANT_RECOVERY_SCHEMA_VERSION,
            "client_uuid": env["ir.config_parameter"].get_str(CLIENT_UUID_PARAM),
            "default_outgoing_number": default_outgoing_number.did_number or None,
            "sounds": sounds_payload,
            "music_on_holds": music_on_holds_payload,
            "users": users_payload,
            "extensions": [
                {
                    "odoo_id": extension.id,
                    "number": extension.number,
                    "destination": {
                        "model": extension.destination_ref._name,
                        "odoo_id": extension.destination_ref.id,
                    },
                }
                for extension in extensions.sorted("id")
            ],
            "voicemails": voicemails_payload,
            "groups": groups_payload,
            "queues": queues_payload,
            "ivrs": ivrs_payload,
            "schedules": schedules_payload,
            "incalls": incalls_payload,
        }

    # ----- Users, lines, extensions -----

    def _sync_user(self, **kwargs):
        api = PhoneServiceAPI(self.env, request_timeout=PBX_SYNC_USER_TIMEOUT)
        return api.pbx_call("sync_user", **kwargs)

    def _sync_user_extension(self, **kwargs):
        return PhoneServiceAPI(self.env).pbx_call("sync_user_extension", **kwargs)

    def _update_user_routing(self, **kwargs):
        return PhoneServiceAPI(self.env).pbx_call("update_user_routing", **kwargs)

    def _update_user_caller_id(self, **kwargs):
        return PhoneServiceAPI(self.env).pbx_call("update_user_caller_id", **kwargs)

    def _update_default_outgoing_number(self, **kwargs):
        return PhoneServiceAPI(self.env).pbx_call("update_default_outgoing_number", **kwargs)

    def _delete_extension(self, **kwargs):
        return PhoneServiceAPI(self.env).pbx_call("delete_extension", **kwargs)

    # ----- Groups and queues -----

    def _sync_group(self, **kwargs):
        return PhoneServiceAPI(self.env).pbx_call("sync_group", **kwargs)

    def _update_group_routing(self, **kwargs):
        return PhoneServiceAPI(self.env).pbx_call("update_group_routing", **kwargs)

    def _sync_group_extension(self, **kwargs):
        return PhoneServiceAPI(self.env).pbx_call("sync_group_extension", **kwargs)

    def _sync_group_schedule(self, **kwargs):
        return PhoneServiceAPI(self.env).pbx_call("sync_group_schedule", **kwargs)

    def _sync_queue(self, **kwargs):
        return PhoneServiceAPI(self.env).pbx_call("sync_queue", **kwargs)

    def _update_queue_routing(self, **kwargs):
        return PhoneServiceAPI(self.env).pbx_call("update_queue_routing", **kwargs)

    def _sync_queue_extension(self, **kwargs):
        return PhoneServiceAPI(self.env).pbx_call("sync_queue_extension", **kwargs)

    def _sync_queue_schedule(self, **kwargs):
        return PhoneServiceAPI(self.env).pbx_call("sync_queue_schedule", **kwargs)

    def _delete_group(self, **kwargs):
        return PhoneServiceAPI(self.env).pbx_call("delete_group", **kwargs)

    def _delete_queue(self, **kwargs):
        return PhoneServiceAPI(self.env).pbx_call("delete_queue", **kwargs)

    # ----- IVRs -----

    def _sync_ivr(self, **kwargs):
        return PhoneServiceAPI(self.env).pbx_call("sync_ivr", **kwargs)

    def _delete_ivr(self, **kwargs):
        return PhoneServiceAPI(self.env).pbx_call("delete_ivr", **kwargs)

    # ----- Schedules -----

    def _sync_schedule(self, **kwargs):
        return PhoneServiceAPI(self.env).pbx_call("sync_schedule", **kwargs)

    def _delete_schedule(self, **kwargs):
        return PhoneServiceAPI(self.env).pbx_call("delete_schedule", **kwargs)

    # ----- Agents -----

    def _sync_agent(self, **kwargs):
        return PhoneServiceAPI(self.env).pbx_call("sync_agent", **kwargs)

    def _get_agents(self, **kwargs):
        return PhoneServiceAPI(self.env).pbx_call("get_agents", **kwargs)

    def _login_agent_to_queue(self, **kwargs):
        return PhoneServiceAPI(self.env).pbx_call("login_agent_to_queue", **kwargs)

    def _logoff_agent_from_queue(self, **kwargs):
        return PhoneServiceAPI(self.env).pbx_call("logoff_agent_from_queue", **kwargs)

    def _get_queue_status(self, **kwargs):
        return PhoneServiceAPI(self.env).pbx_call("get_queue_status", **kwargs)

    # ----- Voicemail -----

    def _sync_voicemail(self, **kwargs):
        return PhoneServiceAPI(self.env).pbx_call("sync_voicemail", **kwargs)

    def _delete_voicemail(self, **kwargs):
        return PhoneServiceAPI(self.env).pbx_call("delete_voicemail", **kwargs)

    def _upload_voicemail_greeting(self, voicemail_id, greeting, content):
        return PhoneServiceAPI(self.env).pbx_upload_voicemail_greeting(
            voicemail_id=voicemail_id, greeting=greeting, content=content)

    def _delete_voicemail_greeting(self, voicemail_id, greeting):
        return PhoneServiceAPI(self.env).pbx_call(
            "delete_voicemail_greeting", voicemail_id=voicemail_id, greeting=greeting)

    def _get_voicemail_message_recording(self, voicemail_id, message_id):
        return PhoneServiceAPI(self.env).pbx_get_voicemail_message_recording(
            voicemail_id=voicemail_id, message_id=message_id)

    # ----- Sounds -----

    def _upload_sound(self, *, filename, content, sound_format):
        return PhoneServiceAPI(self.env).pbx_upload_sound(
            filename=filename, content=content, sound_format=sound_format)

    # ----- Music on hold -----

    def _sync_moh(self, *, files, **kwargs):
        return PhoneServiceAPI(self.env).pbx_sync_moh(files=files, **kwargs)

    def _delete_moh(self, **kwargs):
        return PhoneServiceAPI(self.env).pbx_call("delete_moh", **kwargs)

    # ----- Incalls -----

    def _sync_incall(self, **kwargs):
        return PhoneServiceAPI(self.env).pbx_call("sync_incall", **kwargs)

    def _delete_incall(self, **kwargs):
        return PhoneServiceAPI(self.env).pbx_call("delete_incall", **kwargs)

    # ----- User deprovisioning -----

    def _deprovision_user(self, user_uuid):
        return PhoneServiceAPI(self.env).pbx_call("deprovision_user", user_uuid=user_uuid)
