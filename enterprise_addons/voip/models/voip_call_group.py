from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .pbx_service import PBX_DESTINATION_MODELS


class VoipCallGroup(models.Model):
    _name = "voip.call.group"
    _inherit = [
        "voip.call.flow.member.mixin",
        "voip.extension.destination.mixin",
        "voip.pbx.destination.mixin",
    ]
    _description = "PBX Group"

    _call_flow_destination_fields = frozenset({"no_answer_destination_ref"})

    name = fields.Char(required=True)
    user_ids = fields.Many2many(
        "res.users",
        "voip_call_group_user_rel",
        "call_group_id",
        "user_id",
        string="Users",
    )
    user_count = fields.Integer(
        string="User Count",
        compute="_compute_user_count",
    )
    user_display_names = fields.Json(compute="_compute_user_display_names")
    callflow_id = fields.Many2one(
        "voip.call.flow",
        string="Call Flow",
        copy=False,
        index=True,
        ondelete="set null",
        readonly=True,
    )
    no_answer_destination_ref = fields.Reference(
        selection=PBX_DESTINATION_MODELS,
        string="No Answer Destination",
    )
    music_on_hold_id = fields.Many2one(
        "voip.music.on.hold",
        string="Music on Hold",
        ondelete="restrict",
    )
    timeout = fields.Integer(
        default=10,
        help="Maximum number of seconds the call may remain in this group. Set to 0 for no timeout.",
    )
    user_timeout = fields.Integer(
        default=15,
        required=True,
        help="Number of seconds each group member rings before the next attempt.",
    )
    pbx_group_id = fields.Integer(
        string="PBX Group ID",
        copy=False,
        groups="base.group_system",
    )
    pbx_group_uuid = fields.Char(
        string="PBX Group UUID",
        copy=False,
        groups="base.group_system",
    )

    @api.depends("user_ids")
    def _compute_user_count(self):
        for call_group in self:
            call_group.user_count = len(call_group.user_ids)

    @api.depends("user_ids.name")
    def _compute_user_display_names(self):
        for call_group in self:
            call_group.user_display_names = [
                user.display_name for user in call_group.user_ids
            ]

    @api.constrains("timeout", "user_timeout")
    def _check_timeouts(self):
        for call_group in self:
            if call_group.timeout < 0:
                raise ValidationError(
                    self.env._("The Group timeout cannot be negative.")
                )
            if call_group.user_timeout <= 0:
                raise ValidationError(
                    self.env._("The Group user timeout must be positive.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        call_groups = super().create(vals_list)
        if not self.env.context.get("voip_skip_pbx_sync"):
            call_groups.user_ids._select_odoo_voip_provider()
            call_groups._sync_pbx()
        return call_groups

    def write(self, vals):
        queues = self.env["voip.queue"]
        should_sync_queues = (
            "user_ids" in vals
            and not self.env.context.get("voip_skip_pbx_sync")
        )
        if should_sync_queues:
            queues = queues._get_for_call_groups(self)
        users_before = self.user_ids
        res = super().write(vals)
        if "user_ids" in vals and not self.env.context.get("voip_skip_pbx_sync"):
            (self.user_ids - users_before)._select_odoo_voip_provider()
        if (
            {
                "music_on_hold_id",
                "name",
                "no_answer_destination_ref",
                "timeout",
                "user_ids",
                "user_timeout",
            } & vals.keys()
            and not self.env.context.get("voip_skip_pbx_sync")
        ):
            self._sync_pbx()
        if should_sync_queues:
            queues |= queues._get_for_call_groups(self)
            queues._recompute_agents_and_sync_pbx()
        return res

    def unlink(self):  # nosemgrep: unlink-override
        queues = self.env["voip.queue"]
        if not self.env.context.get("voip_skip_pbx_sync"):
            queues = queues.search([("allowed_call_group_ids", "in", self.ids)])
        res = super().unlink()
        if queues:
            queues.invalidate_recordset(["allowed_call_group_ids"])
            queues._recompute_agents_and_sync_pbx()
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_pbx_resources(self):
        if self.env.context.get("voip_skip_pbx_sync"):
            return
        group_uuid_by_id = {
            call_group.id: call_group.pbx_group_uuid
            for call_group in self.sudo().filtered("pbx_group_uuid")
        }
        if not group_uuid_by_id:
            return

        def _delete(env, call_group_id):
            env["voip.pbx.service"]._delete_group(group_uuid=group_uuid_by_id[call_group_id])

        self.env["voip.pbx.service"]._call_after_commit_for_deleted(
            "voip.call.group", list(group_uuid_by_id), _delete,
        )

    def _sync_pbx(self):
        for call_group in self.sudo():
            for user in call_group.user_ids:
                user._sync_pbx_user()
            if (
                call_group.music_on_hold_id
                and not call_group.music_on_hold_id.pbx_moh_name
            ):
                call_group.music_on_hold_id._sync_pbx()
            service = call_group.env["voip.pbx.service"]
            ids = service._sync_group(
                group_id=call_group.pbx_group_id,
                group_uuid=call_group.pbx_group_uuid or None,
                group_name=call_group.name,
                music_on_hold=call_group.music_on_hold_id.pbx_moh_name or None,
                timeout=call_group.timeout or None,
                user_ids=[user.voip_pbx_user_id for user in call_group.user_ids],
                user_timeout=call_group.user_timeout,
            )
            call_group.with_context(voip_skip_pbx_sync=True).write({
                "pbx_group_id": ids["group_id"],
                "pbx_group_uuid": ids["group_uuid"],
            })
            call_group._sync_pbx_routing()

    def _sync_pbx_routing(self):
        """Synchronize the global Wazo fallbacks of an existing Call Group."""
        for call_group in self.sudo().filtered("pbx_group_uuid"):
            service = call_group.env["voip.pbx.service"]
            if call_group.callflow_id:
                destination = call_group.callflow_id._get_record_output_pbx_destinations(
                    call_group, ("no_answer",)
                )["no_answer"]
            else:
                destination = service._get_pbx_destination(
                    call_group.no_answer_destination_ref
                )
            service._update_group_routing(
                group_uuid=call_group.pbx_group_uuid,
                no_answer_destination=destination,
            )
