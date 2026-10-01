from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from .pbx_service import PBX_DESTINATION_MODELS


PBX_QUEUE_SYNC_FIELDS = {
    "name",
    "allowed_call_group_ids",
    "allowed_user_ids",
    "strategy",
    "agent_timeout",
    "queue_timeout",
    "retry_on_timeout",
    "max_waiting_calls",
    "music_on_hold_id",
    "no_answer_destination_ref",
    "busy_destination_ref",
}


class VoipQueue(models.Model):
    _name = "voip.queue"
    _inherit = [
        "voip.call.flow.member.mixin",
        "voip.extension.destination.mixin",
        "voip.pbx.destination.mixin",
    ]
    _description = "VoIP Queue"

    _call_flow_destination_fields = frozenset({
        "busy_destination_ref",
        "no_answer_destination_ref",
    })

    name = fields.Char(required=True)
    callflow_id = fields.Many2one(
        "voip.call.flow",
        string="Call Flow",
        copy=False,
        index=True,
        ondelete="set null",
        readonly=True,
    )
    pbx_queue_id = fields.Integer(
        string="PBX Queue ID",
        copy=False,
        groups="base.group_system",
    )
    allowed_call_group_ids = fields.Many2many(
        "voip.call.group",
        "voip_queue_allowed_call_group_rel",
        string="Allowed Groups",
    )
    allowed_user_ids = fields.Many2many(
        "res.users",
        "voip_queue_allowed_user_rel",
        string="Allowed Users",
        domain=[("share", "=", False)],
    )
    agent_ids = fields.One2many(
        "voip.queue.agent",
        "queue_id",
        string="Agents",
    )
    resolved_agent_user_ids = fields.Many2many(
        "res.users",
        compute="_compute_resolved_agent_user_ids",
        string="Agent Users",
    )
    resolved_agent_count = fields.Integer(
        string="Agent Count",
        compute="_compute_resolved_agent_count",
    )
    is_current_user_agent = fields.Boolean(compute="_compute_current_user_agent_status")
    is_current_user_logged = fields.Boolean(compute="_compute_current_user_agent_status")
    strategy = fields.Selection(
        [
            ("ringall", "Ring All"),
            ("linear", "Linear"),
            ("rrmemory", "Round Robin"),
            ("leastrecent", "Least Recent"),
            ("fewestcalls", "Fewest Calls"),
            ("random", "Random"),
        ],
        default="ringall",
        help=(
            "Ring All: ring all agents simultaneously.\n"
            "Linear: start with the first agent in the list.\n"
            "Round Robin: start with the agent after the last one to hang up.\n"
            "Least Recent: start with the agent who least recently hung up.\n"
            "Fewest Calls: start with the agent who has answered the fewest calls "
            "since joining the queue.\n"
            "Random: choose an agent randomly."
        ),
        required=True,
    )
    agent_timeout = fields.Integer(
        string="Agent Timeout",
        default=20,
        required=True,
    )
    queue_timeout = fields.Integer(
        string="Queue Timeout",
        default=60,
        help="Maximum number of seconds a call may remain in the queue. Set to 0 for no timeout.",
        required=True,
    )
    retry_on_timeout = fields.Integer(
        string="Retry Delay",
        default=5,
        required=True,
    )
    max_waiting_calls = fields.Integer(
        string="Maximum Waiting Calls",
        default=0,
        required=True,
        help="Maximum number of calls waiting in the queue. Set to 0 for no limit.",
    )
    music_on_hold_id = fields.Many2one(
        "voip.music.on.hold",
        string="Music on Hold",
        ondelete="restrict",
    )
    no_answer_destination_ref = fields.Reference(
        selection=PBX_DESTINATION_MODELS,
        string="No Answer Destination",
    )
    busy_destination_ref = fields.Reference(
        selection=PBX_DESTINATION_MODELS,
        string="Busy Destination",
    )
    agent_connect_code = fields.Char(
        string="Connect Code",
        compute="_compute_agent_connection_codes",
        help="Dial this code in Odoo Phone to connect to this queue.",
    )
    agent_disconnect_code = fields.Char(
        string="Disconnect Code",
        compute="_compute_agent_connection_codes",
        help="Dial this code in Odoo Phone to disconnect from this queue.",
    )

    def _compute_agent_connection_codes(self):
        for queue in self:
            queue.agent_connect_code = f"*55{queue.id}" if queue.id else False
            queue.agent_disconnect_code = f"*56{queue.id}" if queue.id else False

    @api.depends(
        "allowed_call_group_ids",
        "allowed_call_group_ids.user_ids",
        "allowed_user_ids",
    )
    def _compute_resolved_agent_user_ids(self):
        for queue in self:
            queue.resolved_agent_user_ids = queue._get_resolved_agent_users()

    @api.depends(
        "allowed_call_group_ids",
        "allowed_call_group_ids.user_ids",
        "allowed_user_ids",
    )
    def _compute_resolved_agent_count(self):
        for queue in self:
            queue.resolved_agent_count = len(queue._get_resolved_agent_users())

    @api.depends_context("uid")
    @api.depends("agent_ids.is_logged", "agent_ids.user_id")
    def _compute_current_user_agent_status(self):
        current_user = self.env.user
        current_user_agents_by_queue = {
            agent.queue_id: agent
            for agent in self.agent_ids
            if agent.user_id == current_user
        }
        for queue in self:
            agent = current_user_agents_by_queue.get(queue)
            queue.is_current_user_agent = bool(agent)
            queue.is_current_user_logged = agent.is_logged if agent else False

    def action_join_queue(self):
        self._get_current_user_agent().action_login_to_queue()

    def action_leave_queue(self):
        self._get_current_user_agent().action_logoff_from_queue()

    def _get_current_user_agent(self):
        self.ensure_one()
        current_user = self.env.user
        agent = self.agent_ids.filtered(lambda agent: agent.user_id == current_user)
        if not agent:
            raise AccessError(_("Only agents assigned to this queue can join or leave it."))
        return agent

    def _get_resolved_agent_users(self):
        self.ensure_one()
        users = self.allowed_user_ids | self.allowed_call_group_ids.user_ids
        return users - users.filtered("share")

    def _get_all_resolved_agent_users(self):
        users = self.env["res.users"]
        for queue in self:
            users |= queue._get_resolved_agent_users()
        return users

    def _get_resolved_agent_extensions(self):
        """Return one user extension per agent, creating missing extensions."""
        self.ensure_one()
        extensions = self.env["voip.extension"]
        for user in self._get_resolved_agent_users():
            extensions |= self.env["voip.extension"]._find_or_create_for_user(user)
        return extensions

    @api.model
    def _get_for_call_groups(self, call_groups):
        return self.search([
            ("allowed_call_group_ids", "in", call_groups.ids),
        ])

    @api.model
    def _get_for_extensions(self, extensions):
        users = extensions._get_destination_users()
        call_groups = self.env["voip.call.group"].search([
            ("user_ids", "in", users.ids),
        ])
        return self.search([
            ("allowed_user_ids", "in", users.ids),
        ]) | self._get_for_call_groups(call_groups)

    def action_refresh_agent_statuses(self):
        self._refresh_agent_statuses()

    def _refresh_agent_statuses(self):
        if not self.agent_ids:
            return
        service = self.env["voip.pbx.service"]
        wazo_agents = service._get_agents(recurse=True)
        wazo_agents_by_id = {
            agent["id"]: agent
            for agent in wazo_agents
            if agent.get("id")
        }
        queue_members_by_queue_id = {}
        for queue in self.filtered("pbx_queue_id"):
            queue_members_by_queue_id[queue.id] = service._get_queue_status(
                odoo_queue_id=queue.id,
            ).get("members", [])
        self.agent_ids._refresh_statuses_from_wazo(
            wazo_agents_by_id,
            queue_members_by_queue_id=queue_members_by_queue_id,
        )

    def _defer_refresh_agent_statuses(self):
        """Refresh agent statuses after this transaction commits.

        Only the Wazo-status display depends on this, not call routing, so
        it doesn't need to hold up the save - and a read taken after commit
        reflects the agents/queues as they really ended up, instead of a
        snapshot from before the write that triggered it.

        Deduplicated per transaction via postcommit.data: create() and
        write() can each ask for a refresh on the same queue within the
        same transaction (e.g. a new queue saved with agents already
        assigned), and this ensures only one _get_agents() round trip
        happens for it instead of one per call site.
        """
        if not self:
            return
        pending_ids = self.env.cr.postcommit.data.setdefault(
            "voip_queue_refresh_agent_statuses", set()
        )
        is_first_request = not pending_ids
        pending_ids.update(self.ids)
        if not is_first_request:
            return
        self.env["voip.pbx.service"]._call_after_commit(
            lambda env: env["voip.queue"].browse(list(pending_ids)).exists()._refresh_agent_statuses()
        )

    def _recompute_agents_and_sync_pbx(self):
        self.invalidate_recordset(["resolved_agent_user_ids", "resolved_agent_count"])
        self._sync_pbx()
        self._defer_refresh_agent_statuses()

    @api.model_create_multi
    def create(self, vals_list):
        queues = super().create(vals_list)
        if not self.env.context.get("voip_skip_pbx_sync"):
            queues._get_all_resolved_agent_users()._select_odoo_voip_provider()
            queues._sync_pbx()
            queues._defer_refresh_agent_statuses()
        return queues

    def write(self, vals):
        assignment_fields = {"allowed_call_group_ids", "allowed_user_ids"}
        should_sync_pbx = not self.env.context.get("voip_skip_pbx_sync")
        users_before = self.env["res.users"]
        if should_sync_pbx and assignment_fields & vals.keys():
            users_before = self._get_all_resolved_agent_users()
        res = super().write(vals)
        if should_sync_pbx and assignment_fields & vals.keys():
            (self._get_all_resolved_agent_users() - users_before)._select_odoo_voip_provider()
        if should_sync_pbx and PBX_QUEUE_SYNC_FIELDS & vals.keys():
            self._sync_pbx()
        if should_sync_pbx and assignment_fields & vals.keys():
            self._defer_refresh_agent_statuses()
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_pbx_resources(self):
        if self.env.context.get("voip_skip_pbx_sync"):
            return
        pbx_queue_id_by_id = {
            queue.id: queue.pbx_queue_id
            for queue in self.sudo().filtered("pbx_queue_id")
        }
        if not pbx_queue_id_by_id:
            return

        def _delete(env, queue_id):
            env["voip.pbx.service"]._delete_queue(queue_id=pbx_queue_id_by_id[queue_id])

        self.env["voip.pbx.service"]._call_after_commit_for_deleted(
            "voip.queue", list(pbx_queue_id_by_id), _delete,
        )

    def _sync_pbx(self):
        # write() calls this whenever a PBX_QUEUE_SYNC_FIELDS field changes,
        # even on an empty recordset (e.g. base_partner_merge's generic
        # reference-field sweep writes unconditionally on its search result).
        if not self:
            return
        for queue in self.sudo():
            service = queue.env["voip.pbx.service"]
            if queue.music_on_hold_id and not queue.music_on_hold_id.pbx_moh_name:
                queue.music_on_hold_id._sync_pbx()
            agent_extensions = queue._get_resolved_agent_extensions()
            agent_users = queue.env["res.users"].browse([
                extension.destination_ref.id
                for extension in agent_extensions
            ])
            wazo_agent_ids = []
            agent_vals_by_user_id = {}
            for sequence, extension in enumerate(agent_extensions, start=1):
                agent_user = extension.destination_ref
                agent_names = agent_user._get_pbx_agent_names()
                agent = service._sync_agent(
                    agent_id=agent_user.voip_pbx_agent_id,
                    agent_number=extension.number,
                    firstname=agent_names["firstname"],
                    lastname=agent_names["lastname"],
                )
                agent_user.with_context(voip_skip_pbx_sync=True).voip_pbx_agent_id = agent["agent_id"]
                agent_vals_by_user_id[agent_user.id] = {
                    "sequence": sequence,
                    "pbx_agent_id": agent["agent_id"],
                    "agent_number": extension.number,
                }
                wazo_agent_ids.append(agent["agent_id"])
            queue._sync_resolved_agent_records(agent_users, agent_vals_by_user_id)
            result = service._sync_queue(
                queue_id=queue.pbx_queue_id,
                odoo_queue_id=queue.id,
                queue_label=queue.name,
                strategy=queue.strategy,
                agent_timeout=queue.agent_timeout,
                queue_timeout=queue.queue_timeout,
                retry_delay=queue.retry_on_timeout,
                max_waiting_calls=queue.max_waiting_calls,
                agent_ids=wazo_agent_ids,
                music_on_hold=queue.music_on_hold_id.pbx_moh_name or None,
            )
            queue.with_context(voip_skip_pbx_sync=True).pbx_queue_id = result["queue_id"]
            queue._sync_pbx_routing()

    def _sync_pbx_routing(self):
        """Synchronize the global Wazo fallbacks of an existing Queue."""
        for queue in self.sudo().filtered("pbx_queue_id"):
            service = queue.env["voip.pbx.service"]
            if queue.callflow_id:
                destinations = queue.callflow_id._get_record_output_pbx_destinations(
                    queue, ("no_answer", "busy")
                )
            else:
                destinations = {
                    "no_answer": service._get_pbx_destination(
                        queue.no_answer_destination_ref
                    ),
                    "busy": service._get_pbx_destination(
                        queue.busy_destination_ref
                    ),
                }
            service._update_queue_routing(
                queue_id=queue.pbx_queue_id,
                no_answer_destination=destinations["no_answer"],
                busy_destination=destinations["busy"],
            )

    def _sync_resolved_agent_records(self, agent_users, agent_vals_by_user_id):
        self.ensure_one()
        existing_agents = {agent.user_id.id: agent for agent in self.agent_ids}
        agent_user_ids = set(agent_users.ids)
        stale_agents = self.agent_ids.filtered(lambda agent: agent.user_id.id not in agent_user_ids)
        if stale_agents:
            stale_agents.unlink()
        for agent_user in agent_users:
            vals = agent_vals_by_user_id[agent_user.id]
            agent = existing_agents.get(agent_user.id)
            if agent:
                agent.write(vals)
            else:
                self.env["voip.queue.agent"].create({
                    **vals,
                    "queue_id": self.id,
                    "user_id": agent_user.id,
                })
