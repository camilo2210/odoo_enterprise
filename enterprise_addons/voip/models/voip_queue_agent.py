from odoo import api, fields, models
from odoo.exceptions import AccessError


ASTERISK_QUEUE_MEMBER_IN_CALL_STATUSES = ("2", "3", "6", "7", "8")
QUEUE_AGENT_STATUS_SORT_ORDER = {
    "in_call": 0,
    "available": 1,
    "paused": 2,
    "unavailable": 3,
    "logged_out": 4,
    "unknown": 5,
}


class VoipQueueAgent(models.Model):
    _name = "voip.queue.agent"
    _description = "VoIP Queue Agent"
    _order = "sequence, id"

    queue_id = fields.Many2one(
        "voip.queue",
        required=True,
        index=True,
        ondelete="cascade",
    )
    user_id = fields.Many2one(
        "res.users",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    pbx_agent_id = fields.Integer(
        string="PBX Agent ID",
        copy=False,
        groups="base.group_system",
    )
    agent_number = fields.Char(
        string="Agent Number",
        copy=False,
        groups="base.group_system",
    )
    is_logged = fields.Boolean(
        string="Logged In Queue",
        readonly=True,
    )
    is_paused = fields.Boolean(
        string="Paused",
        readonly=True,
    )
    pause_reason = fields.Char(
        string="Pause Reason",
        readonly=True,
    )
    status = fields.Selection(
        [
            ("unknown", "Unknown"),
            ("logged_out", "Disconnected"),
            ("available", "Available"),
            ("paused", "On Pause"),
            ("in_call", "In Call"),
            ("unavailable", "No Device Detected"),
        ],
        default="unknown",
        readonly=True,
        required=True,
    )
    status_sort_order = fields.Integer(
        compute="_compute_status_sort_order",
        store=True,
    )
    status_last_sync = fields.Datetime(
        string="Status Last Sync",
        readonly=True,
    )

    @api.depends("status")
    def _compute_status_sort_order(self):
        for agent in self:
            agent.status_sort_order = QUEUE_AGENT_STATUS_SORT_ORDER.get(agent.status, 5)

    @api.model
    def get_current_user_queue_memberships(self):
        agents = self.sudo().search([("user_id", "=", self.env.uid)])
        return [
            {
                "id": agent.id,
                "is_logged": agent.is_logged,
                "queue_id": agent.queue_id.id,
                "queue_name": agent.queue_id.name,
            }
            for agent in agents
        ]

    @api.model
    def set_current_user_queue_membership(self, agent_id, is_logged):
        agent = self.sudo().browse(agent_id).exists()
        if not agent or agent.user_id != self.env.user:
            raise AccessError(self.env._("You can only join or leave queues assigned to you."))
        if is_logged:
            agent.action_login_to_queue()
        else:
            agent.action_logoff_from_queue()
        return agent.is_logged

    def action_login_to_queue(self):
        self.ensure_one()
        self.env["voip.pbx.service"]._login_agent_to_queue(
            agent_id=self.pbx_agent_id,
            queue_id=self.queue_id.pbx_queue_id,
        )
        self.queue_id._refresh_agent_statuses()

    def action_logoff_from_queue(self):
        self.ensure_one()
        self.env["voip.pbx.service"]._logoff_agent_from_queue(
            agent_id=self.pbx_agent_id,
            queue_id=self.queue_id.pbx_queue_id,
        )
        self.queue_id._refresh_agent_statuses()

    def _refresh_statuses_from_wazo(self, wazo_agents_by_id, queue_members_by_queue_id=None):
        queue_members_by_queue_id = queue_members_by_queue_id or {}
        now = fields.Datetime.now()
        for agent in self:
            wazo_agent = wazo_agents_by_id.get(agent.pbx_agent_id)
            queue_member = agent._get_queue_member(queue_members_by_queue_id)
            if not wazo_agent:
                if queue_member:
                    agent._write_status_from_queue_member(queue_member, now)
                    continue
                agent.write({
                    "is_logged": False,
                    "is_paused": False,
                    "pause_reason": False,
                    "status": "unknown",
                    "status_last_sync": now,
                })
                continue
            if queue_member:
                agent._write_status_from_queue_member(queue_member, now)
                continue
            wazo_queue = next((
                queue
                for queue in wazo_agent.get("queues") or []
                if queue.get("id") == agent.queue_id.pbx_queue_id
            ), {})
            is_logged = bool(wazo_queue.get("logged"))
            is_paused = bool(wazo_queue.get("paused"))
            agent.write({
                "is_logged": is_logged,
                "is_paused": is_paused,
                "pause_reason": wazo_queue.get("paused_reason") or False,
                "status": agent._get_status_from_wazo_agent(wazo_agent, is_logged, is_paused),
                "status_last_sync": now,
            })

    def _get_queue_member(self, queue_members_by_queue_id):
        self.ensure_one()
        members = queue_members_by_queue_id.get(self.queue_id.id) or []
        agent_name = f"Agent/{self.agent_number}" if self.agent_number else False
        for member in members:
            if agent_name and member.get("Name") == agent_name:
                return member
            state_interface = member.get("StateInterface") or ""
            if self._get_user_id_from_queue_member_interface(state_interface) == self.user_id.id:
                return member
        return False

    @staticmethod
    def _get_user_id_from_queue_member_interface(state_interface):
        if not state_interface.startswith("PJSIP/odoo-") or "_" not in state_interface:
            return False
        user_id = state_interface.rsplit("_", 1)[0].rsplit("-", 1)[-1]
        return int(user_id) if user_id.isdecimal() else False

    def _write_status_from_queue_member(self, queue_member, now):
        self.ensure_one()
        is_paused = bool(int(queue_member.get("Paused") or 0))
        self.write({
            "is_logged": True,
            "is_paused": is_paused,
            "pause_reason": queue_member.get("PausedReason") or False,
            "status": self._get_status_from_queue_member(queue_member),
            "status_last_sync": now,
        })

    @staticmethod
    def _get_status_from_queue_member(queue_member):
        if bool(int(queue_member.get("Paused") or 0)):
            return "paused"
        if queue_member.get("InCall") == "1" or queue_member.get("Status") in ASTERISK_QUEUE_MEMBER_IN_CALL_STATUSES:
            return "in_call"
        if queue_member.get("Status") == "1":
            return "available"
        if queue_member.get("Status") == "5":
            return "unavailable"
        return "unknown"

    @staticmethod
    def _get_status_from_wazo_agent(wazo_agent, is_logged, is_paused):
        if not is_logged:
            return "logged_out"
        if is_paused:
            return "paused"
        raw_status = wazo_agent.get("status") or wazo_agent.get("state")
        if raw_status in ("in_call", "busy"):
            return "in_call"
        return "available"
