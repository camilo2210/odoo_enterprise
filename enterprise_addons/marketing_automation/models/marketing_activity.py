# Part of Odoo. See LICENSE file for full copyright and licensing details.
from __future__ import annotations

import json
import logging
import textwrap
import typing

from ast import literal_eval
from collections import defaultdict
from datetime import timedelta, date
from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import api, fields, models, modules, _
from odoo.fields import Domain
from odoo.exceptions import ValidationError, AccessError
from odoo.tools import SQL, split_every
from odoo.tools.misc import clean_context, OrderedSet

_logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from odoo.api import DomainType
    from odoo.addons.marketing_automation.models.marketing_trace import MarketingTrace


class MarketingActivity(models.Model):
    _name = 'marketing.activity'
    _description = 'Marketing Activity'
    _order = 'interval_standardized, id ASC'

    name = fields.Char('Name', compute="_compute_name", store=True, readonly=False, copy=True)
    description = fields.Html('Description', compute="_compute_description")
    campaign_id = fields.Many2one(
        'marketing.campaign', string='Campaign',
        index=True, ondelete='cascade', required=True)
    utm_campaign_id = fields.Many2one(
        'utm.campaign', string='UTM Campaign',
        readonly=True, related='campaign_id.utm_campaign_id')  # propagate to mailings
    # Type: action done by the activity
    # ------------------------------------------------------------
    activity_type = fields.Selection([
        ('mail', 'Email'),
        ('action', 'Server Action'),
        ('split', 'Split'),
        ('structure', 'Structure'),
        ('log_note', 'Log Note'),
        ('subscribe_to_list', 'Mailing List Subscription')], string='Activity Type', required=True)
    # -- type: email
    mass_mailing_id = fields.Many2one(
        'mailing.mailing', string='Marketing Template', compute='_compute_mass_mailing_id',
        readonly=False, store=True, index='btree_not_null')
    campaign_mass_mailing_count = fields.Integer(
        'Campaign Mailing Count', related='campaign_id.mass_mailing_count', store=False,
    )
    # Technical field doing the mapping of activity type and mailing type
    mass_mailing_id_mailing_type = fields.Selection([
        ('mail', 'Email')], string='Mailing Type', compute='_compute_mass_mailing_id_mailing_type',
        readonly=True, store=True)
    # -- type: action
    server_action_id = fields.Many2one(
        'ir.actions.server', string='Server Action', compute='_compute_server_action_id',
        readonly=False, store=True, index=True, ondelete='restrict')
    server_action_state = fields.Selection(related='server_action_id.state', readonly=True)
    # -- type: split
    split_domain = fields.Char(
        string='Applied Split Filter',
        help="Used to determine a Split's domain to apply when the activity is set as a Split.")
    is_split_no = fields.Boolean("Is it the False branch of the split?", default=False)
    # -- type: log_note
    log_note_body = fields.Text("Note to Log")
    # -- type: subscribe_to_list
    subscribe_to_list_id = fields.Many2one(
        "mailing.list", string="Mailing List",
        compute="_compute_subscribe_to_list", index=True,
        readonly=False, store=True, ondelete="restrict")
    subscribe_to_list_action = fields.Selection(
        [('add', 'Add'), ('remove', 'Remove')], string="Perform",
        compute="_compute_subscribe_to_list", readonly=False, store=True)
    # Time information
    # ------------------------------------------------------------
    # interval
    interval_number = fields.Integer(string='Send after', default=0)
    interval_type = fields.Selection([
        ('hours', 'Hours'),
        ('days', 'Days'),
        ('weeks', 'Weeks'),
        ('months', 'Months')], string='Delay Type',
        default='hours', required=True)
    interval_standardized = fields.Integer('Send after (in hours)', compute='_compute_interval_standardized', store=True, readonly=True)
    # validity
    validity_duration = fields.Boolean('Validity Duration',
        help='Check this to make sure your actions are not executed after a specific amount of time after the scheduled date. (e.g. Time-limited offer, Upcoming event, …)')
    validity_duration_number = fields.Integer(string='Valid during', default=0)
    validity_duration_type = fields.Selection([
        ('hours', 'Hours'),
        ('days', 'Days'),
        ('weeks', 'Weeks'),
        ('months', 'Months')],
        default='hours', required=True)
    # Target / Hierarchy
    # ------------------------------------------------------------
    activity_domain = fields.Char(
        string='Activity Filter',
        help='Domain that applies to this activity and its child activities')
    model_id = fields.Many2one('ir.model', related='campaign_id.model_id', string='Model', readonly=True)
    model_name = fields.Char(related='model_id.model', string='Model Name', readonly=True)
    # Related to parent activity
    parent_id = fields.Many2one(
        'marketing.activity', string='Parent activity', index=True)
    allowed_parent_ids = fields.Many2many(
        'marketing.activity', string='Allowed parents', help='All activities which can be the parent of this one', compute='_compute_allowed_parent_ids')
    child_ids = fields.One2many('marketing.activity', 'parent_id', string='Child Activities')
    # Trigger: condition to fire the activity
    # ------------------------------------------------------------
    trigger_type = fields.Selection([
        ('begin', 'beginning of workflow'),
        ('activity', 'another activity'),
        ('mail_open', 'Mail: opened'),
        ('mail_not_open', 'Mail: not opened'),
        ('mail_reply', 'Mail: replied'),
        ('mail_not_reply', 'Mail: not replied'),
        ('mail_click', 'Mail: clicked'),
        ('mail_not_click', 'Mail: not clicked'),
        ('mail_bounce', 'Mail: bounced'),
        ('collect_reply', 'Collect Any Reply'),
        ('wait_value', 'Wait for a value')], default="begin", required=True)
    trigger_category = fields.Selection([('mail', 'Mail')], compute='_compute_trigger_category')
    trigger_type_category = fields.Selection([('domain', 'Filter'), ('interaction', 'Interaction')], compute="_compute_trigger_type_category", inverse="_inverse_trigger_type_category", store=False)
    # UI fields
    trigger_type_ui = fields.Selection([
        ('open', 'Opened'),
        ('not_open', 'Not opened'),
        ('reply', 'Replied'),
        ('not_reply', 'Not replied'),
        ('click', 'Clicked'),
        ('not_click', 'Not clicked'),
        ('bounce', 'Bounced')], inverse="_inverse_trigger_type_ui", compute="_compute_trigger_type_ui", store=False)
    allowed_trigger_type_ui = fields.Json('Allowed Trigger Types', compute='_compute_allowed_trigger_type_ui')
    trigger_category_ui = fields.Selection([('mail', 'Email')], compute="_compute_trigger_category_ui")
    # Trigerring activity tree
    triggering_activity_id = fields.Many2one("marketing.activity",
        help="Activity to check for the trigger", index="btree_not_null")
    triggering_activity_allowed_ids = fields.Many2many(
        'marketing.activity', string='Allowed Triggers',
        compute='_compute_triggering_activity_allowed_ids', store=False,
    )
    triggered_activity_ids = fields.One2many("marketing.activity", "triggering_activity_id")
    can_be_triggering_activity = fields.Boolean(store=False, search='_search_can_be_triggering_activity')
    # -- trigger: wait_value
    wait_value_domain = fields.Char(string="Applied Wait Value Domain", help="Used to determine the domain to apply when waiting for a value.")
    # -- trigger: collect_reply
    collect_reply_early_end = fields.Boolean("Cancel flows when replied")  # deprecated, remove in 20.1
    # cron / updates
    require_sync = fields.Boolean('Require trace sync', copy=False)
    # For trace
    trace_ids = fields.One2many('marketing.trace', 'activity_id', string='Traces', copy=False)
    processed = fields.Integer(compute='_compute_statistics')
    rejected = fields.Integer(compute='_compute_statistics')
    total_sent = fields.Integer(compute='_compute_statistics')
    total_click = fields.Integer(compute='_compute_statistics')
    total_open = fields.Integer(compute='_compute_statistics')
    total_reply = fields.Integer(compute='_compute_statistics')
    total_bounce = fields.Integer(compute='_compute_statistics')
    statistics_graph_data = fields.Char(compute='_compute_statistics_graph_data')
    # Position of the activity nodes in the plan:
    # Format:
    #   - 'trigger': coordinates of the fake trigger node (e.g: "wait for value", "mail interaction", ...)
    #   - 'delay': coordinates of the fake delay node
    #   - 'activity': coordinates of the activity node
    #   - 'flag': coordinates of the flag of the last node
    #   - 'yes_branch_flag': coordinates of the flag for the "yes" branch of the split nodes
    #   - 'no_branch_flag': coordinates of the flag for the "no" branch of the split nodes
    view_coordinates = fields.Json()

    _check_general_trigger = models.Constraint(
        "CHECK(trigger_type != 'collect_reply' or parent_id IS NULL)",
        "A general triggered activity cannot have a parent activity",
    )
    _check_subscribe_to_list = models.Constraint(
        "CHECK(activity_type != 'subscribe_to_list' or (subscribe_to_list_id is not NULL and subscribe_to_list_action is not NULL))",
        "A subscribe_to_list activity should have a mailing list to (un)sub to it. And its action should also be set.",
    )
    _check_log_note = models.Constraint(
        "CHECK(activity_type != 'log_note' or log_note_body is not NULL)",
        "A log note activity should always have a note to log on the record",
    )

    def _get_allowed_triggering_activity_types(self):
        return ['mail']

    @api.constrains('parent_id')
    def _check_parent_id(self):
        if self._has_cycle():
            raise ValidationError(_("Error! You can't create recursive hierarchy of Activity."))

    @api.constrains('trigger_type', 'parent_id', 'triggering_activity_id')
    def _check_consistency_in_activities(self):
        """Check the consistency in the activity chaining."""
        for activity in self:
            if (activity.trigger_type == 'activity' and not activity.parent_id) or (activity.trigger_type == 'begin' and activity.parent_id) or activity.trigger_category not in [False, activity.triggering_activity_id.activity_type]:
                trigger_string = dict(activity._fields['trigger_type']._description_selection(self.env))[activity.trigger_type]
                raise ValidationError(
                    _('You are trying to set the activity "%(parent_activity)s" as "%(parent_type)s" while its child "%(activity)s" has the trigger type "%(trigger_type)s"\nPlease modify one of those activities before saving.',
                      parent_activity=activity.triggering_activity_id.name, parent_type=activity.triggering_activity_id.activity_type, activity=activity.name, trigger_type=trigger_string))

    @api.constrains('triggering_activity_id')
    def _check_triggering_activity_id(self):
        for activity in self.filtered('triggering_activity_id'):
            if activity.triggering_activity_id.activity_type == 'structure':
                raise ValidationError(_("The triggering activity mustn't be a structure activity."))
            if activity.triggering_activity_id.activity_type not in activity._get_allowed_triggering_activity_types():
                raise ValidationError(_("You are trying to set an incorrect activity as the triggering of another one. Please change the triggering activity."))
            is_cycle = activity.filtered_domain([('id', 'parent_of', activity.triggering_activity_id.id)])
            if is_cycle:
                raise ValidationError(_("No cycle on triggers."))

    @api.constrains('view_coordinates')
    def _check_view_coordinates_keys(self):
        coordinates_keys = {'no_branch_flag', 'yes_branch_flag', 'flag', 'delay', 'trigger', 'activity'}
        for activity in self.filtered('view_coordinates'):
            view_coordinates = activity.view_coordinates
            if set(view_coordinates.keys()) - coordinates_keys:
                raise ValidationError(_("The coordinates for activities shouldn't be messed with."))
            for key in coordinates_keys:
                coordinate_values = view_coordinates.get(key)
                if not coordinate_values:
                    continue
                if coordinate_values is not None and set(coordinate_values.keys()) - {'x', 'y'}:
                    raise ValidationError(_("The coordinates for activities shouldn't be messed with."))
                if not (isinstance(coordinate_values.get('x', 0.0), (float, int)) and isinstance(coordinate_values.get('y', 0.0), (float, int))):
                    raise ValidationError(_("The coordinates for activities shouldn't be messed with."))

    def _set_default_trigger_type(self):
        activity_triggered = self.filtered('parent_id')
        activity_triggered.write({'trigger_type': 'activity'})
        (self - activity_triggered).write({'trigger_type': 'begin'})

    @api.depends("activity_type")
    def _compute_description(self):
        for activity in self:
            if activity.activity_type == 'log_note':
                activity.description = Markup.escape(_(
                    "Log on record: %(log_note_body)s",
                    log_note_body=textwrap.shorten((activity.log_note_body or ''), width=10, placeholder='...')
                ))
            elif activity.activity_type == 'subscribe_to_list':
                if activity.subscribe_to_list_action == 'add':
                    activity.description = _("Add participant to %s", Markup("<span class='o_ma_dynamic_field'>%s</span>") % activity.subscribe_to_list_id.display_name)
                else:
                    activity.description = Markup.escape(_("Remove participant from %(list_name)s", list_name=activity.subscribe_to_list_id.display_name))
            elif activity.activity_type == 'action':
                server_action_id = activity.server_action_id
                if server_action_id.state == 'object_write':
                    activity.description = _("%(action)s %(field_name)s",
                        action=dict(server_action_id._fields['evaluation_type']._description_selection(self.env)).get(server_action_id.evaluation_type),
                        field_name=server_action_id.update_field_id.with_context(hide_model=True).display_name)
                elif server_action_id.state == 'next_activity':
                    activity_name = server_action_id.activity_type_id.display_name
                    if server_action_id.activity_user_type == 'generic':
                        field_path = server_action_id.activity_user_field_name.split('.')
                        model = activity.env[activity.model_name]
                        for field in field_path[:-1]:
                            # we don't use mapped to avoid calling unnecessary computes
                            model = activity.env[model._fields[field].comodel_name]
                        user_description = Markup('<em class="o_ma_dynamic_field">%s</em>') % model._fields[field_path[-1]].string
                    else:
                        user_description = (server_action_id.activity_user_id or server_action_id.activity_role_id).display_name
                    activity.description = _("%(activity_name)s for %(user_description)s", activity_name=activity_name, user_description=user_description)
                else:
                    activity.description = Markup.escape(server_action_id.display_name)
            else:
                activity.description = False

    @api.depends(
        'activity_type', 'mass_mailing_id', 'log_note_body', 'subscribe_to_list_id', 'server_action_id',
    )
    def _compute_name(self):
        for activity in self:
            if activity.activity_type == 'mail':
                mailing_subject = activity.mass_mailing_id.subject
                activity.name = _("Send Email: %(mailing_subject)s", mailing_subject=mailing_subject) \
                    if mailing_subject else _("Send Email")
            elif activity.activity_type == 'log_note':
                log_note_body = textwrap.shorten((activity.log_note_body or ''), width=10, placeholder='...')
                activity.name = _("Log Note: %(log_note_body)s", log_note_body=log_note_body) \
                    if log_note_body else _("Log Note")
            elif activity.activity_type == 'subscribe_to_list':
                mailing_list = activity.subscribe_to_list_id.display_name
                activity.name = _("Mailing List Management: %(mailing_list)s", mailing_list=mailing_list) \
                    if mailing_list else _("Mailing List Management")
            elif activity.activity_type == 'action':
                server_action_name = activity.server_action_id.display_name
                activity.name = _("Server action: %(server_action_name)s", server_action_name=server_action_name) \
                    if server_action_name else _("Server action")
            elif isinstance(activity.id, int):
                activity.name = _("Marketing Activity: %(activity_type)s,%(activity_id)s",
                    activity_type=activity.activity_type,
                    activity_id=activity.id)
            else:
                activity.name = _("Marketing Activity: %(activity_type)s", activity_type=activity.activity_type)

    @api.depends('activity_type')
    def _compute_mass_mailing_id_mailing_type(self):
        for activity in self:
            if activity.activity_type == 'mail':
                activity.mass_mailing_id_mailing_type = 'mail'
            else:
                activity.mass_mailing_id_mailing_type = False

    @api.depends('mass_mailing_id_mailing_type')
    def _compute_mass_mailing_id(self):
        for activity in self:
            if activity.mass_mailing_id_mailing_type != activity.mass_mailing_id.mailing_type:
                activity.mass_mailing_id = False

    @api.depends('interval_type', 'interval_number')
    def _compute_interval_standardized(self):
        factors = {'hours': 1,
                   'days': 24,
                   'weeks': 168,
                   'months': 720}
        for activity in self:
            activity.interval_standardized = (
                (activity.interval_number * factors[activity.interval_type])
                if activity.interval_type else 0
            )

    @api.depends('trigger_type', 'campaign_id.marketing_activity_ids', 'trigger_category')
    def _compute_allowed_parent_ids(self):
        for activity in self:
            if activity.trigger_type == 'activity':
                activity.allowed_parent_ids = activity.campaign_id.marketing_activity_ids.filtered(
                    lambda parent_id: parent_id.ids != activity.ids)
            elif activity.trigger_category:
                activity.allowed_parent_ids = activity.campaign_id.marketing_activity_ids.filtered(
                    lambda parent_id: parent_id.ids != activity.ids and parent_id.activity_type == activity.trigger_category)
            else:
                activity.allowed_parent_ids = False

    @api.depends('activity_type')
    def _compute_server_action_id(self):
        self.filtered(lambda a: a.activity_type != 'action').server_action_id = False

    @api.depends('activity_type')
    def _compute_subscribe_to_list(self):
        for record in self:
            if record.activity_type == 'subscribe_to_list':
                record.subscribe_to_list_action = 'add'
                record.subscribe_to_list_id = False

    @api.depends('trigger_type')
    def _compute_trigger_category(self):
        for activity in self:
            if activity.trigger_type in ['mail_open', 'mail_not_open', 'mail_reply', 'mail_not_reply',
                                         'mail_click', 'mail_not_click', 'mail_bounce']:
                activity.trigger_category = 'mail'
            else:
                activity.trigger_category = False

    @api.depends('triggering_activity_id')
    def _compute_allowed_trigger_type_ui(self):
        split_activities = self.filtered_domain([('activity_type', '=', 'split')])
        split_activities.allowed_trigger_type_ui = ['open', 'reply', 'click', 'bounce']
        (self - split_activities).allowed_trigger_type_ui = [*self._fields['trigger_type_ui']._selection.keys()]

    @api.depends('triggering_activity_id')
    def _compute_trigger_category_ui(self):
        for record in self:
            record.trigger_category_ui = record.triggering_activity_id.activity_type

    @api.depends("trigger_type")
    def _compute_trigger_type_ui(self):
        for activity in self:
            if activity.trigger_category_ui and activity._is_an_interaction_trigger_type(activity.trigger_type):
                activity.trigger_type_ui = activity.trigger_type.removeprefix(f"{activity.trigger_category_ui}_")
            else:
                activity.trigger_type_ui = False

    def _inverse_trigger_type_ui(self):
        for record in self:
            if record.trigger_category_ui and record.trigger_type_ui:
                record.trigger_type = f"{record.trigger_category_ui}_{record.trigger_type_ui}"

    @api.onchange('trigger_type_ui', 'trigger_category_ui')
    def _onchange_trigger_type_ui(self):
        self._inverse_trigger_type_ui()

    @api.depends('trigger_type')
    def _compute_trigger_type_category(self):
        for activity in self:
            if activity.trigger_type == 'wait_value':
                activity.trigger_type_category = 'domain'
            else:
                activity.trigger_type_category = 'interaction'

    def _inverse_trigger_type_category(self):
        for activity in self:
            if activity.trigger_type_category == 'domain':
                activity.trigger_type = 'wait_value'
                activity.triggering_activity_id = False
            elif activity.trigger_type_category == 'interaction':
                if activity.trigger_type == 'wait_value':
                    activity.trigger_type = 'activity' if activity.parent_id else 'begin'
                activity.wait_value_domain = False

    @api.onchange('trigger_type_category')
    def _onchange_trigger_type_category(self):
        self._inverse_trigger_type_category()

    @api.depends('trigger_type_category')
    def _compute_triggering_activity_allowed_ids(self):
        for activity in self:
            if activity.trigger_type_category == 'interaction':
                activity.triggering_activity_allowed_ids = activity.campaign_id.marketing_activity_ids.filtered(
                    lambda a: a.ids != activity.ids and a.trigger_category == activity.trigger_category
                )
            else:
                activity.triggering_activity_allowed_ids = False

    def _search_can_be_triggering_activity(self, operator, value):
        domain = Domain('activity_type', '=', 'mail')
        if (operator == '=' and False in value) or (operator == '!=' and True in value):
            domain = ~domain
        return domain

    @api.depends('activity_type', 'trace_ids')
    def _compute_statistics(self):
        # Fix after ORM-pocalyspe : Update in any case, otherwise, None to some values (crash)
        self.update({
            'total_bounce': 0, 'total_reply': 0, 'total_sent': 0,
            'rejected': 0, 'total_click': 0, 'processed': 0, 'total_open': 0,
        })
        if self.ids:
            activity_data = {activity._origin.id: {} for activity in self}
            for stat in self._get_full_statistics():
                activity_data[stat.pop('activity_id')].update(stat)
            for activity in self:
                activity.update(activity_data[activity._origin.id])

    @api.depends('activity_type', 'trace_ids')
    def _compute_statistics_graph_data(self):
        if not self.ids:
            date_range = [date.today() - timedelta(days=d) for d in range(0, 15)]
            date_range.reverse()
            default_values = [{'x': date_item.strftime('%d %b'), 'y': 0} for date_item in date_range]
            self.statistics_graph_data = json.dumps([
                {'points': default_values, 'label': _('Success'), 'color': '#28A745'},
                {'points': default_values, 'label': _('Rejected'), 'color': '#D23f3A'}])
        else:
            activity_data = {activity._origin.id: {} for activity in self}
            for act_id, graph_data in self._get_graph_statistics().items():
                activity_data[act_id]['statistics_graph_data'] = json.dumps(graph_data)
            for activity in self:
                activity.update(activity_data[activity._origin.id])

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if 'trigger_type_ui' in values:
                values.pop('trigger_type_ui')
            if 'trigger_type_category' in values:
                values.pop('trigger_type_category')
            campaign_id = values.get('campaign_id')
            if not campaign_id:
                campaign_id = self.default_get(['campaign_id']).get('campaign_id')
            if campaign_id:
                values['require_sync'] = self.env['marketing.campaign'].browse(campaign_id).state == 'running'
            if self._is_an_interaction_trigger_type(values.get('trigger_type')) and not values.get('triggering_activity_id'):
                values['triggering_activity_id'] = values.get('parent_id')
        return super().create(vals_list)

    def copy_data(self, default=None):
        """ When copying the activities, we should also copy their mailings. """
        default = dict(default or {})
        if self.mass_mailing_id:
            default['mass_mailing_id'] = self.mass_mailing_id.copy().id
        return super(MarketingActivity, self).copy_data(default=default)

    def write(self, vals):
        if 'trigger_type_ui' in vals:
            vals.pop('trigger_type_ui')
        if 'trigger_type_category' in vals:
            vals.pop('trigger_type_category')
        if vals.get('activity_type') == 'split' and len(self.child_ids | (vals.get('child_ids') or self.env['marketing.activity'])) > 1:
            raise ValidationError(_("Avoid adding an if/else right before a split. There is no way to know which way to go for each branch"))
        if any(activity.campaign_id.state == 'running' for activity in self) and any(field in vals for field in ('interval_number', 'interval_type')):
            vals['require_sync'] = True
        if 'parent_id' in vals and self.trace_ids and not all(t.is_test for t in self.trace_ids):
            # Prevent modifying relationships when real traces exist, as it could create duplicates
            # and would require a full trace resynchronization in some cases.
            raise ValidationError(_("Error! You can't modify the hierarchy of an active Activity."))
        return super().write(vals)

    def _get_full_statistics(self):
        self.env['marketing.trace'].flush_model(['activity_id', 'participant_id', 'state'])
        self.env['mailing.trace'].flush_model([
            'marketing_trace_id', 'links_click_datetime', 'sent_datetime', 'trace_status',
        ])
        self.env['marketing.participant'].flush_model(['is_test'])
        self.env.cr.execute("""
            SELECT
                trace.activity_id,
                COUNT(stat.sent_datetime) AS total_sent,
                COUNT(stat.links_click_datetime) AS total_click,
                COUNT(stat.trace_status) FILTER (WHERE stat.trace_status = 'reply') AS total_reply,
                COUNT(stat.trace_status) FILTER (WHERE stat.trace_status in ('open', 'reply')) AS total_open,
                COUNT(stat.trace_status) FILTER (WHERE stat.trace_status = 'bounce') AS total_bounce,
                COUNT(trace.state) FILTER (WHERE trace.state = 'processed') AS processed,
                COUNT(trace.state) FILTER (WHERE trace.state = 'rejected') AS rejected
            FROM
                marketing_trace AS trace
            LEFT JOIN
                mailing_trace AS stat
                ON (stat.marketing_trace_id = trace.id)
            JOIN
                marketing_participant AS part
                ON (trace.participant_id = part.id)
            WHERE
                (part.is_test = false or part.is_test IS NULL) AND
                trace.activity_id IN %s
            GROUP BY
                trace.activity_id;
        """, (tuple(self.ids), ))
        return self.env.cr.dictfetchall()

    def _get_graph_statistics(self):
        """ Compute activities statistics based on their traces state for the last fortnight """
        past_date = (self.env.cr.now() + timedelta(days=-14)).strftime('%Y-%m-%d 00:00:00')
        stat_map = {}
        base = date.today() + timedelta(days=-14)
        date_range = [base + timedelta(days=d) for d in range(0, 15)]

        self.env['marketing.trace'].flush_model(['activity_id', 'is_test', 'schedule_date', 'state'])
        self.env.cr.execute("""
            SELECT
                activity.id AS activity_id,
                trace.schedule_date::date AS dt,
                count(*) AS total,
                trace.state
            FROM
                marketing_trace AS trace
            JOIN
                marketing_activity AS activity
                ON (activity.id = trace.activity_id)
            WHERE
                activity.id IN %s AND
                trace.schedule_date >= %s AND
                (trace.is_test = false or trace.is_test IS NULL)
            GROUP BY activity.id , dt, trace.state
            ORDER BY dt;
        """, (tuple(self.ids), past_date))

        for stat in self.env.cr.dictfetchall():
            stat_map[(stat['activity_id'], stat['dt'], stat['state'])] = stat['total']
        graph_data = {}
        for activity in self:
            success = []
            rejected = []
            for i in date_range:
                x = i.strftime('%d %b')
                success.append({
                    'x': x,
                    'y': stat_map.get((activity._origin.id, i, 'processed'), 0)
                })
                rejected.append({
                    'x': x,
                    'y': stat_map.get((activity._origin.id, i, 'rejected'), 0)
                })
            graph_data[activity._origin.id] = [
                {'points': success, 'label': _('Success'), 'color': '#28A745'},
                {'points': rejected, 'label': _('Rejected'), 'color': '#D23f3A'}
            ]
        return graph_data

    # STATUS MANAGEMENT
    # ------------------------------------------------------------

    @api.model
    def _cron_update_status(self, batch_size=None):
        """ Cron call only. Loops over active (running) activities and check
        for status to update. """
        campaign_cron_domain = self.env['marketing.campaign']._get_campaign_cron_alive_domain()
        to_check = self.search((
            Domain('campaign_id', 'any', campaign_cron_domain) &
            Domain('trace_ids', 'any', Domain('state', '=', 'waiting'))
        ), limit=batch_size)
        self.env['ir.cron']._commit_progress(remaining=len(to_check))
        for activity in to_check:
            campaign = activity.campaign_id
            try:
                activity._update_waiting_traces()
                # commit in try because it might also fail
                remaining = self.env['ir.cron']._commit_progress(processed=1)
            except Exception as e:  # noqa: BLE001
                self.env['ir.cron']._rollback_progress()
                _logger.warning(
                    'MarketingAutomation: cron failed checking activities status on activity [%s] (campaign [%d]) due to %r',
                    activity.id, campaign.id, e, exc_info=True)
                campaign._message_log(
                    body=_(
                        'Cron failed checking activities status on %(activity)s, received error %(error)s',
                        activity=activity.name,
                        error=repr(e),
                    ),
                    partner_ids=campaign.user_id.partner_id.ids if campaign.user_id.active else False,
                )
                # mark as processed as we handle errors manually; allows to log
                # progress, avoid immediate re-run or deactivation
                remaining = self.env['ir.cron']._commit_progress(processed=1)
            # break if not time remaining
            if not remaining:
                break

    def _update_waiting_traces(self):
        """ Find traces in waiting state whose res_id links to a record
        that matches the activity waiting filter domain. """
        for activity in self:
            # subselect documents passing the wait_value_domain
            activity_domain = Domain(literal_eval(activity.wait_value_domain or '[]'))
            DocumentModel = activity.env[activity.model_name]
            documents_query = DocumentModel._search(activity_domain)
            documents_table = documents_query.table
            exists_subquery = documents_query.subselect(documents_table.id)
            # fetch waiting traces linked to those
            traces_query = activity.env['marketing.trace']._search(Domain('activity_id', '=', activity.id) & Domain('state', '=', 'waiting'))
            traces_table = traces_query.table
            traces_query.add_where(SQL("%s IN %s", traces_table.res_id, exists_subquery))
            # traces_query.limit = 10000
            traces_validated_ids = [r[0] for r in self.env.execute_query(traces_query.select(SQL("%s", traces_table.id)))]

            batch_size = self.env['ir.config_parameter'].sudo().get_int('marketing.trace.batch.size') or 500
            for batch_ids in split_every(batch_size, traces_validated_ids, piece_maker=list):
                allowed = activity.env['marketing.trace'].browse(batch_ids)
                allowed._schedule_based_on_activity()

    # MAIN EXECUTION METHODS
    # ------------------------------------------------------------

    def execute(self, domain: DomainType | None = None) -> MarketingTrace:
        """ Fetch scheduled traces associated to running participants, linked to
        activities given by 'self'. Execute them: for each activity, run the
        specific action on their trace subset.

        :return: traces created for children activities i.e. scheduled followup. """
        # auto-commit except in testing mode
        auto_commit = not modules.module.current_test

        # organize traces by activity
        trace_domain = [
            ('schedule_date', '<=', self.env.cr.now()),
            ('state', '=', 'scheduled'),
            ('activity_id', 'in', self.ids),
            ('participant_id.state', '=', 'running'),
        ]
        if domain:
            trace_domain += domain
        trace_to_activities = dict(self.env['marketing.trace']._read_group(
            trace_domain, groupby=['activity_id'], aggregates=['id:recordset']
        ))

        # execute activity on their traces
        # action execution, 500 seems good to create mail/sms/wa/ execute SA (0 means no iteration -> avoid)
        children = self.env['marketing.trace']
        batch_size = self.env['ir.config_parameter'].sudo().get_int('marketing.execute.batch.size') or 500
        for activity in self.filtered(lambda a: a in trace_to_activities):
            traces = trace_to_activities[activity]
            for traces_batch in (traces[i:i + batch_size] for i in range(0, len(traces), batch_size)):
                children += activity.execute_on_traces(traces_batch)
                if auto_commit:
                    self.env.cr.commit()
        return children

    def execute_on_traces(self, traces: MarketingTrace) -> MarketingTrace:
        """ Execute current activity on given traces.

        :return: traces created for children activities i.e. scheduled followup. """
        self.ensure_one()
        now = self.env.cr.now()
        new_children_traces = self.env['marketing.trace']

        if self.validity_duration:
            duration = relativedelta(**{self.validity_duration_type: self.validity_duration_number})
            invalid_traces = traces.filtered(
                lambda trace: not trace.schedule_date or trace.schedule_date + duration < now
            )
            invalid_traces.action_set_canceled()
            traces = traces - invalid_traces

        # Filter traces not fitting the activity filter and whose record has been deleted
        if self.activity_domain:
            rec_domain = literal_eval(self.activity_domain)
        else:
            rec_domain = []
        if rec_domain:
            user_id = self.campaign_id.user_id or self.env.user
            rec_valid = self.env[self.model_name].with_context(lang=user_id.lang).search(rec_domain)
            rec_ids_domain = rec_valid.ids

            traces_allowed = traces.filtered(lambda trace: trace.res_id in rec_ids_domain)
            # either rejected, either deleted record
            traces_rejected = traces.filtered(lambda trace: trace.res_id not in rec_ids_domain)
        else:
            traces_allowed = traces
            traces_rejected = self.env['marketing.trace']

        if self.activity_type != 'split':
            postponed = self.env['marketing.trace']
            if self._is_an_interaction_trigger_type(self.trigger_type):
                traces_allowed = self._filter_triggered_traces(traces_allowed)
            elif self.trigger_type == 'wait_value':
                domain = literal_eval(self.wait_value_domain or '[]')
                rec_valid_ids = self.env[self.model_name].search(domain).ids
                allowed = traces_allowed.filtered_domain([('res_id', 'in', rec_valid_ids)])
                postponed = traces_allowed - allowed
                traces_allowed = allowed
                postponed.action_set_waiting()

        if traces_allowed:
            activity_method = getattr(self, '_execute_%s' % (self.activity_type))
            new_children_traces += self._generate_children_traces(traces_allowed)
            activity_method(traces_allowed)
            traces.participant_id.check_completed()

        if traces_rejected and self.activity_type != 'split':
            traces_rejected.action_set_rejected(
                message=self.env._('Rejected by activity filter or record deleted / archived'),
                check_participant_completed=True,
            )

        return new_children_traces

    def _execute_action(self, traces: MarketingTrace) -> MarketingTrace:
        """ Server-action based activity. Runs on 'res_ids' linked to traces.

        :return: correctly processed traces, subset of input 'traces' """
        if not self.server_action_id:
            return False

        # Do a loop here because we have to try / catch each execution separately to ensure other traces are executed
        # and proper state message stored
        # TDE note: better multi support ?
        processed_traces = self.env['marketing.trace']
        for trace in traces:
            is_activity_server_action = self.server_action_id.model_name == "marketing.activity"
            action = self.server_action_id.with_context(
                active_model=self.model_name,
                active_ids=[trace.res_id],
                active_id=trace.res_id,
                onchange_self=self if is_activity_server_action else False
            )
            try:
                action.run()
            except Exception as e:
                _logger.warning('Marketing Automation: activity <%s> encountered server action issue %s', self.id, str(e), exc_info=True)
                trace.action_set_error(message=self.env._('Exception in server action: %s', e))
            else:
                processed_traces += trace

        # Update status
        processed_traces.action_set_processed()
        return processed_traces

    def _execute_log_note(self, traces: MarketingTrace) -> MarketingTrace:
        """ Batch-post a note. Note that it can not really fail individually as
        it is basically creating a message. """
        records = self.env[self.model_name].browse(traces.mapped('res_id'))
        records._message_log_batch(
            bodies={record.id: self.log_note_body for record in records},
        )
        traces.action_set_processed()
        return traces

    def _execute_mail(self, traces: MarketingTrace) -> MarketingTrace:
        """ Email marketing based activity. Runs on 'res_ids' linked to traces.
        Launch activity's mailing.mailing on traces res_ids in batch.

        :return: correctly processed traces, subset of input 'traces' """
        # we only allow to continue if the user has sufficient rights, as a sudo() follows
        if not self.env.is_superuser() and not self.env.user.has_group('marketing_automation.group_marketing_automation_user'):
            raise AccessError(_('To use this feature you should be an administrator or belong to the marketing automation group.'))

        res_ids = list(OrderedSet(traces.mapped('res_id')))
        ctx = dict(clean_context(self.env.context), default_marketing_activity_id=self.ids[0], active_ids=res_ids)
        mailing = self.mass_mailing_id.sudo().with_context(ctx)
        processed_traces = self.env['marketing.trace']

        try:
            mailing.action_send_mail(res_ids)
        except Exception as e:  # noqa: BLE001
            _logger.warning('Marketing Automation: activity <%s> encountered mass mailing issue %s', self.id, str(e), exc_info=True)
            traces.action_set_error(message=self.env._('Exception in mass mailing: %s', e))
        else:
            failed_stats = self.env['mailing.trace'].sudo().search([
                ('marketing_trace_id', 'in', traces.ids),
                ('trace_status', 'in', ['error', 'bounce', 'cancel'])
            ])
            error_doc_ids = [stat.res_id for stat in failed_stats if stat.trace_status in ('error', 'bounce')]
            cancel_doc_ids = [stat.res_id for stat in failed_stats if stat.trace_status == 'cancel']

            processed_traces = traces
            canceled_traces = traces.filtered(lambda trace: trace.res_id in cancel_doc_ids)
            error_traces = traces.filtered(lambda trace: trace.res_id in error_doc_ids)

            if canceled_traces:
                canceled_traces.action_set_canceled(message=self.env._('Email cancelled'), check_participant_completed=False)
                processed_traces = processed_traces - canceled_traces
            if error_traces:
                error_traces.action_set_error(message=self.env._('Email failed'))
                processed_traces = processed_traces - error_traces
            if processed_traces:
                processed_traces.action_set_processed()
        return processed_traces

    def _execute_split(self, traces: MarketingTrace) -> MarketingTrace:
        """ A split is an intermediate node without business action, easing split
        of participants. All traces are considered as processed.

        :return: correctly processed traces, subset of input 'traces' """
        traces.action_set_processed()
        return traces

    def _execute_structure(self, traces: MarketingTrace) -> MarketingTrace:
        """
        A structure is an empty node that is only used to store data like an activity. The difference is that this activity does nothing
        and is only used to structure the activities like the user wants.

        :return: correctly processed traces, subset of input 'traces'
        """
        traces.action_set_processed()
        return traces

    def _execute_subscribe_to_list(self, traces: MarketingTrace) -> MarketingTrace:
        """ Subscribe to a mailing list. Try to dynamically find an email to
        add in the mailing list, based on 'primary_email' if defined, otherwise
        just try some common field names. """
        records = self.env[self.model_name].browse(traces.mapped('res_id'))
        primary_emails = records._mail_get_primary_email()

        valid_fnames = [
            fname for fname in (
                'email_from', 'x_email_from',
                'email', 'x_email',
                'partner_email',
                'email_normalized',
            ) if fname in records
        ]

        def _find_email(record):
            # Taken from '_message_add_default_recipients', could be a tool
            return next(
                (
                    record[fname] for fname in valid_fnames if record[fname]
                ), False
            )
        subscribe_emails = {
            record.id: primary_emails[record.id] or _find_email(record)
            for record in records
        }

        failed_records = records.browse()
        for record in records:
            email_to = subscribe_emails[record.id]
            if not email_to:
                failed_records += records
                continue
            self.subscribe_to_list_id._update_subscription_from_email(
                email_to, self.subscribe_to_list_action == 'remove', False,
            )

        failed_traces = traces.filtered(lambda t: t.res_id in failed_records.ids)
        failed_traces.action_set_canceled(_("Could not update the mailing list subscription"), True)
        (traces - failed_traces).action_set_processed()
        return (traces - failed_traces)

    # ------------------------------------------------------------
    # TRACES MANAGEMENT
    # ------------------------------------------------------------

    def _generate_children_traces(self, traces: MarketingTrace) -> MarketingTrace:
        """Generate child traces for child activities that are directly time
        dependant e.g. after an activity, after not opened email, ...
        Action-based traces (mail open, ...) have no specific scheduled date
        as they depend on external actions.

        Split: either trigger_type is an interaction (e.g. mail_open) and split
        is done based on that interaction. Otherwise the domain is taken into
        account.

        :param traces: marketing.trace records which have been processed and
          validated and for which we want to generate children traces

        :return: generated child traces
        """
        cron_trigger_dates = set()
        trace_vals_list = []

        # begin by performing the split (done here to split children, not considered
        # as part of split activity execution)
        split_traces = self.activity_type == 'split'
        no_traces, yes_traces = self.env['marketing.trace'], traces
        if split_traces and self._is_an_interaction_trigger_type(self.trigger_type):
            yes_traces = self._filter_triggered_traces(traces)
            no_traces = traces - yes_traces
        elif split_traces:
            # fetch documents linked to traces, passing domain - at this point chunk
            # size should be limited, hence search is ok
            split_domain = self._parse_mailing_domain('split_domain')
            passing_docs = self.env[self.model_name].search(Domain('id', 'in', traces.mapped('res_id')) & split_domain)
            yes_traces = traces.filtered_domain([('res_id', 'in', passing_docs.ids)])
            no_traces = traces - yes_traces

        # when only one branch of the split is alive -> cancel the other part
        if split_traces and not self.child_ids.filtered('is_split_no'):
            traces = yes_traces
            no_traces.action_set_processed(check_participant_completed=True)
        elif split_traces and not self.child_ids.filtered(lambda a: a.is_split_no is False):
            traces = no_traces
            yes_traces.action_set_processed(check_participant_completed=True)

        reschedule_trigger_types = self._get_reschedule_trigger_types()
        should_cancel = []
        triggering_traces_ids_by_res_id = defaultdict(lambda: self.env['marketing.trace'])
        triggering_traces_ids_by_res_id.update(
            self.child_ids
                .filtered(lambda child: child.activity_type not in ['activity', 'wait_value']).mapped('triggering_activity_id')
                .trace_ids.grouped(lambda trace: (trace.activity_id.id, trace.participant_id.id))
        )
        for activity in self.child_ids:
            activity_offset = relativedelta(**{activity.interval_type: activity.interval_number})

            action_trigger = (activity.trigger_type or "").replace('not_', '')
            reschedule_triggered_activities = activity.trigger_type in reschedule_trigger_types
            already_processed = activity.triggering_activity_id.trace_ids.filtered(lambda t: (t.processed_triggers or "").count(action_trigger)).grouped('res_id')
            for trace in traces:
                if split_traces:
                    add_trace = trace in (no_traces if activity.is_split_no else yes_traces)
                    if not add_trace:
                        continue
                should_cancel.append(reschedule_triggered_activities and trace.res_id in already_processed)
                trace_vals = {
                    'parent_id': trace.id,
                    'participant_id': trace.participant_id.id,
                    'activity_id': activity.id,
                    'triggering_trace_id': triggering_traces_ids_by_res_id[activity.triggering_activity_id.id, trace.participant_id.id].id
                }

                # xor between the 2
                if activity.activity_type == 'split' or bool(reschedule_triggered_activities) != bool(trace.res_id in already_processed):
                    schedule_date = activity._plan_schedule_date(trace.schedule_date, activity_offset)
                    trace_vals['schedule_date'] = schedule_date
                    cron_trigger_dates.add(schedule_date)
                trace_vals_list.append(trace_vals)

        child_traces = self.env['marketing.trace'].create(trace_vals_list)
        for trace, cancel in zip(child_traces, should_cancel):
            if cancel:
                _opposite_triggers, msg = self._get_opposite_trigger_types().get(trace.trigger_type, ["", _("Opposite trigger processed")])
                trace.action_set_canceled(msg, True)

        if cron_trigger_dates:
            # based on created activities, we schedule CRON triggers that match the scheduled_dates
            # we use a set to only trigger the CRON once per timeslot event if there are multiple
            # marketing.participants
            cron = self.env.ref('marketing_automation.ir_cron_campaign_execute_activities')
            cron._trigger(cron_trigger_dates)

        return child_traces

    def _filter_triggered_traces(self, traces_to_check) -> MarketingTrace:
        """
        :return: allowed_traces
        """
        event_to_test = self.trigger_type.replace("not_", "")
        triggered_res_ids = (self.triggering_activity_id or self.parent_id).trace_ids.filtered(lambda t: (t.processed_triggers or "").count(event_to_test)).mapped("res_id")
        triggered_traces = traces_to_check.filtered_domain([('res_id', 'in', triggered_res_ids)])

        if self.trigger_type in self._get_reschedule_trigger_types():
            return traces_to_check - triggered_traces
        else:
            return triggered_traces

    def _plan_schedule_date(self, start, offset):
        """
            :param start: starting datetime
            :param offset: offset datetime to apply
        """
        self.ensure_one()
        start = start or self.env.cr.now()
        if not self.campaign_id.scheduling_calendar_id or not offset:
            return start + offset
        planning_fn = self.campaign_id.scheduling_calendar_id.plan_hours if offset.hours else self.campaign_id.scheduling_calendar_id.plan_days
        if self.interval_type == "hours":
            return planning_fn(offset.hours or 0, start)
        elif self.interval_type == "days":
            return planning_fn(offset.days or 0, start)
        # mainly for months -> depends on actual days to reschedule ? -> TDE FIXME
        # check to add an easy "first open day after my offseted date" tool
        now = fields.Datetime.now()
        other = now - offset
        _days = (now - other).days  # does not make sense to plan 31 open days for 1 month
        return start + offset

    # ------------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------------

    def action_view_sent(self):
        return self._action_view_documents_filtered('sent')

    def action_view_replied(self):
        return self._action_view_documents_filtered('reply')

    def action_view_clicked(self):
        return self._action_view_documents_filtered('click')

    def action_view_opened(self):
        return self._action_view_documents_filtered('open')

    def _action_view_documents_filtered(self, view_filter: str) -> dict[str, str]:
        if not self.mass_mailing_id:  # Only available for mass mailing
            return False
        action = self.env["ir.actions.actions"]._for_xml_id("marketing_automation.marketing_participants_action_mail")

        if view_filter == 'reply':
            found_traces = self.trace_ids.filtered(lambda trace: trace.mailing_trace_status == view_filter)
        elif view_filter == 'open':
            found_traces = self.trace_ids.filtered(lambda trace: trace.mailing_trace_status in ('open', 'reply'))
        elif view_filter == 'sent':
            found_traces = self.trace_ids.filtered('mailing_trace_ids.sent_datetime')
        elif view_filter == 'click':
            found_traces = self.trace_ids.filtered('mailing_trace_ids.links_click_datetime')
        else:
            found_traces = self.env['marketing.trace']

        participants = found_traces.participant_id
        action.update({
            'display_name': _('Participants of %(activity)s (%(filter)s)', activity=self.name, filter=view_filter),
            'domain': [('id', 'in', participants.ids)],
            'context': dict(self.env.context, create=False)
        })
        return action

    # ------------------------------------------------------------
    # TOOLS
    # ------------------------------------------------------------

    def _get_reschedule_trigger_types(self) -> set[str]:
        """ Retrieve a set of trigger types that have a schedule_date that depends
        on parent or activity / campaign, not on external user actions.

        :returns: set of ``trigger_type`` elements
        :rtype: set[str]
        """
        return {'activity', 'begin', 'mail_not_open', 'mail_not_click', 'mail_not_reply', 'wait_value'}

    def _get_implied_processed_events(self) -> dict[str, set]:
        """
            Return a set of events that should be considered as processed on the trigger_type.
        """
        return {
            'mail_open': {'mail_open'},
            'mail_click': {'mail_open', 'mail_click'},
            'mail_reply': {'mail_open', 'mail_click', 'mail_reply'},
            'mail_bounce': {'mail_bounce'}
        }

    def _get_opposite_trigger_types(self) -> dict[str, tuple]:
        """ Return triggers considered as opposite which means flows should not
        execute them if the first one is processed. """
        return {
            'activity': (
                [], '',
            ),
            'begin': (
                [], '',
            ),
            'wait_value': (
                [], '',
            ),
            'mail_bounce': (
                ['mail_click', 'mail_open', 'mail_reply', 'activity'],
                self.env._('Parent activity mail bounced'),
            ),
            'mail_click': (
                ['mail_not_click'],
                self.env._('Parent activity mail clicked'),
            ),
            'mail_not_click': (
                ['mail_click'], '',
            ),
            'mail_not_open': (
                ['mail_open'], '',
            ),
            'mail_not_reply': (
                ['mail_reply'], '',
            ),
            'mail_open': (
                ['mail_not_open'],
                self.env._('Parent activity mail opened'),
            ),
            'mail_reply': (
                ['mail_not_reply'],
                self.env._('Parent activity mail replied'),
            ),
        }

    @api.model
    def _is_a_bounce_trigger_type(self, trigger_type):
        return "bounce" in trigger_type

    @api.model
    def _is_a_reply_trigger_type(self, trigger_type):
        return trigger_type.endswith("reply")

    @api.model
    def _is_an_interaction_trigger_type(self, trigger_type):
        return trigger_type not in [False, None, 'activity', 'begin', 'collect_reply', 'wait_value']

    def _parse_mailing_domain(self, fname):
        domain = self[fname]
        try:
            parsed = Domain(literal_eval(domain))
        except Exception:  # noqa: BLE001
            _logger.warning('MarketingAutomation: failed parsing domain of activity [%d]', self.id, exc_info=True)
            parsed = Domain('id', 'in', [])
        return parsed
