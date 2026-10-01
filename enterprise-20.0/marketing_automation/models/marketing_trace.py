# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from __future__ import annotations
import typing

from collections import defaultdict
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models, tools
from odoo.fields import Domain

if typing.TYPE_CHECKING:
    from typing import Literal


class MarketingTrace(models.Model):
    _name = 'marketing.trace'
    _description = 'Marketing Trace'
    _order = 'schedule_date DESC, id ASC'
    _rec_name = 'participant_id'

    # Participant
    participant_id = fields.Many2one(
        'marketing.participant', string='Participant',
        index=True, ondelete='cascade', required=True)
    res_id = fields.Integer(string='Document ID', related='participant_id.res_id', index=True, store=True, readonly=False)
    is_test = fields.Boolean(string='Test Trace', related='participant_id.is_test', index=True, store=True, readonly=True)
    # Activity
    activity_id = fields.Many2one(
        'marketing.activity', string='Activity',
        index=True, ondelete='cascade', required=True)
    activity_type = fields.Selection(related='activity_id.activity_type', readonly=True)
    trigger_type = fields.Selection(related='activity_id.trigger_type', readonly=True)
    campaign_id = fields.Many2one(related="activity_id.campaign_id")
    trigger_category = fields.Selection(related='activity_id.trigger_category')
    # Trace hierarchy (based on activity triggers)
    triggering_trace_id = fields.Many2one('marketing.trace', string='Triggering Trace', index=True)
    triggered_trace_ids = fields.One2many('marketing.trace', 'triggering_trace_id', string='Traces that will be triggered when processed')
    triggered_activity_ids = fields.One2many("marketing.activity", related="activity_id.triggered_activity_ids")
    processed_triggers = fields.Char()
    # Status
    state = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('processed', 'Processed'),
        ('rejected', 'Rejected'),
        ('canceled', 'Cancelled'),
        ('error', 'Error'),
        ('waiting', 'Waiting'),  # A waiting trace is a trace linked to an activity with a trigger_type `wait_value` that isn't processed yet.
        ], default='scheduled', index=True, required=True)
    schedule_date = fields.Datetime()
    state_msg = fields.Char(string='Error message')
    # hierarchy
    parent_id = fields.Many2one('marketing.trace', string='Parent', index=True, ondelete='cascade')
    child_ids = fields.One2many('marketing.trace', 'parent_id', string='Direct child traces')
    # mailing traces
    mailing_trace_ids = fields.One2many('mailing.trace', 'marketing_trace_id', string='Mass mailing statistics')
    mailing_trace_status = fields.Selection(related='mailing_trace_ids.trace_status', readonly=True)
    links_click_datetime = fields.Datetime(compute='_compute_links_click_datetime')

    def _get_activity_trigger_type_ordered_list(self):
        return ['mail_open', 'mail_click', 'mail_reply']

    @api.depends('mailing_trace_ids')
    def _compute_links_click_datetime(self):
        # necessary, because sometimes mailing_trace_ids aren't available
        # due to failed messages, which prevents `links_click_datetime` to get assigned
        self.links_click_datetime = False
        mailing_trace = self.filtered(lambda x: x.mailing_trace_ids)
        for trace in mailing_trace:
            trace.links_click_datetime = trace.mailing_trace_ids[0].links_click_datetime

    # ------------------------------------------------------------
    # State management
    # ------------------------------------------------------------

    def action_set_canceled(self, message: str | None = None, check_participant_completed: bool = False):
        if not self:
            return True
        values = {
            'state': 'canceled',
            'schedule_date': self.env.cr.now(),
        }
        if message:
            values['state_msg'] = message
        self.write(values)
        if check_participant_completed:
            self.participant_id.check_completed()
        return True

    def action_set_canceled_manual(self):
        return self.action_set_canceled(
            message=self.env._('Manually canceled by %(user_name)s', user_name=self.env.user.name),
            check_participant_completed=True,
        )

    def action_set_error(self, message: str | None = None, check_participant_completed: bool = False):
        values = {
            'state': 'error',
            'schedule_date': self.env.cr.now(),
        }
        if message:
            values['state_msg'] = message
        self.write(values)
        if check_participant_completed:
            self.participant_id.check_completed()
        return True

    def action_set_processed(self, check_participant_completed: bool = False):
        self.write({
            'state': 'processed',
            'schedule_date': self.env.cr.now(),
            'state_msg': False,
        })
        if check_participant_completed:
            self.participant_id.check_completed()
        return True

    def action_set_rejected(self, message: str | None = None, check_participant_completed: bool = False):
        # TDE check: scheduled_date ?
        values = {'state': 'rejected'}
        if message:
            values['state_msg'] = message
        self.write(values)
        if check_participant_completed:
            self.participant_id.check_completed()
        return True

    def action_set_scheduled(self, schedule_date=None):
        values = {
            'state': 'scheduled',
            'state_msg': False,
        }
        if schedule_date:
            values['schedule_date'] = schedule_date
        self.write(values)
        return True

    def action_set_waiting(self):
        self.write({'state': 'waiting'})
        return True

    def _cancel_with_open_descendants(self, message: str | None):
        start_traces = (self.triggered_trace_ids | self.child_ids).filtered_domain(Domain('state', 'in', ['scheduled', 'waiting', 'processed']))
        canceled = self.browse()
        candidates = start_traces
        while candidates:
            to_cancel = candidates.filtered_domain(Domain('state', 'in', ['scheduled', 'waiting']))
            to_cancel.action_set_canceled(message=message, check_participant_completed=False)
            canceled |= to_cancel
            candidates = candidates.child_ids.filtered_domain(Domain('state', 'in', ['scheduled', 'waiting', 'processed']))
        return canceled

    def _schedule_based_on_activity(self):
        for activity, traces in self.grouped('activity_id').items():
            offset = relativedelta(**{activity.interval_type: activity.interval_number})
            traces.action_set_scheduled(
                schedule_date=activity._plan_schedule_date(self.env.cr.now(), offset)
            )
        return True

    # ------------------------------------------------------------
    # Trace execution
    # ------------------------------------------------------------

    def action_execute(self):
        self.activity_id.execute_on_traces(self)

    def process_event(self, trigger_type: str) -> Literal[True]:
        """ Process event coming from customers.
        The child traces are now either the direct children of the trace or the triggered activities' traces
        as a trigger can be set on another activity than a direct child.
        It updates child traces as such:

         * child trace matching action is scheduled or executed depending on
           time interval configuration;
         * opposite actions are canceled
           e.g. mail_not_open is canceled if mail_open is triggered
           e.g. mail_bounce cancels all child actions not being mail_bounced;

        :param str trigger_type: one of ``trigger_type`` of marketing activity
        """
        # DANE: try to make this function to work on batches later
        self.ensure_one()
        if self.participant_id.campaign_id.state not in ['draft', 'running']:
            return

        now = self.env.cr.now()

        possible_opened_traces = (self.child_ids | self.triggered_trace_ids).filtered_domain([('state', '=', 'scheduled')])
        cron_trigger_dates = set()
        if self.activity_id._is_a_reply_trigger_type(trigger_type):
            # collect (potentially early ending) activities should be triggered
            collect_activities = self.env['marketing.activity'].search([
                ('trigger_type', '=', 'collect_reply'),
                ('campaign_id', '=', self.campaign_id.id),
            ])
            if collect_activities:
                existing = self.env['marketing.trace'].search([
                    ('res_id', '=', self.res_id),
                    ('activity_id', 'in', collect_activities.ids),
                ])
                new_collect_activities = collect_activities.filtered(lambda a: a not in existing.activity_id)
                trace_vals_list = []
                for activity in new_collect_activities:
                    activity_offset = relativedelta(**{activity.interval_type: activity.interval_number})
                    trace_vals_list.append({
                        'activity_id': activity.id,
                        'participant_id': self.participant_id.id,
                        'res_id': self.res_id,
                        'schedule_date': activity._plan_schedule_date(self.env.cr.now(), activity_offset),
                    })
                collect_reply_created_traces = self.env['marketing.trace'].create(trace_vals_list) if trace_vals_list else self.browse()
                if self.campaign_id.collect_reply_early_end:
                    self._cancel_with_open_descendants(message=_('Early ending: mail replied'))
                    possible_opened_traces = (collect_activities - new_collect_activities).mapped('trace_ids') | collect_reply_created_traces

        processed_triggers = self.activity_id._get_implied_processed_events()[trigger_type]

        already_processed_triggers = set((self.processed_triggers or '').split(','))
        if processed_triggers - already_processed_triggers:
            self.write({"processed_triggers": ','.join(map(str, processed_triggers))})

        for next_trace in possible_opened_traces.filtered_domain([
            '|', ('trigger_type', '=', 'collect_reply'),
            '&', ('state', '=', 'scheduled'), ('trigger_type', '=', trigger_type)
        ]):
            if next_trace.activity_id.interval_number == 0:
                next_trace.write({
                    'schedule_date': now,
                })
                next_trace.activity_id.execute_on_traces(next_trace)
            else:
                trace_offset = relativedelta(**{
                    next_trace.activity_id.interval_type: next_trace.activity_id.interval_number
                })
                schedule_date = next_trace.activity_id._plan_schedule_date(now, trace_offset)

                next_trace.write({
                    'schedule_date': schedule_date,
                })
                cron_trigger_dates.add(schedule_date)

        if cron_trigger_dates:
            # based on updated activities, we schedule CRON triggers that match the scheduled_dates
            # we use a set to only trigger the CRON once per timeslot event if there are multiple
            # marketing.participants
            cron = self.env.ref('marketing_automation.ir_cron_campaign_execute_activities')
            cron._trigger(cron_trigger_dates)

        # cancel opposite traces e.g. if mail is opened, cancel not open trace
        if trigger_type not in self.env['marketing.activity']._get_reschedule_trigger_types():
            opposite_triggers, msg = self.env['marketing.activity']._get_opposite_trigger_types()[trigger_type]
            possible_opened_traces.filtered(
                lambda trace: trace.activity_id.trigger_type in opposite_triggers
            ).action_set_canceled(message=msg)

        return possible_opened_traces

    def _update_schedule_date(self):
        """ Update scheduled date of traces, based on activity interval fields
        update. Rationale

          * begin activities: offset is based on participant creation e.g.
            2 days after entering the campaign;
          * reschedule triggers: based on parent trace scheduled date e.g.
            mail_not_open triggered 2 days after sending the mailing aka the
            parent activity;
          * other triggers: reschedule only if already scheduled, based on a
            master record e.g. 2 days after opening an email is based on the
            mailing trace;
        """
        reschedule_types = self.env["marketing.activity"]._get_reschedule_trigger_types()
        batch_size = self.env['ir.config_parameter'].sudo().get_int('marketing.execute.batch.size') or 100
        for traces_batch in tools.split_every(batch_size, self, piece_maker=list):
            traces_per_schedule_date = defaultdict(self.browse)
            for trace in traces_batch:
                base_dt_str = False
                trace_offset = relativedelta(**{trace.activity_id.interval_type: trace.activity_id.interval_number})
                # begin: based on participant creation as it is their first one
                if trace.activity_id.trigger_type == 'begin':
                    base_dt_str = trace.participant_id.create_date
                # reschedule (mail_not_open, ...) -> based on parent
                elif trace.trigger_type in reschedule_types:
                    base_dt_str = trace.parent_id.schedule_date or trace.parent_id.mailing_trace_ids[:1].write_date or trace.participant_id.create_date
                # other (mail_open, ...): update only already scheduled traces, other unscheduled should stay as it
                elif trace.schedule_date and trace.parent_id.mailing_trace_ids:
                    base_dt_str = trace.parent_id.mailing_trace_ids[0].write_date

                if base_dt_str:
                    dt = trace.activity_id._plan_schedule_date(fields.Datetime.from_string(base_dt_str), trace_offset)
                    traces_per_schedule_date[dt] += trace
            for dt, traces in traces_per_schedule_date.items():
                if traces:
                    traces.schedule_date = dt
