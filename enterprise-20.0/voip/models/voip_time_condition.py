from odoo import _, api, fields, models
from odoo.addons.base.models.res_partner import _tz_get
from odoo.exceptions import ValidationError
from odoo.tools import format_time
from odoo.tools.date_utils import float_to_time

from .pbx_service import PBX_DESTINATION_MODELS


PBX_TIME_CONDITION_SYNC_FIELDS = {
    "closed_destination_ref",
    "name",
    "open_destination_ref",
    "period_ids",
    "timezone",
}


class VoipTimeCondition(models.Model):
    _name = "voip.time.condition"
    _inherit = "voip.call.flow.member.mixin"
    _description = "VoIP Time Condition"

    _call_flow_destination_fields = frozenset({
        "open_destination_ref",
        "closed_destination_ref",
    })

    name = fields.Char(default="Time Condition", required=True)
    timezone = fields.Selection(
        selection=_tz_get,
        default=lambda self: self.env.company.tz or "UTC",
        required=True,
    )
    period_ids = fields.One2many(
        "voip.time.condition.period",
        "time_condition_id",
        string="Periods",
        copy=True,
    )
    has_open_period = fields.Boolean(compute="_compute_has_open_period")
    open_destination_ref = fields.Reference(
        selection=PBX_DESTINATION_MODELS,
        string="Open Destination",
        copy=False,
    )
    closed_destination_ref = fields.Reference(
        selection=PBX_DESTINATION_MODELS,
        string="Closed Destination",
        copy=False,
    )
    callflow_id = fields.Many2one(
        "voip.call.flow",
        string="Call Flow",
        copy=False,
        index=True,
        ondelete="set null",
        readonly=True,
    )
    call_group_id = fields.Many2one(
        "voip.call.group",
        copy=False,
        ondelete="set null",
        readonly=True,
    )
    queue_id = fields.Many2one(
        "voip.queue",
        copy=False,
        ondelete="set null",
        readonly=True,
    )
    pbx_schedule_id = fields.Integer(
        string="PBX Schedule ID",
        copy=False,
        groups="base.group_system",
    )

    @api.depends("period_ids.mode")
    def _compute_has_open_period(self):
        for condition in self:
            condition.has_open_period = any(
                period.mode == "open" for period in condition.period_ids
            )

    @api.model_create_multi
    def create(self, vals_list):
        conditions = super(
            VoipTimeCondition,
            self.with_context(voip_skip_pbx_sync=True),
        ).create(vals_list)
        for condition, vals in zip(conditions, vals_list):
            if "name" not in vals:
                condition.name = f"Time Condition {condition.id}"
        if not self.env.context.get("voip_skip_pbx_sync"):
            conditions.with_context(voip_skip_pbx_sync=False)._sync_pbx()
        return conditions.with_context(self.env.context)

    def write(self, vals):
        result = super(
            VoipTimeCondition,
            self.with_context(voip_skip_pbx_sync=True),
        ).write(vals)
        if (
            PBX_TIME_CONDITION_SYNC_FIELDS & vals.keys()
            and not self.env.context.get("voip_skip_pbx_sync")
            and not self.env.context.get("voip_call_flow_sync")
        ):
            self._sync_pbx()
        return result

    def copy_data(self, default=None):
        defaults = dict(default or {})
        defaults.setdefault("open_destination_ref", False)
        defaults.setdefault("closed_destination_ref", False)
        defaults.setdefault("callflow_id", False)
        defaults.setdefault("call_group_id", False)
        defaults.setdefault("queue_id", False)
        defaults.setdefault("pbx_schedule_id", False)
        return super().copy_data(defaults)

    @api.ondelete(at_uninstall=False)
    def _unlink_pbx_resources(self):
        if self.env.context.get("voip_skip_pbx_sync"):
            return
        deletion_by_id = {
            condition.id: {
                "callflow_id": condition.callflow_id.id,
                "pbx_schedule_id": condition.pbx_schedule_id,
            }
            for condition in self.sudo().filtered("pbx_schedule_id")
        }
        if not deletion_by_id:
            return

        def _delete_schedule(env, condition_id):
            deletion = deletion_by_id[condition_id]
            call_flow = env["voip.call.flow"].browse(deletion["callflow_id"]).exists()
            if call_flow:
                call_flow._get_pbx_reference_owners()["voip.did.number"]._sync_pbx_incall()
            env["voip.pbx.service"]._delete_schedule(
                schedule_id=deletion["pbx_schedule_id"]
            )

        self.env["voip.pbx.service"]._call_after_commit_for_deleted(
            "voip.time.condition",
            list(deletion_by_id),
            _delete_schedule,
        )

    def _sync_pbx(self, excluded_period_ids=()):
        if self.env.context.get("voip_skip_pbx_sync"):
            return
        for condition in self.sudo().filtered("callflow_id"):
            previous_schedule_id = condition.pbx_schedule_id
            result = condition.env["voip.pbx.service"]._sync_schedule(
                **condition._get_pbx_sync_values(excluded_period_ids=excluded_period_ids)
            )
            condition.with_context(voip_skip_pbx_sync=True).pbx_schedule_id = result[
                "schedule_id"
            ]
            condition._sync_owner_schedule(condition.pbx_schedule_id or None)
            if condition.pbx_schedule_id != previous_schedule_id:
                condition.callflow_id._get_pbx_reference_owners()[
                    "voip.did.number"
                ]._sync_pbx_incall()

    def _release_from_call_flow(self):
        """Detach reusable conditions and delete their now-unreferenced PBX schedules."""
        conditions = self.sudo().filtered("callflow_id")
        schedules = {
            condition.id: condition.pbx_schedule_id
            for condition in conditions.filtered("pbx_schedule_id")
        }
        conditions._sync_owner_schedule(None)
        conditions.with_context(
            voip_call_flow_sync=True,
            voip_skip_pbx_sync=True,
        ).write({
            "callflow_id": False,
            "open_destination_ref": False,
            "closed_destination_ref": False,
            "call_group_id": False,
            "queue_id": False,
            "pbx_schedule_id": False,
        })
        if schedules:
            service = self.env["voip.pbx.service"]

            def _delete_schedules(env):
                for condition_id, schedule_id in schedules.items():
                    condition = env["voip.time.condition"].browse(condition_id).exists()
                    if condition and condition.pbx_schedule_id == schedule_id:
                        continue
                    env["voip.pbx.service"]._delete_schedule(schedule_id=schedule_id)

            service._call_after_commit(_delete_schedules)

    def _sync_owner_schedule(self, schedule_id):
        service = self.env["voip.pbx.service"]
        for condition in self.sudo():
            if condition.call_group_id.pbx_group_uuid:
                service._sync_group_schedule(
                    group_uuid=condition.call_group_id.pbx_group_uuid,
                    schedule_id=schedule_id,
                )
            if condition.queue_id.pbx_queue_id:
                service._sync_queue_schedule(
                    queue_id=condition.queue_id.pbx_queue_id,
                    schedule_id=schedule_id,
                )

    def _get_pbx_sync_values(self, excluded_period_ids=()):
        self.ensure_one()
        periods = self.period_ids.filtered(
            lambda period: period.id not in excluded_period_ids
        )
        destinations = self.callflow_id._get_time_condition_output_pbx_destinations(
            self,
        )
        return {
            "schedule_id": self.pbx_schedule_id or None,
            "schedule_name": f"Odoo Time Condition {self.id}: {self.name}",
            "closed_destination": destinations["closed"],
            "open_periods": [
                period._get_pbx_values()
                for period in periods.filtered(lambda period: period.mode == "open")
            ],
            "exceptional_periods": [
                {
                    **period._get_pbx_values(),
                    "destination": destinations["closed"],
                }
                for period in periods.filtered(lambda period: period.mode == "closed")
            ],
            "timezone": self.timezone,
        }


