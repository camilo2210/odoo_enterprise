from __future__ import annotations

import logging
import traceback
import typing

from collections import defaultdict

from ast import literal_eval
from dateutil.relativedelta import relativedelta
from uuid import uuid4

from odoo import api, fields, models, modules, tools, _
from odoo.fields import Datetime, Domain
from odoo.exceptions import ValidationError, AccessError, UserError
from odoo.tools import convert
from odoo.tools.func import deprecated
from odoo.tools.misc import clean_context, OrderedSet

_logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from odoo.api import DomainType
    from odoo.api import ValuesType
    from odoo.addons.marketing_automation.models.marketing_participant import MarketingParticipant


class MarketingCampaign(models.Model):
    _name = 'marketing.campaign'
    _description = 'Marketing Campaign'
    _inherit = ['mail.activity.mixin', 'mail.thread']
    _inherits = {'utm.campaign': 'utm_campaign_id'}
    _order = 'create_date DESC'

    # campaign description
    utm_campaign_id = fields.Many2one('utm.campaign', 'UTM Campaign', ondelete='restrict', required=True, index=True)
    responsible_partner_id = fields.Many2one("res.partner", related="utm_campaign_id.user_id.partner_id")
    campaign_title = fields.Char(string="Campaign Title", related='utm_campaign_id.title', tracking=1)
    active = fields.Boolean(default=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('running', 'Running'),
        ('stopped', 'Stopped')
        ], copy=False, default='draft', tracking=2,
        group_expand=True)
    # target model
    model_id = fields.Many2one(
        'ir.model', string='Model', index=True, required=True, ondelete='cascade', tracking=3,
        default=lambda self: self.env.ref('base.model_res_partner', raise_if_not_found=False),
        domain="['&', ('is_mail_thread', '=', True), ('model', '!=', 'mail.blacklist')]")
    model_name = fields.Char(string='Model Name', related='model_id.model', readonly=True, store=True)
    # Enroll options
    enroll_unique_field_id = fields.Many2one(
        'ir.model.fields', string='Unique Field',
        compute='_compute_enroll_unique_field_id', readonly=False, store=True,
        domain="[('model_id', '=', model_id), ('ttype', 'in', ['char', 'integer', 'many2one', 'text', 'selection']), ('store', '=', True)]",
        help="""Used to avoid duplicates based on model field.\ne.g.
                For model 'Customers', select email field here if you don't
                want to process records which have the same email address""")
    enroll_multiple = fields.Boolean("Participants can re-enroll",
        help="Allows a single record to re-enter the flow as long as all previous participants are done.")
    # Enroll triggers
    enroll_type = fields.Selection([
        ("domain", "Filter"),
        ("action", "Event"),
        ("date", "Date"),
        ("anniversary", "Anniversary"),
        ("on_demand", "Manual"),
        ("webhook", "Webhook")], string="Trigger type", required=True, default="domain")
    blacklisted_enroll_type = fields.Json(compute="_compute_blacklisted_enroll_type")
    enroll_domain = fields.Char(string="Filter", compute='_compute_enroll_domain', readonly=False, store=True, tracking=True)
    enroll_recipients_count = fields.Integer('# Of Recipients', compute='_compute_enroll_recipients_count')
    # -- date/anniversary enroll
    enroll_date_field_id = fields.Many2one(
        "ir.model.fields", string="Date field",
        compute="_compute_enroll_date_field_id",
        domain="[('model_id', '=', model_id), ('ttype', 'in', ['date', 'datetime']), ('store', '=', True)]",
        store=True, readonly=False)
    enroll_date_delay_number = fields.Integer(
        "Date-based delay unit",
        compute='_compute_enroll_date_delay_data', readonly=False, store=True,
    )
    enroll_date_delay_type = fields.Selection(
        [
            ('hours', 'Hours'),
            ('days', 'Days'),
            ('weeks', 'Weeks'),
            ('months', 'Months'),
        ],
        compute='_compute_enroll_date_delay_data', readonly=False, store=True,
    )
    enroll_date_delay_order = fields.Selection(
        [('after', 'After'), ('before', 'Before')],
        compute='_compute_enroll_date_delay_data', readonly=False, store=True,
    )
    # -- action enroll
    enroll_action_type = fields.Selection(
        [
            ('subscribe', "Subscribed to List"),
        ],
        compute="_compute_enroll_action_type", readonly=False, store=True,
    )
    # ---- action: subscribe to list
    mailing_list_ids = fields.Many2many("mailing.list",
        string="Lists",
        compute="_compute_enroll_action_data",
        readonly=False,
        store=True,
    )
    # -- webhook enroll
    # webhook enrollment
    webhook_url = fields.Char(compute='_compute_webhook_url', help='Use this URL in the third-party app to call the webhook.')
    webhook_uuid = fields.Char(string='Webhook UUID', readonly=True, copy=False, default=lambda self: str(uuid4()))
    webhook_allow_create = fields.Boolean(string='Allow Record Creation', default=False,
        help='Allow the creation of new records through the webhook with create_values')
    webhook_log_calls = fields.Boolean(string='Log Calls', copy=False, groups='base.group_system')
    # Mailing Filter
    mailing_filter_ids = fields.Many2many(
        'mailing.filter', 'marketing_campaign_filter_rel', 'marketing_campaign_id', 'mailing_filter_id', string='Dynamic Lists',
        domain="[('mailing_model_name', '=', model_name)]",
        compute='_compute_mailing_filter_ids', readonly=False, store=True, index='btree_not_null')
    # cron management
    cron_enroll_failure_dt = fields.Datetime("Enroll Failure")
    cron_activities_failure_dt = fields.Datetime("Execution Failure")
    # activities
    marketing_activity_ids = fields.One2many('marketing.activity', 'campaign_id', copy=False)
    mass_mailing_count = fields.Integer('# Mailings', compute='_compute_mass_mailing_count')
    link_tracker_click_count = fields.Integer('# Clicks', compute='_compute_link_tracker_click_count')
    last_sync_date = fields.Datetime(string='Last activities synchronization', copy=False)
    require_sync = fields.Boolean(string="Sync of participants is required", compute='_compute_require_sync')
    scheduling_calendar_id = fields.Many2one(
        'resource.calendar', string="Use Calendar",
        ondelete='restrict',
        help="When calculating a day-based timed condition, it is possible to use a calendar to compute the date based on working days.")
    collect_reply_early_end = fields.Boolean("Cancel flows with global reply catcher")
    # participants
    participant_ids = fields.One2many('marketing.participant', 'campaign_id', string='Participants', copy=False)
    running_participant_count = fields.Integer(string="# of active participants", compute='_compute_participants')
    completed_participant_count = fields.Integer(string="# of completed participants", compute='_compute_participants')
    total_participant_count = fields.Integer(string="# of active and completed participants", compute='_compute_participants')
    test_participant_count = fields.Integer(string="# of test participants", compute='_compute_participants')
    # Position of the campaign node in the plan:
    # Format:
    #   - 'trigger': coordinates of the main trigger node
    #   - 'trigger_flag': coordinates of the flag of the main trigger node
    #   - 'reply_trigger': coordinates of the reply trigger node
    #   - 'reply_trigger_flag': coordinates of the flag of the reply trigger node
    view_coordinates = fields.Json()
    is_admin_and_debug = fields.Boolean(compute='_compute_is_admin_and_debug')

    @api.constrains('model_id', 'mailing_filter_ids')
    def _check_mailing_filter_model(self):
        """Check that if the favorite filters are set, they must contain the same target model as campaign"""
        for campaign in self:
            if any(
                campaign.model_id != mailing_filter_id.mailing_model_id
                for mailing_filter_id in campaign.mailing_filter_ids
            ):
                raise ValidationError(
                    _("The saved filters target different recipients and are incompatible with this campaign.")
                )

    @api.constrains('model_id', 'enroll_unique_field_id')
    def _check_enroll_unique_field_id(self):
        for campaign in self.filtered('enroll_unique_field_id'):
            if campaign.enroll_unique_field_id.model_id != campaign.model_id:
                raise ValidationError(_(
                    'Field used for unicity check does not match campaign model.'
                ))
            if campaign.enroll_unique_field_id.ttype not in ('char', 'integer', 'many2one', 'text', 'selection'):
                raise ValidationError(_(
                    'Field used for unicity check should be a char, integer, manyone, text or selection field.'
                ))

    @api.constrains('enroll_date_field_id', 'enroll_type', 'model_id')
    def _check_enroll_anniversary_date_field(self):
        """ Anniversary / Date fields should be stored date(time) fields """
        for campaign in self.filtered(lambda c: c.model_id and c.enroll_type in ('anniversary', 'date')):
            if not campaign.enroll_date_field_id:
                raise ValidationError(
                    _('Anniversary / Date campaigns should have a anniversary field set up.')
                )
            if campaign.enroll_date_field_id.model_id != campaign.model_id:
                raise ValidationError(
                    _('Anniversary / Date campaigns should have a anniversary field coming from target model.')
                )
            if not campaign.enroll_date_field_id.ttype in ('date', 'datetime') or not campaign.enroll_date_field_id.store:
                raise ValidationError(
                    _('Anniversary / Date field should be a valid stored date or datetime field.')
                )

    @api.constrains('enroll_date_delay_number', 'enroll_type')
    def _check_enroll_anniversary_date_delay(self):
        """ Anniversary / Date campaigns delay check """
        for campaign in self.filtered(lambda c: c.model_id and c.enroll_type in ('anniversary', 'date')):
            if (campaign.enroll_date_delay_number or 0) < 0:
                raise ValidationError(
                    _('Anniversary / Date campaigns should have a positive delay.')
                )

    @api.constrains('enroll_type', 'model_id')
    def _check_enroll_action_consistency(self):
        invalid_campaigns = self.filtered_domain([
            ('enroll_type', '=', 'action'),
            ('model_id.model', 'not in', self._ENROLL_ACTION_TARGET_MODELS),
        ])
        if invalid_campaigns:
            raise ValidationError(_(
                "You have action triggered campaigns that are using an incorrect model: %(campaign_names)s",
                campaign_names=tools.format_list(self.env, invalid_campaigns.mapped('name')),
            ))

    @property
    def _ENROLL_ACTION_TARGET_MODELS(self):
        return {'res.partner'}

    @api.constrains('view_coordinates')
    def _check_view_coordinates_keys(self):
        coordinates_keys = {'reply_trigger', 'reply_trigger_flag', 'trigger', 'trigger_flag'}
        for campaign in self.filtered('view_coordinates'):
            view_coordinates = campaign.view_coordinates
            if set(view_coordinates.keys()) - coordinates_keys:
                raise ValidationError(_("The coordinates for campaigns shouldn't be messed with."))
            for key in coordinates_keys:
                coordinate_values = view_coordinates.get(key)
                if not coordinate_values:
                    continue
                if coordinate_values is not None and set(coordinate_values.keys()) - {'x', 'y'}:
                    raise ValidationError(_("The coordinates for campaigns shouldn't be messed with."))
                if not (isinstance(coordinate_values.get('x', 0), (int, float)) and isinstance(coordinate_values.get('y', 0), (int, float))):
                    raise ValidationError(_("The coordinates for campaigns shouldn't be messed with."))

    @api.depends('model_name')
    @api.depends_context('uid')
    def _compute_blacklisted_enroll_type(self):
        for record in self:
            blacklist = []
            if record.model_name not in record._ENROLL_ACTION_TARGET_MODELS:
                blacklist.append('action')
            if not self.env.is_admin():
                if record.enroll_type != 'webhook':
                    blacklist.append('webhook')
            record.blacklisted_enroll_type = blacklist

    @api.depends('enroll_type')
    def _compute_enroll_action_type(self):
        self.filtered(lambda c: c.enroll_type != 'action').enroll_action_type = False

    @api.depends('enroll_action_type', 'enroll_type')
    def _compute_enroll_action_data(self):
        to_reset = self.filtered(lambda c: c.enroll_type != 'action')
        to_reset.update({fname: False for fname in self._ENROLL_ACTION_FIELDS_TO_RESET})
        for campaign in (self - to_reset):
            if campaign.enroll_action_type != 'subscribe':
                campaign.mailing_list_ids = False

    @property
    def _ENROLL_ACTION_FIELDS_TO_RESET(self):
        return {'mailing_list_ids'}

    @api.depends('model_id')
    def _compute_enroll_unique_field_id(self):
        for campaign in self:
            campaign.enroll_unique_field_id = False

    @api.depends('model_id', 'enroll_domain', 'mailing_filter_ids', 'mailing_filter_ids.mailing_domain')
    def _compute_enroll_domain(self):
        for campaign in self:
            if campaign.mailing_filter_ids:
                campaign.enroll_domain = repr(Domain.OR(literal_eval(mailing_filter.mailing_domain) for mailing_filter in campaign.mailing_filter_ids))
            else:
                campaign.enroll_domain = repr([])

    @api.depends('enroll_domain')
    def _compute_enroll_recipients_count(self):
        """Compute the total number of recipients affected by the specified enroll_domain"""
        for campaign in self:
            if campaign.enroll_domain and campaign.model_name:
                try:
                    enroll_domain = literal_eval(campaign.enroll_domain)
                except Exception:  # noqa: BLE001
                    enroll_domain = Domain.FALSE
                try:
                    campaign.enroll_recipients_count = self.env[campaign.model_name].search_count(Domain(enroll_domain))
                except ValueError:
                    campaign.enroll_recipients_count = 0
            else:
                campaign.enroll_recipients_count = 0

    @api.depends('enroll_type', 'model_id')
    def _compute_enroll_date_field_id(self):
        if to_reset := self.filtered(lambda c: (
            not c.model_id or c.enroll_type not in ('anniversary', 'date') or
            c.enroll_date_field_id.model_id != c.model_id
        )):
            to_reset.enroll_date_field_id = False

    @api.depends('enroll_type')
    def _compute_enroll_date_delay_data(self):
        reset_values = {
            'enroll_date_delay_number': False,
            'enroll_date_delay_type': False,
            'enroll_date_delay_order': False,
        }
        default_values = {
            'enroll_date_delay_number': 0,
            'enroll_date_delay_type': 'hours',
            'enroll_date_delay_order': 'after',
        }
        to_reset = self.filtered(lambda c: c.enroll_type not in ('anniversary', 'date'))
        to_update = (self - to_reset).filtered(lambda c: not c.enroll_date_delay_type and not c.enroll_date_delay_order)
        to_reset.update(reset_values)
        to_update.update(default_values)

    @api.depends('webhook_uuid', 'enroll_type')
    def _compute_webhook_url(self):
        webhook_campaigns = self.filtered(lambda r: r.enroll_type == 'webhook')
        for campaign in webhook_campaigns:
            campaign.webhook_url = '%s/mkauto/webhook/%s/%s%s' % (
                campaign.get_base_url(),
                campaign.id, campaign.webhook_uuid,
                '' if campaign.state == 'running' else '/test',
            )
        (self - webhook_campaigns).webhook_url = ''

    @api.depends('model_name')
    def _compute_mailing_filter_ids(self):
        for mailing in self:
            mailing.mailing_filter_ids = [fields.Command.clear()]

    @api.depends('marketing_activity_ids.mass_mailing_id')
    def _compute_mass_mailing_count(self):
        # TDE NOTE: this could be optimized but is currently displayed only in a form view, no need to optimize now
        all_mailings = dict(self.env['mailing.mailing']._read_group(
            [('campaign_id', 'in', self.utm_campaign_id.ids), ('mailing_type', '=', 'mail'), ('is_template', '=', False)],
            ['campaign_id'],
            ['id:recordset']
        ))
        # We use '._origin' to avoid getting a NewId (as the record is in a transient state) instead of id
        for campaign in self:
            linked_mailings = all_mailings.get(campaign._origin.utm_campaign_id, self.env['mailing.mailing'])
            campaign.mass_mailing_count = len(linked_mailings)

    @api.depends('utm_campaign_id')
    def _compute_link_tracker_click_count(self):
        click_data = self.env['link.tracker.click'].sudo()._read_group(
            [('campaign_id', 'in', self.utm_campaign_id.ids)],
            ['campaign_id'],
            ['__count']
        )
        mapped_data = {utm_campaign.id: count for utm_campaign, count in click_data}
        for campaign in self:
            campaign.link_tracker_click_count = mapped_data.get(campaign.utm_campaign_id.id, 0)

    @api.depends('marketing_activity_ids.require_sync', 'last_sync_date')
    def _compute_require_sync(self):
        for campaign in self:
            if campaign.last_sync_date and campaign.state == 'running':
                activities_changed = campaign.marketing_activity_ids.filtered(lambda activity: activity.require_sync)
                campaign.require_sync = bool(activities_changed)
            else:
                campaign.require_sync = False

    @api.depends('participant_ids.state')
    def _compute_participants(self):
        participants_data = self.env['marketing.participant']._read_group(
            [('campaign_id', 'in', self.ids)],
            ['campaign_id', 'state', 'is_test'],
            ['__count'])
        mapped_data = defaultdict(dict)
        for campaign, state, is_test, count in participants_data:
            if is_test:
                mapped_data[campaign.id]['is_test'] = mapped_data[campaign.id].get('is_test', 0) + count
            else:
                mapped_data[campaign.id][state] = count
        for campaign in self:
            campaign_data = mapped_data[campaign.id]
            campaign.running_participant_count = campaign_data.get('running', 0)
            campaign.completed_participant_count = campaign_data.get('completed', 0)
            campaign.total_participant_count = campaign.completed_participant_count + campaign.running_participant_count
            campaign.test_participant_count = campaign_data.get('is_test', 0)

    @api.depends_context('uid')
    def _compute_is_admin_and_debug(self):
        self.is_admin_and_debug = self.env.is_admin() and self.env.user.has_group('base.group_no_one')

    @api.onchange('model_id')
    def _onchange_model_id(self):
        if any(campaign.marketing_activity_ids for campaign in self):
            return {'warning': {
                'title': _("Warning"),
                'message': _("Switching Target Model invalidates the existing activities. "
                             "Either update your activity actions to match the new Target Model or delete them.")
            }}

    # ------------------------------------------------------------
    # CRUD / ORM / MAIL
    # ------------------------------------------------------------

    def copy(self, default=None):
        """ Copy the activities of the campaign, each parent_id of each child
        activities should be set to the new copied parent activity. """
        new_campaigns = super().copy(dict(default or {}))

        for old_campaign, new_campaign in zip(self, new_campaigns):
            old_to_new = {}

            for marketing_activity_id in old_campaign.marketing_activity_ids:
                new_marketing_activity_id = marketing_activity_id.copy()
                old_to_new[marketing_activity_id] = new_marketing_activity_id
                new_marketing_activity_id.write({
                    'campaign_id': new_campaign.id,
                    'require_sync': False,
                    'trace_ids': False,
                })

            for marketing_activity_id in new_campaign.marketing_activity_ids:
                marketing_activity_id.parent_id = old_to_new.get(
                    marketing_activity_id.parent_id)
            # TDE note: add unit tests
            new_campaign.marketing_activity_ids.mass_mailing_id.campaign_id = new_campaign.utm_campaign_id

        return new_campaigns

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.update({'is_auto_campaign': True})
        new_campaign = super().create(vals_list)
        if new_campaign.filtered(lambda c: c.enroll_type == 'webhook') and not self.env.is_admin():
            raise AccessError(_('Campaigns with a webhook enrollment type cannot be created by non-admin users'))
        new_campaign.action_sort_steps()
        return new_campaign

    def write(self, vals):
        if not vals.get('active', True):
            vals['state'] = 'stopped'
        for campaign in self:
            if (
                vals.get('enroll_type') == 'webhook'
                or (campaign.enroll_type == 'webhook' and vals.get('enroll_type', 'webhook') != 'webhook')
                or 'webhook_allow_create' in vals
            ) and not self.env.is_admin():
                raise AccessError(_('Oops! Only Administrators can change a trigger to or from Webhook!'))
            if campaign.enroll_type == 'webhook' and 'model_id' in vals and not self.env.is_admin():
                raise AccessError(_('Oops! Only Administrators can change the target of a webhook campaign!'))
        return super().write(vals)

    def _mail_get_partner_fields(self, introspect_fields=False):
        return ["responsible_partner_id"]

    # ------------------------------------------------------------
    # TRACES SYNCHRONIZE / MANAGEMENT
    # ------------------------------------------------------------

    def _set_scheduled_traces_to_canceled(self, message):
        self.ensure_one()
        self.env['marketing.trace'].search([('campaign_id', '=', self.id), ('state', '=', 'scheduled')]).action_set_canceled(message)

    def action_set_synchronized(self):
        """ Reset campaign and activities 'need synchronization' flags. """
        self.write({'last_sync_date': self.env.cr.now()})
        self.mapped('marketing_activity_ids').write({'require_sync': False})

    def action_synchronize_traces(self):
        """ Calling traces synchronization manually form form view """
        return self._synchronize_traces()

    def _synchronize_traces(self):
        """ Synchronizes all participants traces based on activities requiring
        synchronization aka it mainly creates and updates 'marketing.trace'
        records. It is done in 2 steps:

        * update traces related to activities requiring sync, based on their
          ``require_sync`` field. For those we update ``schedule date``.

        * create traces for new activities added in the workflow, aka created
          after campaign ``last_sync_date``:

        * activities without parent_id: create traces for all running participants;

        * 'general_mail_reply': create traces like before without any schedule_date (will be set when
           a mail_reply is processed)

        * other activities: create child for traces linked to the parent of
          the newly created activity

        * for 'not' triggers take into account brother traces that are already
          processed e.g. do not schedule 'mail_not_open' if 'mail_open' is
          already processed;

        Note that scheduling is done right after parent processing independently
        of other time considerations.

        This sets both campaign and all activities to be synchronized. It is
        used mainly on campaign form view, when activities have been modified
        by marketing users.
        """
        now = self.env.cr.now()
        batch_size = int(self.env['ir.config_parameter'].sudo().get_int('marketing.trace.batch.size')) or 100

        for campaign in self:
            # Action 1: On activity modification
            modified_activities = campaign.marketing_activity_ids.filtered(
                lambda activity: activity.require_sync
            )
            traces_to_reschedule = self.env['marketing.trace'].search([
                ('state', '=', 'scheduled'),
                ('activity_id', 'in', modified_activities.ids)])
            traces_to_reschedule._update_schedule_date()

            # Action 2: On activity creation
            created_activities = campaign.marketing_activity_ids.filtered(
                lambda activity: (
                    campaign.last_sync_date and activity.create_date >= campaign.last_sync_date
                )
            )

            # pre-fetch existing traces to avoid duplicates
            existing_traces = self.env['marketing.trace']
            if created_activities:
                existing_traces = self.env['marketing.trace'].search([
                    ('activity_id', 'in', created_activities.ids),
                ])
            for activity in created_activities:
                activity_offset = relativedelta(**{activity.interval_type: activity.interval_number})
                participants_with_traces = existing_traces.filtered(lambda trace: trace.activity_id == activity).participant_id

                # Case 1: root activity of the tree
                # Create new root traces for all running participants -> consider campaign begin date is now to avoid spamming participants
                if activity.trigger_type in ['begin', 'collect_reply']:
                    participants = self.env['marketing.participant'].search([
                        ('state', '=', 'running'),
                        ('campaign_id', '=', campaign.id),
                        ('id', 'not in', participants_with_traces.ids),
                    ])
                    schedule_date = activity._plan_schedule_date(now, activity_offset)
                    for participants_batch in tools.split_every(batch_size, participants, piece_maker=list):
                        self.env['marketing.trace'].create([
                            {
                                'activity_id': activity.id,
                                'participant_id': participant.id,
                                'schedule_date': schedule_date,
                            }
                            for participant in participants_batch
                        ])
                else:
                    valid_parent_traces = self.env['marketing.trace'].search([
                        ('state', '=', 'processed'),
                        ('activity_id', '=', activity.parent_id.id),
                        ('participant_id', 'not in', participants_with_traces.ids),
                    ])

                    # avoid creating new traces that would have processed brother traces already processed
                    # example: do not create a mail_not_click trace if mail_click is already processed
                    if activity.trigger_type in activity._get_reschedule_trigger_types():
                        opposite_triggers, _msg = activity._get_opposite_trigger_types()[activity.trigger_type]
                        if opposite_triggers:
                            brother_traces = self.env['marketing.trace'].search([
                                ('parent_id', 'in', valid_parent_traces.ids),
                                ('trigger_type', 'in', opposite_triggers),
                                ('state', '=', 'processed'),
                            ])
                            valid_parent_traces = valid_parent_traces - brother_traces.mapped('parent_id')

                    valid_parent_traces.mapped('participant_id').filtered(lambda participant: participant.state == 'completed').action_set_running()
                    for parent_traces_batch in tools.split_every(batch_size, valid_parent_traces, piece_maker=list):
                        trace_vals_list = []
                        for parent_trace in parent_traces_batch:
                            if activity.trigger_type in activity._get_reschedule_trigger_types():
                                schedule_date = Datetime.from_string(parent_trace.schedule_date) + activity_offset
                            else:
                                schedule_date = False
                            trace_vals_list.append({
                                'activity_id': activity.id,
                                'participant_id': parent_trace.participant_id.id,
                                'parent_id': parent_trace.id,
                                'schedule_date': schedule_date,
                            })
                        self.env['marketing.trace'].create(trace_vals_list)

        self.action_set_synchronized()

    # ------------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------------

    def action_start_campaign(self):
        self._cleanup_campaign()
        self._check_campaign_validity()
        # trigger CRON job ASAP so that participants are synced
        cron = self.env.ref('marketing_automation.ir_cron_campaign_sync_participants')
        cron._trigger(at=self.env.cr.now())
        self.write({'state': 'running'})

    def _check_campaign_validity(self):
        if any(not campaign.marketing_activity_ids for campaign in self):
            raise ValidationError(_('You must set up at least one activity to start this campaign.'))
        invalid_root_activities = self.mapped('marketing_activity_ids').filtered_domain([('parent_id', '=', False), ('trigger_type', 'not in', ['begin', 'collect_reply'])])
        if invalid_root_activities:
            raise ValidationError(_("Your campaign isn't valid as you have some root activities that have a checkpoint: %(activity_names)s", activity_names=tools.format_list(self.env, invalid_root_activities.mapped('name'))))

    def _cleanup_campaign(self):
        void_activities = self.mapped('marketing_activity_ids').filtered_domain([('activity_type', '=', 'structure'), ('interval_number', '=', 0), ('trigger_type', 'in', ['activity', 'begin', 'collect_reply'])])
        void_activities._delete_marketing_activity()

    def action_stop_campaign(self):
        self.write({'state': 'stopped'})

    def action_view_mailings(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("marketing_automation.mail_mass_mailing_action_marketing_automation")
        action['domain'] = [
            '&',
            ('use_in_marketing_automation', '=', True),
            ('campaign_id', 'in', self.utm_campaign_id.ids),
            ('mailing_type', '=', 'mail')
        ]
        action['context'] = dict(self.env.context)
        action['context'].update({
            # defaults
            'default_mailing_model_id': self.model_id.id,
            'default_campaign_id': self.utm_campaign_id.id,
            'default_use_in_marketing_automation': True,
            'default_mailing_type': 'mail',
            'default_state': 'done',
            # action
            'create': True,
        })
        return action

    def action_view_tracker_statistics(self):
        action = self.env["ir.actions.actions"]._for_xml_id("marketing_automation.link_tracker_action_marketing_campaign")
        action['domain'] = [('campaign_id', 'in', self.utm_campaign_id.ids)]
        return action

    # ------------------------------------------------------------
    # PARTICIPANTS SYNCHRONIZE / MANAGEMENT
    # ------------------------------------------------------------

    def action_add_participants_manually(self, model_name, record_ids):
        return self._add_participants_manually(self.env[model_name].browse(record_ids))

    def _add_participants_manually_from_partners(self, partner_ids):
        new_participants = self.env['marketing.participant']
        valid_campaigns = self.filtered_domain(self._get_campaign_cron_alive_domain())
        if not partner_ids or not valid_campaigns:
            return new_participants

        partner_domain = Domain('id', 'in', partner_ids)
        partner_campaigns = valid_campaigns.filtered_domain([('model_name', '=', 'res.partner')])
        new_participants += partner_campaigns._add_participants_manually(self.env['res.partner'].browse(partner_ids))
        for campaign in (valid_campaigns - partner_campaigns):
            Model = self.env[campaign.model_name]
            partner_fields = Model._mail_get_partner_fields(True)
            if partner_fields:
                records = Model.search(Domain.OR(
                    [Domain(field, 'any', partner_domain) for field in partner_fields]
                ))
                new_participants += campaign._add_participants_manually(records)
        return new_participants

    def _remove_participants_manually_from_partners(self, partner_ids):
        valid_campaigns = self.filtered_domain(self._get_campaign_cron_alive_domain())
        if not partner_ids or not valid_campaigns:
            return

        partner_domain = Domain('id', 'in', partner_ids)
        partner_campaigns = valid_campaigns.filtered_domain([('model_name', '=', 'res.partner')])
        if partner_campaigns:
            self.env['marketing.participant'].search([
                ('campaign_id', 'in', partner_campaigns.ids), ('res_id', 'in', partner_ids)
            ]).action_set_rejected()
        for campaign in (valid_campaigns - partner_campaigns):
            Model = self.env[campaign.model_name]
            partner_fields = Model._mail_get_partner_fields(True)
            if partner_fields:
                records = Model.search(Domain.OR(
                    [Domain(field, 'any', partner_domain) for field in partner_fields]
                ))
                self.env['marketing.participant'].search([
                    ('campaign_id', '=', campaign.id), ('res_id', 'in', records.ids)
                ]).action_set_rejected()

    def _add_participants_manually(self, records):
        """ Used to manually create new participants inside campaigns. Those
        records should match the campaign model and filtering domain. As number
        of records to subscribe should be low, no commit / progress mechanism
        is implemented. """
        if any(campaign.model_name != records._name for campaign in self):
            raise ValueError('Invalid participants model')

        new_participants = self.env['marketing.participant']
        participants = self.env['marketing.participant'].search([
            ("res_id", "in", records.ids),
            ("campaign_id", "in", self.ids),
            ("state", "=", "running"),
        ])
        campaign_participants = participants.grouped('campaign_id')

        valid_campaigns = self.filtered_domain(self._get_campaign_cron_alive_domain())
        for campaign in valid_campaigns:
            existing_ids = campaign_participants.get(campaign, self.env['marketing.participant']).mapped('res_id')
            to_create_records = (
                records
                if campaign.enroll_multiple and campaign.enroll_type != "domain"
                else records.filtered(lambda rec: rec.id not in existing_ids)
            )
            if not to_create_records:  # all participants already exist don't create new ones
                continue

            # TDE Note: duplicated code with cron, to cleanup later
            RecordModel = self.env[campaign.model_name].with_context(lang=(campaign.user_id or self.env.user).lang, prefetch_fields=False)
            to_create_rec_ids = to_create_records.ids
            unique_field_su = campaign.enroll_unique_field_id.sudo()
            # check for unicity field -> be defensive with model, as there is no DB constraint
            if unique_field_su.name != 'id' and unique_field_su.model_id == campaign.model_id:
                without_duplicates = []
                existing_records = RecordModel.browse(existing_ids).exists()
                # Split the read in batch of 1000 to avoid the prefetch
                # crawling the cache for the next 1000 records to fetch
                unique_field_vals = {rec[unique_field_su.name]
                                        for index in range(0, len(existing_records), 1000)
                                        for rec in existing_records[index:index + 1000]}

                for rec in RecordModel.browse(to_create_rec_ids):
                    field_val = rec[unique_field_su.name]
                    # we exclude the empty recordset with the first condition
                    if (not unique_field_su.relation or field_val) and field_val not in unique_field_vals:
                        without_duplicates.append(rec.id)
                        unique_field_vals.add(field_val)
                to_create_rec_ids = without_duplicates

            new_participants += campaign._create_participants(to_create_rec_ids, auto_commit=False)
        return new_participants

    def action_synchronize_participants(self):
        """ Calling participants update manually from form view """
        return self.filtered(lambda c: c.state == 'running')._synchronize_participants()

    @deprecated("Deprecated since 20.0, use `action_synchronize_participants`")
    def sync_participants(self):
        """ Kept for compatibility / server actions """
        return self._synchronize_participants()

    @api.model
    def _cron_synchronize_participants(self, batch_size=None):
        """ Cron call only. Loops over active (running) campaigns and tries to
        synchronize their participants (add new one matching enroll criterions,
        remove rejected or unlinked participants, see '_synchronize_participants'
        for more details). Purpose of this dedicated method is to use cron
        mechanisms to ease iteration-based job and lessen issues coming with
        heavy usage. """
        cron_domain = self._get_campaign_cron_alive_domain() & self._get_campaign_cron_synchronize_enroll_domain() & (
            # exclude recently failed campaigns
            Domain.OR([
                Domain('cron_enroll_failure_dt', '=', False),
                Domain('cron_enroll_failure_dt', '<=', self.env.cr.now() - relativedelta(hours=1))
            ])
        )
        running = self.search(cron_domain, limit=batch_size)
        self.env['ir.cron']._commit_progress(remaining=len(running))
        for campaign in running:
            try:
                campaign._synchronize_participants()
                campaign.write({
                    'cron_enroll_failure_dt': False,
                })
                # commit in try because it might also fail
                remaining = self.env['ir.cron']._commit_progress(processed=1)
            except Exception as e:  # noqa: BLE001
                self.env['ir.cron']._rollback_progress()
                _logger.warning('MarketingAutomation: cron failed synchronizing participants on campaign [%d] due to %r', campaign.id, e, exc_info=True)
                campaign.write({
                    'cron_enroll_failure_dt': self.env.cr.now(),
                })
                campaign._message_log(
                    body=_('Cron failed enrolling participants, received error %(error)s', error=repr(e)),
                    partner_ids=campaign.user_id.partner_id.ids if campaign.user_id.active else False,
                )
                # mark as processed as we handle errors manually; allows to log
                # progress, avoid immediate re-run or deactivation
                remaining = self.env['ir.cron']._commit_progress(processed=1)
            # break if not time remaining
            if not remaining:
                break

    def _synchronize_participants(self):
        """ Synchronize campaign participants, based on records in DB. New
        participants are created taking into account campaign filter and unique
        field. Note that traces for 'begin' activities are created when
        creating participants.

        If records have been unlinked since last synchronization, matching
        participants are set as removed.

        It also updates ``last_sync_date`` that is used to know if a new
        synchronization is necessary, based on activities 'require_sync'
        flag.

        This method is called by a cron mainly. It can be called manually on
        campaign form view.

        :return: new participants to the campaign
        """
        participants = self.env['marketing.participant']
        now = self.env.cr.now()

        for campaign in self.filtered_domain(self._get_campaign_cron_synchronize_enroll_domain()):
            if not campaign.last_sync_date:
                campaign.last_sync_date = now
            participants += campaign._synchronize_participants_domain()

        return participants

    def _synchronize_participants_domain(self):
        """ Domain-based participant synchronization. """
        self.ensure_one()
        # auto-commit except in testing mode
        auto_commit = not modules.module.current_test

        user_id = self.user_id or self.env.user
        RecordModel = self.env[self.model_name].with_context(lang=user_id.lang)

        # Fetch existing participants
        part_domain = Domain('campaign_id', '=', self.id)
        if self.enroll_type == 'anniversary':
            # previous iteration of anniversary should not impact enrolling
            part_domain &= Domain('anniversary_dt.year_number', '=', self.env.cr.now().year)
        campaign_participants = self.env['marketing.participant'].search_fetch(part_domain, ['res_id'])
        participants_res_ids = OrderedSet(campaign_participants.mapped('res_id'))
        existing_records = RecordModel.browse()

        record_domain = self._get_campaign_domain()
        db_rec_ids = OrderedSet(RecordModel.search(record_domain).ids)
        to_create_rec_ids = [rid for rid in db_rec_ids if rid not in participants_res_ids]  # keep ordered IDs
        to_remove_rec_ids = participants_res_ids - db_rec_ids
        unique_field_su = self.enroll_unique_field_id.sudo()
        # check for unicity field -> be defensive with model, as there is no DB constraint
        if unique_field_su.name != 'id' and unique_field_su.model_id == self.model_id:
            without_duplicates = []
            existing_records = RecordModel.with_context(prefetch_fields=False).browse(participants_res_ids).exists()
            # Split the read in batch of 1000 to avoid the prefetch
            # crawling the cache for the next 1000 records to fetch
            unique_field_vals = {rec[unique_field_su.name]
                                    for index in range(0, len(existing_records), 1000)
                                    for rec in existing_records[index:index + 1000]}

            for rec in RecordModel.with_context(prefetch_fields=False).browse(to_create_rec_ids):
                field_val = rec[unique_field_su.name]
                # we exclude the empty recordset with the first condition
                if (not unique_field_su.relation or field_val) and field_val not in unique_field_vals:
                    without_duplicates.append(rec.id)
                    unique_field_vals.add(field_val)
            to_create_rec_ids = without_duplicates

        additional_values = {}
        if self.enroll_type == 'anniversary':
            offset = {self.enroll_date_delay_type: (1 if self.enroll_date_delay_order == 'before' else -1) * self.enroll_date_delay_number}
            additional_values['anniversary_dt'] = self.env.cr.now() + relativedelta(**offset)  # used notably for multiple enroll
        participants = self._create_participants(
            to_create_rec_ids, auto_commit=auto_commit,
            additional_values=additional_values,
        )
        if to_remove_rec_ids:
            if not existing_records:  # don't do it twice if unique field
                existing_records = RecordModel.with_context(prefetch_fields=False).browse(participants_res_ids).exists()
            self._remove_participants(to_remove_rec_ids, existing_record_ids=existing_records.ids, auto_commit=auto_commit)

        return participants

    def _create_participants(self, record_ids, auto_commit=False, additional_values=None):
        self.ensure_one()
        additional_values = additional_values or {}
        now = self.env.cr.now()
        participants = self.env['marketing.participant']
        start_activities = self.marketing_activity_ids.filtered(lambda act: act.trigger_type == 'begin')
        start_dt = [
            now + relativedelta(**{activity.interval_type: activity.interval_number})
            for activity in start_activities
        ]

        # small model -> can create big batches (0 means no iteration -> to avoid)
        batch_size = self.env['ir.config_parameter'].sudo().get_int('marketing.trace.batch.size') or 500
        for to_create_batch in tools.split_every(batch_size, record_ids):
            participants += participants.create([{
                'campaign_id': self.id,
                'res_id': rec_id,
                'trace_ids': [
                    (0, 0, {
                        'activity_id': activity.id,
                        'schedule_date': schedule_date,
                    }) for activity, schedule_date in zip(start_activities, start_dt)
                ],
                **additional_values,
            } for rec_id in to_create_batch])

            if auto_commit:
                self.env.cr.commit()  # nosemgrep: commit-in-models

        if start_dt:
            # based on activities with 'begin' trigger_type, we schedule CRON triggers
            # that match the scheduled_dates of created marketing.traces
            cron = self.env.ref('marketing_automation.ir_cron_campaign_execute_activities')
            cron._trigger(start_dt)

        return participants

    def _remove_participants(self, record_ids, existing_record_ids=False, auto_commit=False):
        self.ensure_one()

        # be sure to not have 0, as otherwise no iteration is done
        batch_size = self.env['ir.config_parameter'].sudo().get_int('marketing.trace.batch.size') or 500
        participants_to_unlink = self.env['marketing.participant'].search([
            ('res_id', 'in', record_ids),
            ('campaign_id', '=', self.id),
            ('state', '!=', 'unlinked'),
        ])
        for index in range(0, len(participants_to_unlink), batch_size):
            batch = participants_to_unlink[index:index + batch_size]
            if filter_excluded := batch.filtered(lambda p: p.res_id in (existing_record_ids or [])):
                filter_excluded.action_set_rejected(trace_message=self.env._('Record no longer matches campaign filter'))
            if deleted := batch - filter_excluded:
                deleted.action_set_unlinked()
            # Commit every 10k record. It should be ok, it takes 1sec second to process 10k
            batch_count = round(10000 / batch_size) or 1
            if auto_commit and not index % (batch_size * batch_count):
                self.env.cr.commit()  # nosemgrep: commit-in-models

    def action_execute_activities(self):
        """ Launching activities execution manually from form view """
        return self.filtered(lambda c: c.state == 'running')._execute_activities()

    @deprecated("Deprecated since 20.0, use `action_execute_activities`")
    def execute_activities(self):
        """ Kept for compatibility for server actions """
        return self._execute_activities()

    @api.model
    def _cron_execute_activities(self, batch_size=None):
        """ Cron call only. Loops over active (running) campaigns and tries to
        execute activities with scheduled traces. Purpose of this dedicated
        method is to use cron mechanisms to ease iteration-based job and lessen
        issues coming with heavy usage. """
        cron_domain = self._get_campaign_cron_alive_domain() & (
            # exclude recently failed campaigns
            Domain.OR([
                Domain('cron_activities_failure_dt', '=', False),
                Domain('cron_activities_failure_dt', '<=', self.env.cr.now() - relativedelta(hours=1))
            ])
        )
        running = self.search(cron_domain, limit=batch_size)
        self.env['ir.cron']._commit_progress(remaining=len(running))
        for campaign in running:
            try:
                campaign._execute_activities()
                campaign.write({
                    'cron_activities_failure_dt': False,
                })
                # commit in try because it might also fail
                remaining = self.env['ir.cron']._commit_progress(processed=1)
            except Exception as e:  # noqa: BLE001
                self.env['ir.cron']._rollback_progress()
                _logger.warning('MarketingAutomation: cron failed processing activities on campaign [%d] due to %r', campaign.id, e, exc_info=True)
                campaign.write({
                    'cron_activities_failure_dt': self.env.cr.now(),
                })
                campaign._message_log(
                    body=_('Cron failed processing activities, received error %(error)s', error=repr(e)),
                    partner_ids=campaign.user_id.partner_id.ids if campaign.user_id.active else False,
                )
                remaining = self.env['ir.cron']._commit_progress(processed=1)
            # break if not time remaining
            if not remaining:
                break

    def _execute_activities(self):
        """ Execute activities by fetching all scheduled traces and execute them
        if their deadline is in the past. Called by cron or manually on campaign
        form view. """
        new_traces = self.env['marketing.trace']
        for campaign in self:
            new_traces += campaign.marketing_activity_ids.sorted('id').execute()
        return new_traces

    @api.model
    def _get_campaign_cron_alive_domain(self):
        """ Base domain definition for alive campaigns from cron POV. """
        return (
            Domain('active', '=', True) &
            Domain('state', '=', 'running') &
            Domain('marketing_activity_ids', '!=', False)
        )

    @api.model
    def _get_campaign_cron_synchronize_enroll_domain(self):
        return Domain('enroll_type', 'not in', ['action', 'on_demand', 'webhook'])

    def _get_campaign_domain(self):
        self.ensure_one()
        domain = Domain(literal_eval(self.enroll_domain or "[]"))
        if self.enroll_type in ["date", 'anniversary']:
            # delay: enroll after means date is before, hence *removing*
            offset = {self.enroll_date_delay_type: (1 if self.enroll_date_delay_order == 'before' else -1) * self.enroll_date_delay_number}
            reference_date = self.env.cr.now().today() + relativedelta(**offset)
            date = reference_date.timetuple().tm_yday if self.enroll_type == 'anniversary' else reference_date
            date_field = f"{self.enroll_date_field_id.name}{'.day_of_year' if self.enroll_type == 'anniversary' else ''}"
            domain &= Domain([(date_field, ">=", date), (date_field, "<", date + relativedelta(days=1))]) if self.enroll_type == 'date' else Domain(date_field, '=', date)
        return domain

    # ------------------------------------------------------------
    # Campaign Templates / Data
    # ------------------------------------------------------------

    def _prepare_res_partner_category_tag_hot_data(self):
        return {
            'xml_id': 'marketing_automation.res_partner_category_tag_hot',
            'values': {
                'name': _('Hot')
            }
        }

    def _prepare_mailing_list_contact_list_data(self):
        return {
            'xml_id': 'marketing_automation.mailing_list_contact_list',
            'values': {
                'name': _('Confirmed contacts'),
                'active': True,
                'is_public': True
            }
        }

    def _prepare_ir_actions_server_partner_tag_data(self):
        # Add the "Hot" category on partners who will click on a mail sent to them.
        self._create_records_with_xml_ids({'res.partner.category': [self._prepare_res_partner_category_tag_hot_data()]})
        hot_id = self.env.ref('marketing_automation.res_partner_category_tag_hot', raise_if_not_found=False).id
        return {
            'xml_id': 'marketing_automation.ir_actions_server_partner_tag',
            'values': {
                'name': _('Add Hot Category'),
                'model_id': self.env['ir.model']._get_id('res.partner'),
                'state': 'object_write',
                'update_field_id': self.env["ir.model.fields"]._get_ids('res.partner')['category_id'],
                'update_path': 'category_id',
                'evaluation_type': 'value',
                'resource_ref': f'res.partner.category,{hot_id}',
                'value': str(hot_id)
            }
        }

    def _prepare_ir_actions_server_partner_todo_data(self):
        # Assign activity to admin called Bounced: check email address.
        return {
            'xml_id': 'marketing_automation.ir_actions_server_partner_todo',
            'values': {
                'name': _('Next activity: Check Email Address'),
                'model_id': self.env['ir.model']._get_id('res.partner'),
                'state': 'next_activity',
                'activity_date_deadline_range': 2,
                'activity_date_deadline_range_type': 'days',
                'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                'activity_user_type': 'generic',
                'activity_user_field_name': 'user_id',
            }
        }

    def _prepare_ir_actions_server_contact_blacklist_data(self):
        # If mail bounces on some contact, blacklist that contact.
        return {
            'xml_id': 'marketing_automation.ir_actions_server_contact_blacklist',
            'values': {
                'name': _('Blacklist record'),
                'model_id': self.env['ir.model']._get_id('mailing.contact'),
                'state': 'code',
                'code':
"""
for record in records:
    record.env['mail.blacklist']._add(
    record.email,
    message='Added in blacklist from automated action',
    )
"""
            }
        }

    def _create_records_with_xml_ids(self, create_xmls):
        for model_name, values in create_xmls.items():
            for record in values:
                module, name = record['xml_id'].split('.')
                if not self.env.ref(f'{module}.{name}', raise_if_not_found=False):
                    created_record = self.env[model_name].sudo().create(record['values'])
                    self.env['ir.model.data'].sudo().create({
                        'name': name,
                        'module': module,
                        'model': model_name,
                        'res_id': created_record.id,
                        'noupdate': True,
                    })

    @api.model
    def get_action_marketing_campaign_from_template(self, template_str):
        if not self.env.su and not self.env.user.has_group('marketing_automation.group_marketing_automation_user'):
            raise AccessError(_('To use this feature you should be an administrator or belong to the marketing automation group.'))
        campaign_templates_info = self.get_campaign_templates_info()
        template = next(
            (template_value
            for group in campaign_templates_info.values()
            for template_key, template_value in group['templates'].items()
            if template_key == template_str),
            False)

        if not template:
            return False
        load_method = template.get('function')
        if not load_method:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'marketing.campaign',
                'views': [[False, 'form']]
            }

        if not load_method.startswith('_get_marketing_template') or not hasattr(self, load_method):
            return
        loaded_method = getattr(self, load_method)
        campaign = loaded_method()
        # Set the campaign_id of the mailings to the current campaign_id
        campaign.marketing_activity_ids.mass_mailing_id.campaign_id = campaign.utm_campaign_id
        campaign.action_sort_steps()

        return {
            'name': 'marketing_automation_templates_action',
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'res_id': campaign.id,
            'res_model': 'marketing.campaign',
            'views': [[False, 'form']]
        }

    @api.model
    def get_campaign_templates_info(self):
        return {
            'misc': {
                'label': _("Misc"),
                'templates': {
                    'hot_contacts': {
                        'title': _('Tag Hot Contacts'),
                        'description': _('Send a welcome email to contacts and tag them if they click in it.'),
                        'function': '_get_marketing_template_hot_contacts_values',
                    },
                    'commercial_prospection': {
                        'title': _('Commercial prospection'),
                        'description': _('Send a free catalog and follow-up according to reactions.'),
                        'function': '_get_marketing_template_commercial_prospection_values',
                    },
                },
            },
            'marketing': {
                'label': _("Marketing"),
                'templates': {
                    'welcome': {
                        'title': _('Welcome Flow'),
                        'description': _('Send a welcome email to new subscribers, remove the addresses that bounced.'),
                        'function': '_get_marketing_template_welcome_values',
                    },
                    'double_opt_in': {
                        'title': _('Double Opt-in'),
                        'description': _('Send an email to new recipients to confirm their consent.'),
                        'function': '_get_marketing_template_double_opt_in_values',
                    },
                }
            }
        }

    def _get_marketing_template_hot_contacts_values(self):
        convert.convert_file(
            self.sudo().env,
            'marketing_automation',
            'data/templates/mail_template_body_welcome_template.xml',
            idref={}, mode='init',
        )
        rendered_template = self.env['ir.qweb']._render(self.env.ref('marketing_automation.mail_template_body_welcome_template').id,
                        {'db_host': self.get_base_url(), 'company_website': self.env.company.website})
        prerequisites = {
            'mailing.mailing': [{
                'subject': _('Welcome!'),
                'body_arch': rendered_template,
                'body_html': rendered_template,
                'email_from': self.env.company.email_formatted,
                'mailing_model_id': self.env['ir.model']._get_id('res.partner'),
                'mailing_type': 'mail',
                'reply_to_mode': 'update',
                'state': 'done',
                'use_in_marketing_automation': True,
            }],
        }
        for model_name, values in prerequisites.items():
            records = self.env[model_name].create(values)
            for idx, record in enumerate(records):
                prerequisites[model_name][idx] = record

        self._create_records_with_xml_ids({
            'ir.actions.server': [self._prepare_ir_actions_server_partner_tag_data(),
                                  self._prepare_ir_actions_server_partner_todo_data()]
        })

        campaign = self.env['marketing.campaign'].create({
            'name': _('Tag Hot Contacts'),
            'enroll_domain': ["&", "&", ("email", "!=", False), ("is_blacklisted", "=", False), ("user_ids", "=", False)],
            'enroll_unique_field_id': self.env['ir.model.fields']._get('res.partner', 'email').id,
            'enroll_type': 'domain',
            'model_id': self.env['ir.model']._get_id('res.partner'),
        })
        self.env['marketing.activity'].create([
            {
                'trigger_type': 'begin',
                'activity_type': 'mail',
                'interval_type': 'hours',
                'mass_mailing_id': prerequisites['mailing.mailing'][0].id,
                'interval_number': 2,
                'name': _('Send Welcome Email'),
                'campaign_id': campaign.id,
                'child_ids': [
                    (0, 0, {
                        'trigger_type': 'mail_click',
                        'activity_type': 'action',
                        'interval_type': 'hours',
                        'interval_number': 2,
                        'name': _('Add Tag'),
                        'campaign_id': campaign.id,  # use the campaign_id here too,
                        'server_action_id': self.env.ref('marketing_automation.ir_actions_server_partner_tag').id,
                    }),
                    (0, 0, {
                        'trigger_type': 'mail_bounce',
                        'activity_type': 'action',
                        'interval_type': 'hours',
                        'interval_number': 2,
                        'name': _('Check Bounce Contact'),
                        'campaign_id': campaign.id,  # use the campaign_id here too,
                        'server_action_id': self.env.ref('marketing_automation.ir_actions_server_partner_todo').id
                    })
                ]
            }
        ])
        return campaign

    def _get_marketing_template_welcome_values(self):
        convert.convert_file(
            self.sudo().env,
            'marketing_automation',
            'data/templates/mail_template_body_yellow_discount_template.xml',
            idref={}, mode='init',
        )
        rendered_template = self.env['ir.qweb']._render(self.env.ref('marketing_automation.mail_template_body_yellow_discount_template').id,
                                                        {'db_host': self.get_base_url(), 'company_website': self.env.company.website})
        prerequisites = {
            'mailing.mailing': [{
                'subject': _('Get 10% OFF'),
                'body_arch': rendered_template,  # set Yellow 10% template
                'body_html': rendered_template,  # set Yellow 10% template
                'email_from': self.env.company.email_formatted,
                'mailing_model_id': self.env['ir.model']._get_id('mailing.contact'),
                'mailing_type': 'mail',
                'reply_to_mode': 'update',
                'state': 'done',
                'use_in_marketing_automation': True
            }],
        }
        for model_name, values in prerequisites.items():
            records = self.env[model_name].create(values)
            for idx, record in enumerate(records):
                prerequisites[model_name][idx] = record

        create_xmls = {
            'ir.actions.server': [
                self._prepare_ir_actions_server_contact_blacklist_data()
            ],
        }
        self._create_records_with_xml_ids(create_xmls)

        campaign = self.env['marketing.campaign'].create({
            'name': _('Welcome Flow'),
            'enroll_type': 'domain',
            'enroll_domain': ["&", ("email", "!=", False), ("is_blacklisted", "=", False)],
            'enroll_unique_field_id': self.env['ir.model.fields']._get('mailing.contact', 'email').id,
            'model_id': self.env['ir.model']._get_id('mailing.contact'),
        })

        self.env['marketing.activity'].create({
            'trigger_type': 'begin',
            'activity_type': 'mail',
            'interval_type': 'hours',
            'mass_mailing_id': prerequisites['mailing.mailing'][0].id,
            'interval_number': 2,
            'name': _('Send 10% Welcome Discount'),
            'campaign_id': campaign.id,
            'child_ids': [(0, 0, {
                'trigger_type': 'mail_bounce',
                'activity_type': 'action',
                'interval_type': 'hours',
                'interval_number': 2,
                'name': _('Blacklist Bounces'),
                'campaign_id': campaign.id,  # use the campaign_id here too,
                'server_action_id': self.env.ref('marketing_automation.ir_actions_server_contact_blacklist').id
            })]
        })
        return campaign

    def _get_marketing_template_double_opt_in_values(self):
        convert.convert_file(
            self.sudo().env,
            'marketing_automation',
            'data/templates/mail_template_body_confirmation_template.xml',
            idref={}, mode='init',
        )
        rendered_template = self.env['ir.qweb']._render(self.env.ref('marketing_automation.mail_template_body_confirmation_template').id,
                                                {'db_host': self.get_base_url()})
        prerequisites = {
            'mailing.mailing': [{
                'subject': _('Confirmation'),
                'body_arch': rendered_template,
                'body_html': rendered_template,
                'email_from': self.env.company.email_formatted,
                'mailing_model_id': self.env['ir.model']._get_id('mailing.contact'),
                'mailing_type': 'mail',
                'reply_to_mode': 'update',
                'state': 'done',
                'use_in_marketing_automation': True
            }],
        }
        for model_name, values in prerequisites.items():
            records = self.env[model_name].create(values)
            for idx, record in enumerate(records):
                prerequisites[model_name][idx] = record

        create_xmls = {
            'mailing.list': [self._prepare_mailing_list_contact_list_data()],
        }
        self._create_records_with_xml_ids(create_xmls)

        campaign = self.env['marketing.campaign'].create({
            'name': _('Double Opt-in'),
            'enroll_domain': ["&", "&", ("email", "!=", False), ("is_blacklisted", "=", False), ("list_ids", "ilike", "Newsletter")],
            'enroll_unique_field_id': self.env['ir.model.fields']._get('mailing.contact', 'email').id,
            'model_id': self.env['ir.model']._get_id('mailing.contact'),
        })
        self.env['marketing.activity'].create({
            'trigger_type': 'begin',
            'activity_type': 'mail',
            'interval_type': 'hours',
            'mass_mailing_id': prerequisites['mailing.mailing'][0].id,
            'interval_number': 0,
            'name': _('Confirmation'),
            'campaign_id': campaign.id,
            'child_ids': [(0, 0, {
                'trigger_type': 'mail_click',
                'activity_type': 'subscribe_to_list',
                'interval_type': 'hours',
                'interval_number': 0,
                'name': _('Add to list'),
                'campaign_id': campaign.id,  # use the campaign_id here too,
                'subscribe_to_list_action': 'add',
                'subscribe_to_list_id': self.env.ref('marketing_automation.mailing_list_contact_list').id,
            })]
        })
        return campaign

    def _get_marketing_template_commercial_prospection_values(self):
        convert.convert_file(
            self.sudo().env,
            'marketing_automation',
            'data/templates/mail_template_body_join_partnership_template.xml',
            idref={}, mode='init',
        )
        convert.convert_file(
            self.sudo().env,
            'marketing_automation',
            'data/templates/mail_template_body_free_trial_template.xml',
            idref={}, mode='init',
        )

        free_trial_rendered = self.env['ir.qweb']._render(self.env.ref('marketing_automation.mail_template_body_free_trial_template').id,
                                                          {'company_website': self.env.company.website})
        join_partnership_rendered = self.env['ir.qweb']._render(self.env.ref('marketing_automation.mail_template_body_join_partnership_template').id,
                                                            {'company_website': self.env.company.website})

        prerequisites = {
            'mailing.mailing': [{
                'subject': _('Welcome!'),
                'body_arch': free_trial_rendered,
                'body_html': free_trial_rendered,
                'email_from': self.env.company.email_formatted,
                'mailing_model_id': self.env['ir.model']._get_id('res.partner'),
                'mailing_type': 'mail',
                'reply_to_mode': 'update',
                'state': 'done',
                'use_in_marketing_automation': True
            }, {
                'subject': _('Join partnership!'),
                'body_arch': join_partnership_rendered,
                'body_html': join_partnership_rendered,
                'email_from': self.env.company.email_formatted,
                'mailing_model_id': self.env['ir.model']._get_id('res.partner'),
                'mailing_type': 'mail',
                'reply_to_mode': 'update',
                'state': 'done',
                'use_in_marketing_automation': True
            }],
        }
        for model_name, values in prerequisites.items():
            records = self.env[model_name].create(values)
            for idx, record in enumerate(records):
                prerequisites[model_name][idx] = record

        campaign = self.env['marketing.campaign'].create({
            'name': _('Commercial prospection'),
            'enroll_type': 'domain',
            'enroll_unique_field_id': self.env['ir.model.fields']._get('res.partner', 'email').id,
            'model_id': self.env['ir.model']._get_id('res.partner'),
        })
        self.env['marketing.activity'].create([{
            'trigger_type': 'begin',
            'activity_type': 'mail',
            'interval_type': 'hours',
            'mass_mailing_id': prerequisites['mailing.mailing'][0].id,
            'interval_number': 1,
            'name': _('Offer free catalog'),
            'campaign_id': campaign.id,
        }, {
            'trigger_type': 'begin',
            'activity_type': 'mail',
            'interval_type': 'days',
            'mass_mailing_id': prerequisites['mailing.mailing'][1].id,
            'interval_number': 7,
            'name': _('After 7 days'),
            'campaign_id': campaign.id,
            'child_ids': [(0, 0, {
                'trigger_type': 'mail_reply',
                'activity_type': 'log_note',
                'interval_type': 'hours',
                'log_note_body': "This contact is interested in becoming a partner.",
                'interval_number': 1,
                'name': _('Message for sales person'),
                'campaign_id': campaign.id,  # use the campaign_id here too,
            })]
        }])
        return campaign

    # ------------------------------------------------------------
    # Webhooks
    # ------------------------------------------------------------

    def _is_webhook_enabled(self):
        return self.filtered(self._get_campaign_cron_alive_domain() & Domain('enroll_type', '=', 'webhook'))

    def action_rotate_webhook_uuid(self):
        if not self.env.is_admin():
            raise AccessError(_('Non-admins are not allowed to rotate webhook UUIDs'))
        for webhook in self:
            webhook.webhook_uuid = str(uuid4())

    def action_view_webhook_logs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Webhook Logs'),
            'res_model': 'ir.logging',
            'view_mode': 'list,form',
            'domain': [('path', '=', "marketing.campaign(%s)" % self.id)],
        }

    def _prepare_logging_values(self, **values):
        self.ensure_one()
        defaults = {
            'dbname': self.env.cr.dbname,
            'func': '',
            'level': 'INFO',
            'line': '',
            'name': _('Webhook Log'),
            'path': 'marketing.campaign(%s)' % self.id,
            'type': 'server',
        }
        defaults.update(**values)
        return defaults

    def _process_webhook_payload(
            self, search_domain: DomainType,
            create_values: ValuesType | list[ValuesType],
            webhook_test: bool = False,
        ) -> MarketingParticipant:
        """ Execute the webhook for the given search_domain and create_values.
        search_domain is a domain (in string form) used to identify the record on which the automation should be run.
        create_values is a dict or array of dicts (in string form) used to create new records should the search_domain not find any.
        """
        self.ensure_one()
        if not self._is_webhook_enabled() and not (self.enroll_type == 'webhook' and webhook_test):
            raise ValidationError(_('Webhooks are not enabled for this campaign'))
        if not search_domain and not create_values:
            raise UserError(_('Either a search or create argument should be provided. Make sure you are sending properly formatted JSON.'))
        if create_values:
            sanitized_create_values = self._process_webhook_payload_check_create_values(create_values)
        else:
            sanitized_create_values = create_values
        ir_logging_sudo = self.env['ir.logging'].sudo()

        records = self.env[self.model_name].with_context(clean_context(self.env.context))
        # find
        if search_domain:
            try:
                records = records.search(Domain(search_domain))
            except Exception as e:  # noqa: BLE001
                msg = '%sCampaign Webhook #%s failed fetching records\n-> triggered with search_domain %s and create_values %s\n%s'
                msg_args = ('(TEST_MODE) ' if webhook_test else '', self.id, search_domain or 'None', create_values or 'None', traceback.format_exc())
                _logger.warning(msg, *msg_args, exc_info=True)
                if self.webhook_log_calls:
                    ir_logging_sudo.create(self._prepare_logging_values(message=msg % msg_args, level='ERROR'))
                raise UserError(_('Campaign Webhook failed fetching records')) from e
        # or create
        if not records and self.webhook_allow_create and sanitized_create_values:
            try:
                records = records.create(sanitized_create_values)
            except Exception as e:  # noqa: BLE001
                self.env.cr.rollback()  # always rollback - as we catch exceptions, records might stay in DB
                msg = '%sCampaign Webhook #%s failed creating records\n-> triggered with search_domain %s and create_values %s\n%s'
                msg_args = ('(TEST_MODE) ' if webhook_test else '', self.id, search_domain or 'None', create_values or 'None', traceback.format_exc())
                _logger.warning(msg, *msg_args, exc_info=True)
                if self.webhook_log_calls:
                    ir_logging_sudo.create(self._prepare_logging_values(message=msg % msg_args, level='ERROR'))
                raise UserError(_('Campaign Webhook failed creating records')) from e

        # info logging is done by the ir.http logger
        msg = '%sWebhook #%s triggered with search_domain %s and create_values %s. Records found or created: %s'
        msg_args = ('(TEST MODE) ' if webhook_test else '', self.id, search_domain, create_values, records.ids)
        _logger.debug(msg, *msg_args)
        if self.webhook_log_calls:
            ir_logging_sudo.create(self._prepare_logging_values(message=msg % msg_args))

        if not webhook_test:
            self._add_participants_manually(records)
        else:
            response_msg = _('Webhook test successful. ')
            if not self.marketing_activity_ids:
                response_msg += _('The campaign doesn\'t have related activities. ')
            # To prevent leaks, outside of draft mode, we do not send information about whether records have been found.
            if not records.exists() and self.state == 'draft':
                response_msg += _('No records were found or created.')
            elif self.state == 'draft':
                response_msg += _(
                    'Webhook resolved to resource IDs %(record_ids)s. Note that records created in webhook tests get deleted.'
                , record_ids=records.ids)
            # Raise to cancel record creation
            raise UserError(response_msg)

    def _process_webhook_payload_check_create_values(self, create_values: ValuesType | list[ValuesType]) -> list[ValuesType]:
        """ Sanitize / check given creation values before propagating to create.
        Do not modify, create new dictionaries in order to allow logging."""
        if not isinstance(create_values, (list, dict)) or (isinstance(create_values, list) and not all(isinstance(el, dict) for el in create_values)):
            raise UserError(_('Create argument is malformed: it should either be a dictionary of values, or a list of dictionaries'))
        sanitized = []
        for values in (create_values if isinstance(create_values, list) else [create_values]):
            propagated_fnames = []
            updated_vals = {}
            for fname in values:
                field = self.env[self.model_name]._fields.get(fname)
                if not field:  # managed by creation itself, will crash and log
                    propagated_fnames.append(fname)
                elif (
                    field.store and not field.groups and not field.related and
                    field.type not in ('properties', 'serialized', 'vector')
                ):
                    propagated_fnames.append(field.name)
                # cleanup if 2many fields are allowed to create sub records and keep only
                # link commands; otherwise just let it crash and log
                if (
                    field and field.type in ('one2many', 'many2many') and field.comodel_name in self.env and
                    self.env[field.comodel_name]._allow_sudo_commands
                ):
                    updated_vals[field.name] = [command for command in values[field.name] if command[0] in (4, 6)]
            sanitized.append({key: updated_vals.get(key, values[key]) for key in values if key in propagated_fnames})
        return sanitized