class VoipTimeConditionPeriod(models.Model):
    _name = "voip.time.condition.period"
    _description = "VoIP Time Condition Period"
    _order = "id"

    mode = fields.Selection(
        [("open", "Open"), ("closed", "Closed")],
        default="open",
        required=True,
    )
    time_condition_id = fields.Many2one(
        "voip.time.condition",
        required=True,
        index=True,
        ondelete="cascade",
    )
    all_day = fields.Boolean(default=True)
    hours_start = fields.Float(default=9.0)
    hours_end = fields.Float(default=18.0)
    hours_display = fields.Char(string="Hours", compute="_compute_hours_display")
    week_days = fields.Char(default="1-7", required=True)
    month_days = fields.Char(default="1-31", required=True)
    months = fields.Char(default="1-12", required=True)

    @api.depends("all_day", "hours_start", "hours_end")
    @api.depends_context("lang")
    def _compute_hours_display(self):
        for period in self:
            if period.all_day:
                period.hours_display = period.env._("All day")
            elif not 0 <= period.hours_start <= 24 or not 0 <= period.hours_end <= 24:
                period.hours_display = period.env._("Invalid hours")
            else:
                period.hours_display = period.env._(
                    "%(start)s → %(end)s",
                    start=format_time(
                        period.env, float_to_time(period.hours_start), time_format="short"
                    ),
                    end=format_time(
                        period.env, float_to_time(period.hours_end), time_format="short"
                    ),
                )

    @api.constrains("all_day", "hours_start", "hours_end")
    def _check_hours(self):
        for period in self:
            if period.all_day:
                continue
            if not 0 <= period.hours_start <= 24 or not 0 <= period.hours_end <= 24:
                raise ValidationError(_("The hours must be between 00:00 and 24:00."))
            if period._format_hour(period.hours_start) >= period._format_hour(period.hours_end):
                raise ValidationError(
                    _("The end time must be strictly after the start time.")
                )

    @api.constrains("week_days", "month_days", "months")
    def _check_period_values(self):
        limits = {
            "week_days": (1, 7),
            "month_days": (1, 31),
            "months": (1, 12),
        }
        for period in self:
            for field_name, (minimum, maximum) in limits.items():
                try:
                    period._parse_integer_ranges(
                        period[field_name], minimum, maximum
                    )
                except (TypeError, ValueError):
                    raise ValidationError(
                        _(
                            "%(field)s must contain comma-separated integers or ranges between %(minimum)s and %(maximum)s.",
                            field=period._fields[field_name].string,
                            minimum=minimum,
                            maximum=maximum,
                        )
                    ) from None

    @staticmethod
    def _parse_integer_ranges(value, minimum, maximum):
        values = set()
        for item in value.split(","):
            bounds = item.strip().split("-", 1)
            start = int(bounds[0])
            end = int(bounds[-1])
            if not minimum <= start <= end <= maximum:
                raise ValueError
            values.update(range(start, end + 1))
        if not values:
            raise ValueError
        return sorted(values)

    def _get_pbx_values(self):
        self.ensure_one()
        return {
            "hours_start": "00:00" if self.all_day else self._format_hour(self.hours_start),
            "hours_end": "23:59" if self.all_day else self._format_hour(self.hours_end),
            "week_days": self._parse_integer_ranges(self.week_days, 1, 7),
            "month_days": self._parse_integer_ranges(self.month_days, 1, 31),
            "months": self._parse_integer_ranges(self.months, 1, 12),
        }

    @staticmethod
    def _format_hour(value):
        return float_to_time(value).strftime("%H:%M")

    @api.model_create_multi
    def create(self, vals_list):
        periods = super(
            VoipTimeConditionPeriod,
            self.with_context(voip_skip_pbx_sync=True),
        ).create(vals_list)
        if not self.env.context.get("voip_skip_pbx_sync"):
            periods.time_condition_id.with_context(
                voip_skip_pbx_sync=False
            )._sync_pbx()
        return periods.with_context(self.env.context)

    def write(self, vals):
        conditions = self.time_condition_id
        result = super(
            VoipTimeConditionPeriod,
            self.with_context(voip_skip_pbx_sync=True),
        ).write(vals)
        if not self.env.context.get("voip_skip_pbx_sync"):
            (conditions | self.time_condition_id).with_context(
                voip_skip_pbx_sync=False
            )._sync_pbx()
        return result

    @api.ondelete(at_uninstall=False)
    def _sync_pbx_before_unlink(self):
        if self.env.context.get("voip_skip_pbx_sync"):
            return
        for condition, periods in self.grouped("time_condition_id").items():
            condition._sync_pbx(excluded_period_ids=periods.ids)
