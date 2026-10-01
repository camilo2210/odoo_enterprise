# Part of Odoo. See LICENSE file for full copyright and licensing details.

import ast
from collections import defaultdict
from dateutil.relativedelta import relativedelta
from lxml import html
from zoneinfo import ZoneInfo

from odoo import api, fields, models, tools, _
from odoo.fields import Command, Domain
from odoo.tools import html_sanitize, LazyTranslate, SQL
from odoo.addons.web.controllers.utils import clean_action
from odoo.exceptions import UserError

_lt = LazyTranslate(__name__)

TICKET_PRIORITY = [
    ('0', 'Low priority'),
    ('1', 'Medium priority'),
    ('2', 'High priority'),
    ('3', 'Urgent'),
]


class HelpdeskTicket(models.Model):
    _name = 'helpdesk.ticket'
    _description = 'Helpdesk Ticket'
    _order = 'priority desc, id desc'
    _mail_defaults_to_email = True
    _mail_thread_customer = True
    _primary_email = 'partner_email'
    _inherit = [
        'portal.mixin',
        'utm.mixin',
        'rating.mixin',
        'mail.activity.mixin',
        'mail.tracking.duration.mixin',
    ]
    _track_duration_field = 'stage_id'
    _priority_field = 'priority'

    @api.model
    def default_get(self, fields):
        result = super().default_get(fields)
        if result.get('team_id') and fields:
            team = self.env['helpdesk.team'].browse(result['team_id'])
            if 'stage_id' in fields and 'stage_id' not in result:  # if no stage given, deduce it from the team
                result['stage_id'] = team._determine_stage()[team.id].id
            if 'user_id' in fields and 'user_id' not in result and ('stage_id' in fields and not self.env['helpdesk.stage'].browse(result['stage_id']).fold):  # if no user given, deduce it from the team
                result['user_id'] = team._determine_user_to_assign({team: 1})[team.id][0]
        return result

    def _default_team_id(self):
        team_id = self.env['helpdesk.team'].search([('member_ids', 'in', self.env.uid)], limit=1).id
        if not team_id:
            team_id = self.env['helpdesk.team'].search([], limit=1).id
        return team_id

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        # write the domain
        # - ('id', 'in', stages.ids): add columns that should be present
        # - OR ('team_ids', '=', team_id) if team_id: add team columns
        search_domain = [('id', 'in', stages.ids)]
        if self.env.context.get('default_team_id'):
            search_domain = ['|', ('team_ids', 'in', self.env.context['default_team_id'])] + search_domain

        return stages.search(search_domain)

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, *, active_test=True, bypass_access=False):
        """ Override _search to have a more intuitive result when ordering by `ticket_ref`, which is a Char field. """
        if order and order.startswith('ticket_ref '):
            order = order.replace('ticket_ref ', 'id ', 1)
        return super()._search(domain, offset, limit, order, active_test=active_test, bypass_access=bypass_access)

    name = fields.Char(string='Subject', required=True, index=True, tracking=True)
    team_id = fields.Many2one('helpdesk.team', string='Helpdesk Team',
        default=lambda self: self._default_team_id(), index=True, tracking=True)
    use_sla = fields.Boolean(related='team_id.use_sla')
    team_privacy_visibility = fields.Selection(related='team_id.privacy_visibility', export_string_translation=False)
    description = fields.Html(sanitize_attributes=False)
    active = fields.Boolean(default=True)
    tag_ids = fields.Many2many('helpdesk.tag', string='Tags')
    company_id = fields.Many2one(related='team_id.company_id', string='Company', store=True, readonly=True)
    color = fields.Integer(string='Color Index')
    kanban_state = fields.Selection([
        ('normal', 'In progress'),
        ('done', 'Ready'),
        ('blocked', 'Blocked')], string='Kanban State',
        copy=False, default='normal', required=True)
    kanban_state_label = fields.Char(compute='_compute_kanban_state_label', string='Kanban State Label', tracking=True)
    legend_blocked = fields.Char(related='stage_id.legend_blocked', string='Kanban Blocked Explanation', readonly=True, related_sudo=False)
    legend_done = fields.Char(related='stage_id.legend_done', string='Kanban Valid Explanation', readonly=True, related_sudo=False)
    legend_normal = fields.Char(related='stage_id.legend_normal', string='Kanban Ongoing Explanation', readonly=True, related_sudo=False)
    domain_user_ids = fields.Many2many('res.users', compute='_compute_domain_user_ids', export_string_translation=False)
    user_id = fields.Many2one(
        'res.users', string='Assigned to', compute='_compute_user_and_stage_ids', store=True,
        readonly=False, tracking=True,
        domain=lambda self: [('all_group_ids', 'in', self.env.ref('helpdesk.group_helpdesk_user').id)],
        falsy_value_label=_lt("👤 Unassigned"))
    properties = fields.Properties(
        'Properties', definition='team_id.ticket_properties',
        copy=True)
    partner_id = fields.Many2one('res.partner', string='Customer', domain="[ '|', ('company_id', '=', False), ('company_id', '=', company_id) ]", tracking=True, index=True)
    partner_ticket_ids = fields.Many2many('helpdesk.ticket', compute='_compute_partner_ticket_count', string="Partner Tickets")
    partner_ticket_count = fields.Integer('Number of other tickets from the same partner', compute='_compute_partner_ticket_count')
    partner_open_ticket_count = fields.Integer('Number of other open tickets from the same partner', compute='_compute_partner_ticket_count')
    # Used to submit tickets from a contact form
    partner_name = fields.Char(string='Customer Name', compute='_compute_partner_name', store=True, readonly=False)
    partner_email = fields.Char(string='Customer Email', compute='_compute_partner_email', inverse="_inverse_partner_email", store=True, readonly=False)
    partner_phone = fields.Char(string='Customer Phone', compute='_compute_partner_phone', inverse="_inverse_partner_phone", store=True, readonly=False)
    commercial_partner_id = fields.Many2one(related="partner_id.commercial_partner_id")
    closed_by_partner = fields.Boolean('Closed by Partner', readonly=True)
    priority = fields.Selection(TICKET_PRIORITY, string='Priority', default='0', tracking=True)
    stage_id = fields.Many2one(
        'helpdesk.stage', string='Stage', compute='_compute_user_and_stage_ids', store=True,
        readonly=False, ondelete='restrict', tracking=1, group_expand='_read_group_stage_ids',
        copy=False, index=True, domain="[('team_ids', '=', team_id)]")
    fold = fields.Boolean(related="stage_id.fold", export_string_translation=False)
    date_last_stage_update = fields.Datetime("Last Stage Update", copy=False, readonly=True)
    ticket_ref = fields.Char(string='Ticket IDs Sequence', copy=False, readonly=True, index=True)
    # next 4 fields are computed in write (or create)
    assign_date = fields.Datetime("First assignment date")
    assign_hours = fields.Float("Time to first assignment (hours)", compute='_compute_assign_hours', store=True, aggregator="avg")
    close_date = fields.Datetime("Close date", copy=False)
    close_hours = fields.Float("Time to close (hours)", compute='_compute_close_hours', store=True, aggregator="avg")
    open_hours = fields.Integer("Open Time (hours)", compute='_compute_open_hours', search='_search_open_hours', aggregator="avg")
    # SLA relative
    sla_ids = fields.Many2many('helpdesk.sla', 'helpdesk_sla_status', 'ticket_id', 'sla_id', string="SLAs", copy=False)
    sla_status_ids = fields.One2many('helpdesk.sla.status', 'ticket_id', string="SLA Status")
    sla_reached_late = fields.Boolean("Has SLA reached late", compute='_compute_sla_reached_late', compute_sudo=True, store=True)
    sla_reached = fields.Boolean("Has SLA reached", compute='_compute_sla_reached', compute_sudo=True, store=True)
    sla_deadline = fields.Datetime("SLA Deadline", compute='_compute_sla_deadline', compute_sudo=True, store=True, falsy_value_label=_lt("Deadline reached"))
    sla_deadline_hours = fields.Float("Working Hours until SLA Deadline", compute='_compute_sla_deadline', compute_sudo=True, store=True, aggregator="avg")
    sla_fail = fields.Boolean("Failed SLA Policy", compute='_compute_sla_fail', search='_search_sla_fail')
    sla_success = fields.Boolean("Success SLA Policy", compute='_compute_sla_success', search='_search_sla_success')

    use_credit_notes = fields.Boolean(related='team_id.use_credit_notes', export_string_translation=False)
    use_coupons = fields.Boolean(related='team_id.use_coupons', string='Use Coupons')
    use_giftcards = fields.Boolean(related='team_id.use_giftcards', string='Use Gift Cards')
    use_product_returns = fields.Boolean(related='team_id.use_product_returns', export_string_translation=False)
    use_product_replacements = fields.Boolean(related='team_id.use_product_replacements', export_string_translation=False)
    use_product_repairs = fields.Boolean(related='team_id.use_product_repairs', export_string_translation=False)

    is_partner_email_update = fields.Boolean(compute='_compute_is_partner_email_update', export_string_translation=False)
    is_partner_phone_update = fields.Boolean(compute='_compute_is_partner_phone_update', export_string_translation=False)

    first_response_hours = fields.Float("Hours to First Response", aggregator="avg", copy=False)
    avg_response_hours = fields.Float("Average Hours to Respond", aggregator="avg", copy=False)
    oldest_unanswered_customer_message_date = fields.Datetime("Oldest Unanswered Customer Message Date", export_string_translation=False)
    answered_customer_message_count = fields.Integer('# Exchanges', aggregator="avg")
    total_response_hours = fields.Float("Total Exchange Time in Hours", aggregator="avg", copy=False)
    display_extra_info = fields.Boolean(compute="_compute_display_extra_info", export_string_translation=False)
    unanswered = fields.Boolean(compute="_compute_unanswered", search='_search_unanswered', export_string_translation=False,
        groups="helpdesk.group_helpdesk_user")
    duration_stage_tracking = fields.Json(compute="_compute_duration_stage_tracking")

    @api.depends('stage_id')
    def _compute_duration_tracking(self):
        tickets = self.filtered(lambda t: t.team_id.resource_calendar_id)
        for ticket in tickets:
            tracking = dict(ticket.duration_tracking or {})
            ticket._get_stage_duration(tracking)
            tracking['s'] = ticket['stage_id'].id
            tracking['d'] = self.env.cr.now()
            ticket.duration_tracking = tracking

        super(HelpdeskTicket, self - tickets)._compute_duration_tracking()

    @api.depends('duration_tracking')
    def _compute_duration_stage_tracking(self):
        for ticket in self:
            if ticket.team_id.resource_calendar_id:
                tracking = dict(ticket.duration_tracking or {})
                ticket.duration_stage_tracking = ticket._get_stage_duration(tracking)
            else:
                ticket.duration_stage_tracking = []

    def _get_stage_duration(self, tracking):
        self.ensure_one()
        now = self.env.cr.now()
        if tracking.get('s') and tracking.get('d'):
            start_dt = fields.Datetime.from_string(tracking.get('d'))
            if start_dt < now:
                stage_id = str(tracking.get('s'))
                total_minutes = round(self.team_id.resource_calendar_id.get_work_hours_count(start_dt, now) * 60, 2)
                tracking[stage_id] = tracking.get(stage_id, 0) + total_minutes
        return tracking

    @api.depends('stage_id', 'kanban_state')
    def _compute_kanban_state_label(self):
        for ticket in self:
            if ticket.kanban_state == 'normal':
                ticket.kanban_state_label = ticket.legend_normal
            elif ticket.kanban_state == 'blocked':
                ticket.kanban_state_label = ticket.legend_blocked
            else:
                ticket.kanban_state_label = ticket.legend_done

    @api.depends('stage_id', 'partner_id', 'message_ids')
    def _compute_unanswered(self):
        for ticket in self:
            if ticket.stage_id.fold:
                ticket.unanswered = False
                continue

            last_message = next(
                (message for message in ticket.message_ids if message.author_id),
                self.env['mail.message']
            )

            if last_message:
                author_partner = last_message.author_id
                if author_partner.partner_share or author_partner == ticket.partner_id:
                    ticket.unanswered = True
                else:
                    ticket.unanswered = False
            else:
                ticket.unanswered = False

    @api.depends('team_id')
    def _compute_domain_user_ids(self):
        user_ids = self.env.ref('helpdesk.group_helpdesk_user').all_user_ids.ids
        for ticket in self:
            ticket_user_ids = []
            ticket_sudo = ticket.sudo()
            if ticket_sudo.team_id and ticket_sudo.team_id.privacy_visibility == 'invited_internal':
                ticket_user_ids = ticket_sudo.team_id.message_partner_ids.user_ids.ids
            ticket.domain_user_ids = [Command.set(user_ids + ticket_user_ids)]

    def _compute_access_url(self):
        super()._compute_access_url()
        for ticket in self:
            ticket.access_url = '/my/ticket/%s' % ticket.id

    @api.depends('sla_status_ids.deadline', 'sla_status_ids.reached_datetime')
    def _compute_sla_reached_late(self):
        """ Required to do it in SQL since we need to compare 2 columns value """
        mapping = {}
        if self.ids:
            self.env.cr.execute("""
                SELECT ticket_id, COUNT(id) AS reached_late_count
                FROM helpdesk_sla_status
                WHERE ticket_id IN %s AND (deadline < reached_datetime OR (deadline < %s AND reached_datetime IS NULL))
                GROUP BY ticket_id
            """, (tuple(self.ids), fields.Datetime.now()))
            mapping = dict(self.env.cr.fetchall())

        for ticket in self:
            ticket.sla_reached_late = mapping.get(ticket.id, 0) > 0

    @api.depends('sla_status_ids.deadline', 'sla_status_ids.reached_datetime')
    def _compute_sla_reached(self):
        sla_status_read_group = self.env['helpdesk.sla.status']._read_group(
            [('reached_datetime', '!=', False), ('ticket_id', 'in', self.ids)],
            ['ticket_id'],
        )
        sla_status_ids_per_ticket = {ticket.id for [ticket] in sla_status_read_group}
        for ticket in self:
            ticket.sla_reached = ticket.id in sla_status_ids_per_ticket

    @api.depends('sla_status_ids.deadline', 'sla_status_ids.reached_datetime')
    def _compute_sla_deadline(self):
        """ Keep the deadline for the last stage (closed one), so a closed ticket can have a status failed.
            Note: a ticket in a closed stage will probably have no deadline
        """
        now = fields.Datetime.now()
        for ticket in self:

            # the current team is invalid, no need to compute new values since the transaction will be rolled back anyway.
            if not (ticket.team_id and ticket.team_id.use_sla):
                continue
            min_deadline = False
            for status in ticket.sla_status_ids:
                if status.reached_datetime or not status.deadline:
                    continue
                if not min_deadline or status.deadline < min_deadline:
                    min_deadline = status.deadline

            ticket.update({
                'sla_deadline': min_deadline,
                'sla_deadline_hours': ticket.team_id.resource_calendar_id.get_work_duration_data\
                    (now, min_deadline, compute_leaves=True)['hours'] if min_deadline else 0.0,
            })

    @api.depends('sla_deadline', 'sla_reached_late')
    def _compute_sla_fail(self):
        now = fields.Datetime.now()
        for ticket in self:
            if ticket.sla_deadline:
                ticket.sla_fail = (ticket.sla_deadline < now) or ticket.sla_reached_late
            else:
                ticket.sla_fail = ticket.sla_reached_late

    @api.depends('partner_email', 'partner_id')
    def _compute_is_partner_email_update(self):
        for ticket in self:
            ticket.is_partner_email_update = ticket._get_partner_email_update()

    @api.depends('partner_phone', 'partner_id')
    def _compute_is_partner_phone_update(self):
        for ticket in self:
            ticket.is_partner_phone_update = ticket._get_partner_phone_update()

    @api.model
    def _search_sla_fail(self, operator, value):
        if operator != 'in':
            return NotImplemented
        datetime_now = fields.Datetime.now()
        return ['|', ('sla_reached_late', '=', True), ('sla_deadline', '<', datetime_now)]

    @api.depends('sla_deadline', 'sla_reached', 'sla_reached_late')
    def _compute_sla_success(self):
        now = fields.Datetime.now()
        for ticket in self:
            ticket.sla_success = (ticket.sla_reached and not ticket.sla_reached_late and (not ticket.sla_deadline or ticket.sla_deadline > now))

    @api.model
    def _search_sla_success(self, operator, value):
        if operator != 'in':
            return NotImplemented
        datetime_now = fields.Datetime.now()
        return [('sla_reached', '=', True), ('sla_reached_late', '=', False), '|', ('sla_deadline', '=', False), ('sla_deadline', '>', datetime_now)]

    @api.depends('team_id')
    def _compute_user_and_stage_ids(self):
        for ticket in self.filtered(lambda ticket: ticket.team_id):
            if not ticket.user_id:
                ticket.user_id = ticket.team_id._determine_user_to_assign({ticket.team_id: 1})[ticket.team_id.id][0]
            if not ticket.stage_id or ticket.stage_id not in ticket.team_id.stage_ids:
                ticket.stage_id = ticket.team_id._determine_stage()[ticket.team_id.id]

    @api.depends('partner_id')
    def _compute_partner_name(self):
        self.fetch(['partner_id'])
        for ticket in self:
            if ticket.partner_id:
                ticket.partner_name = ticket.partner_id.name

    @api.depends('partner_id.email')
    def _compute_partner_email(self):
        self.fetch(['partner_id'])
        for ticket in self:
            if ticket.partner_id:
                ticket.partner_email = ticket.partner_id.email

    def _inverse_partner_email(self):
        for ticket in self:
            if self.env.context.get('helpdesk_partner_sync', True) and ticket._get_partner_email_update():
                ticket.partner_id.email = ticket.partner_email

    @api.depends('partner_id.phone')
    def _compute_partner_phone(self):
        self.fetch(['partner_id'])
        for ticket in self:
            if ticket.partner_id:
                ticket.partner_phone = ticket.partner_id.phone

    def _inverse_partner_phone(self):
        for ticket in self:
            if self.env.context.get('helpdesk_partner_sync', True) and (ticket._get_partner_phone_update() or not ticket.partner_id.phone) and ticket.partner_phone:
                ticket.partner_id.phone = ticket.partner_phone

    @api.depends('partner_id', 'partner_email', 'partner_phone')
    def _compute_partner_ticket_count(self):
        for ticket in self:
            partner_tickets = self.search_fetch([("partner_id", "child_of", ticket.partner_id.commercial_partner_id.id)], ['fold']) if ticket.partner_id else ticket
            ticket.partner_ticket_ids = partner_tickets
            partner_tickets = partner_tickets - ticket._origin
            ticket.partner_ticket_count = len(partner_tickets) if partner_tickets else 0
            open_ticket = partner_tickets.filtered(lambda ticket: not ticket.fold)
            ticket.partner_open_ticket_count = len(open_ticket)

    @api.depends('assign_date')
    def _compute_assign_hours(self):
        for ticket in self:
            create_date = fields.Datetime.from_string(ticket.create_date)
            if create_date and ticket.assign_date and ticket.team_id.resource_calendar_id:
                tz = ticket.team_id.company_id.tz or 'UTC'
                duration_data = ticket.team_id.resource_calendar_id.get_work_duration_data(
                    create_date.astimezone(ZoneInfo(tz)),
                    fields.Datetime.from_string(ticket.assign_date).astimezone(ZoneInfo(tz)),
                    compute_leaves=True,
                )
                ticket.assign_hours = duration_data['hours']
            else:
                ticket.assign_hours = False

    @api.depends('close_date')
    def _compute_close_hours(self):
        stage_map = {
            team.id: team.stage_ids.filtered(lambda s: not s.fold).ids
            for team in self.team_id
        }
        for ticket in self:
            if ticket.close_date:
                tracking = ticket.duration_stage_tracking or {}
                stage_ids = stage_map.get(ticket.team_id.id, [])
                total_minutes = sum(
                    minutes
                    for key, minutes in tracking.items()
                    if key.isdigit()
                    and int(key) in stage_ids)
                ticket.close_hours = total_minutes / 60
            else:
                ticket.close_hours = False

    @api.depends('close_hours')
    def _compute_open_hours(self):
        for ticket in self:
            if ticket.create_date:  # fix from https://github.com/odoo/enterprise/commit/928fbd1a16e9837190e9c172fa50828fae2a44f7
                if ticket.close_date:
                    time_difference = ticket.close_date - fields.Datetime.from_string(ticket.create_date)
                else:
                    time_difference = fields.Datetime.now() - fields.Datetime.from_string(ticket.create_date)
                ticket.open_hours = (time_difference.seconds) / 3600 + time_difference.days * 24
            else:
                ticket.open_hours = 0

    def _compute_display_extra_info(self):
        self.display_extra_info = self.env.user.has_group('base.group_multi_company')

    @api.model
    def _search_open_hours(self, operator, value):
        if operator == 'in':
            return Domain.OR(self._search_open_hours('=', v) for v in value)
        if operator == 'not in':
            return Domain.AND(self._search_open_hours('!=', v) for v in value)

        dt = fields.Datetime.now() - relativedelta(hours=value)
        domain_closed = Domain('close_hours', operator, value)
        if operator in ['<', '<=', '>', '>=']:
            domain_unclosed = ~Domain('create_date', operator, dt)
        elif operator in ['=', '!=']:
            dt = dt.replace(minute=0, second=0, microsecond=0)
            domain_unclosed = (
                Domain('create_date', '>=', dt)
                & Domain('create_date', '<', dt + relativedelta(hours=1))
            )
            if operator == '!=':
                domain_unclosed = ~domain_unclosed
        else:
            return NotImplemented
        return (
            (Domain('close_date', '=', False) & domain_unclosed)
            | (Domain('close_date', '!=', False) & domain_closed)
        )

    @api.model
    def _search_unanswered(self, operator, value):
        if operator != 'in' and not isinstance(value, bool):
            return NotImplemented
        query = SQL("""
            SELECT t.id AS id
              FROM helpdesk_ticket t
              JOIN helpdesk_stage s ON s.id = t.stage_id
              JOIN LATERAL (
                   SELECT m2.id,
                          m2.author_id,
                          m2.message_type
                     FROM mail_message m2
                    WHERE m2.model = 'helpdesk.ticket'
                      AND m2.res_id = t.id
                      AND m2.author_id IS NOT NULL
                    ORDER BY m2.id DESC
                    LIMIT 1
              ) m ON TRUE
              WHERE (m.author_id = t.partner_id or m.message_type = 'auto_comment')
                AND s.fold IS NOT TRUE
        """)
        return [('id', 'in' if value else 'not in', query)]

    def _get_rotting_depends_fields(self):
        return super()._get_rotting_depends_fields() + ['close_date', 'kanban_state']

    def _get_rotting_domain(self):
        return super()._get_rotting_domain() & Domain('close_date', '=', False)

    def _get_partner_email_update(self):
        self.ensure_one()
        if self.partner_id.email and self.partner_email and self.partner_email != self.partner_id.email:
            ticket_email_normalized = tools.email_normalize(self.partner_email) or self.partner_email or False
            partner_emails_normalized = tools.email_normalize_all(self.partner_id.email) or self.partner_id.email or False
            return ticket_email_normalized not in partner_emails_normalized
        return False

    def _get_partner_phone_update(self):
        self.ensure_one()
        if self.partner_id.phone and self.partner_phone and self.partner_phone != self.partner_id.phone:
            ticket_phone_formatted = self.partner_phone or False
            partner_phone_formatted = self.partner_id.phone or False
            return ticket_phone_formatted != partner_phone_formatted
        return False

    def action_customer_preview(self):
        self.ensure_one()
        if self.team_privacy_visibility != 'portal' or not self.partner_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'danger',
                    'message': _('At this time, there is no preview available to show. The current ticket cannot be accessed by the customer, as it belongs to a helpdesk team that is not publicly available, or there is no customer associated with the ticket.'),
                }
            }
        return {
            'type': 'ir.actions.act_url',
            'url': self.get_portal_url(),
            'target': 'self',
        }

    def _get_access_action(self, access_uid=None, force_website=False):
        self.ensure_one()
        user = self.env['res.users'].sudo().browse(access_uid) if access_uid else self.env.user
        if user and not user.share and self.with_user(user).has_access('read') and not force_website:
            if self.team_id:
                return {
                    'type': 'ir.actions.act_url',
                    'url': f'/odoo/helpdesk/{self.team_id.id}/tickets/{self.id}',
                    'target': 'self',
                }
            return {
                "type": "ir.actions.act_url",
                "url": f'/odoo/all-tickets/{int(self.id)}',
                "target": "self",
            }
        return super()._get_access_action(access_uid, force_website)

    # ------------------------------------------------------------
    # ORM overrides
    # ------------------------------------------------------------

    @api.depends('ticket_ref', 'partner_name')
    @api.depends_context('with_partner')
    def _compute_display_name(self):
        display_partner_name = self.env.context.get('with_partner', False)
        ticket_with_name = self.filtered('name')
        for ticket in ticket_with_name:
            name = ticket.name
            if ticket.ticket_ref:
                name += f' (#{ticket.ticket_ref})'
            if display_partner_name and ticket.partner_name:
                name += f' - {ticket.partner_name}'
            ticket.display_name = name
        return super(HelpdeskTicket, self - ticket_with_name)._compute_display_name()

    @api.model
    def get_empty_list_help(self, help_message):
        self = self.with_context(
            empty_list_help_id=self.env.context.get('default_team_id'),
            empty_list_help_model='helpdesk.team',
            empty_list_help_document_name=_("tickets"),
        )
        return super().get_empty_list_help(help_message)

    def create_action(self, action_ref, title, search_view_ref):
        action = self.env["ir.actions.actions"]._for_xml_id(action_ref)
        action = clean_action(action, self.env)
        if title:
            action['display_name'] = title
        if search_view_ref:
            action['search_view_id'] = self.env.ref(search_view_ref).read()[0]
        if 'views' not in action:
            action['views'] = [(False, view) for view in action['view_mode'].split(",")]
        return action

    @api.model
    def _assign_vals_by_tags(self, vals_list):
        """
        Automatically assign unassigned tickets based on added tags.

        Given a list of tuples containing the associated team and tags, this method
        updates each tuple's ``vals_dict`` with the ``user_id`` of the user to assign
        the ticket to. This is a side effect, and the modified dictionaries are
        intended to be used later in a create/write method.

        :param list[tuple] vals_list: A list of tuples with the structure
            ``(helpdesk_team, tag_ids, vals_dict)``. Each tuple contains:

            - ``helpdesk_team``: The ``helpdesk.team`` record for the ticket.
            - ``tag_ids``: A list of IDs corresponding to the ``helpdesk.tag`` objects
              being added to the ticket.
            - ``vals_dict``: A dictionary of values intended for later use in create/write
              operations. This dictionary **will be modified in place**.

        :returns: None
        :rtype: None
        """
        if not vals_list:
            return
        domain = Domain.OR([('team_id', '=', team_id), ('tag_id', 'in', tag_ids)] for team_id, tag_ids, _dummy in vals_list)
        tag_assignment_res = self.env['helpdesk.tag.assignment'].sudo()._read_group(
            domain,
            ['team_id', 'tag_id', 'user_ids'],
        )
        # Dict of all the users that could be assigned from a tag in a team
        users_per_team_and_tag = defaultdict(set)
        all_possible_users_ids = set()
        for team, tag, user in tag_assignment_res:
            users_per_team_and_tag[(team.id, tag.id)].add(user.id)
            all_possible_users_ids.add(user.id)
        all_possible_users = self.env['res.users'].browse(all_possible_users_ids)
        all_team_ids = {vals[0] for vals in vals_list}
        users_per_working_days = all_possible_users._get_working_users_per_first_working_day()

        # Used to keep track of how many open tickets users have in each team
        tickets_per_user_per_team = defaultdict(dict)
        for team, _dummy, user in tag_assignment_res:
            tickets_per_user_per_team[team.id][user.id] = 0
        # Add the open tickets to the previously created dict
        ticket_count_data = self.env['helpdesk.ticket']._read_group(
            [('stage_id.fold', '=', False), ('user_id', 'in', all_possible_users.ids), ('team_id', 'in', list(all_team_ids))],
            ['user_id', 'team_id'],
            ['__count'],
        )
        for user, team, open_tickets in ticket_count_data:
            tickets_per_user_per_team[team.id][user.id] = open_tickets

        for team_id, tag_ids, vals in vals_list:
            # get all users matching at least one of the tags...
            possible_user_ids = {
                user_id
                for tag_id in tag_ids
                for user_id in users_per_team_and_tag.get((team_id, tag_id), [])
            }
            if possible_user_ids:
                for user_ids in users_per_working_days:
                    # ...restrict them to the earliest available users ...
                    if available_user_ids := set(user_ids) & possible_user_ids:
                        # ... and select the one with the fewest open tickets
                        count_per_user = filter(lambda item: item[0] in available_user_ids, tickets_per_user_per_team[team_id].items())
                        chosen_user_id = min(count_per_user, key=lambda count: count[1])[0]
                        vals['user_id'] = chosen_user_id
                        tickets_per_user_per_team[team_id][chosen_user_id] += 1
                        break

    @api.model_create_multi
    def create(self, vals_list):
        self = self.browse()  # noqa: PLW0642
        now = fields.Datetime.now()

        # Determine user_id if not given for teams with automatic assignment. We have two cases:
        #   - If the assignment method is 'randomly' or 'balanced', we determine the next users to assign for each team.
        #   - If the assignment method is 'tags', it's a bit more complex as it depends on the added tags for each individual ticket.
        #       In that case, we directly modify the vals, as it's simpler than computing the user ids then map them to the vals they originate from.
        team_ids = { vals['team_id'] for vals in vals_list if vals.get('team_id') }
        tickets_to_assign_by_tags = []
        teams = self.env['helpdesk.team'].browse(team_ids)

        # determine stage_id if not given. Done in batch.
        default_stage_per_team_id = teams._determine_stage()

        # Determine assignees if auto assignement is enabled
        # In case of assignment by tags, we add the user_ids to the values below. For the other methods, they are added later
        team_per_team_id = dict(zip(team_ids, teams))
        ticket_amount_per_team = defaultdict(int)
        for vals in vals_list:
            if not (team_id := vals.get('team_id')):
                continue
            stage = self.env['helpdesk.stage'].browse(vals['stage_id']) if 'stage_id' in vals else default_stage_per_team_id[team_id]
            team = team_per_team_id[team_id]
            if stage.fold or vals.get('user_id') or not team.auto_assignment:
                continue
            if team.assign_method == 'tags':
                if tag_ids := vals.get('tag_ids'):
                    tag_ids = self._fields['tag_ids'].convert_to_cache(tag_ids, self)
                    tickets_to_assign_by_tags.append((team.id, tag_ids, vals))
            else:
                ticket_amount_per_team[team] += 1

        self._assign_vals_by_tags(tickets_to_assign_by_tags)
        assignees_per_team_id = self.env['helpdesk.team']._determine_user_to_assign(ticket_amount_per_team)

        # Manually create a partner now since '_generate_template_recipients' doesn't keep the name. This is
        # to avoid intrusive changes in the 'mail' module
        # TDE TODO: to extract and clean in mail thread
        for vals in vals_list:
            partner_id = vals.get('partner_id', False)
            partner_name = vals.get('partner_name', False)
            partner_email = vals.get('partner_email', False)
            if partner_email and not partner_id:
                company_id = self.env['helpdesk.team'].browse(vals['team_id']).company_id.id if vals.get('team_id') else False
                suggested_name = tools.parse_contact_from_email(partner_name)[0] or tools.parse_contact_from_email(partner_email)[0]
                vals['partner_id'] = self.env['mail.thread']._partner_find_from_emails_single(
                    [partner_email], additional_values={tools.mail.email_normalize(partner_email) or partner_email: {'name': suggested_name, 'company_id': company_id}},
                    filter_found=lambda partner: not partner.company_id or partner.company_id.id == company_id,
                ).id

        # determine partner email for ticket with partner but no email given
        partners = self.env['res.partner'].browse([vals['partner_id'] for vals in vals_list if 'partner_id' in vals and vals.get('partner_id') and 'partner_email' not in vals])
        partner_email_map = {partner.id: partner.email for partner in partners}
        partner_name_map = {partner.id: partner.name for partner in partners}
        company_per_team_id = {t.id: t.company_id for t in teams}
        for vals in vals_list:
            company = company_per_team_id.get(vals.get('team_id', False))
            vals['ticket_ref'] = self.env['ir.sequence'].with_company(company).sudo().next_by_code('helpdesk.ticket')
            if team_id := vals.get('team_id'):
                if 'stage_id' not in vals:
                    vals['stage_id'] = default_stage_per_team_id[team_id].id
                if self.env['helpdesk.stage'].browse(vals['stage_id']).fold:
                    vals['close_date'] = now
                if 'user_id' not in vals and team_id in assignees_per_team_id:
                    vals['user_id'] = assignees_per_team_id[team_id].pop()
                if vals.get('user_id'):  # if a user is finally assigned, force ticket assign_date and reset assign_hours
                    vals['assign_date'] = fields.Datetime.now()
                    vals['assign_hours'] = 0

            # set partner email if in map of not given
            if vals.get('partner_id') in partner_email_map:
                vals['partner_email'] = partner_email_map.get(vals['partner_id'])
            # set partner name if in map of not given
            if vals.get('partner_id') in partner_name_map:
                vals['partner_name'] = partner_name_map.get(vals['partner_id'])

            if vals.get('stage_id'):
                vals['date_last_stage_update'] = now
            vals['oldest_unanswered_customer_message_date'] = now

        # context: no_log, because subtype already handle this
        tickets = super().create(vals_list)

        # make customer follower
        for ticket in tickets:
            if ticket.partner_id:
                ticket.message_subscribe(ticket.partner_id.ids)

            ticket._portal_ensure_token()

        # apply SLA
        tickets.sudo()._sla_apply()

        return tickets

    def write(self, vals):
        # we set the assignation date (assign_date) to now for tickets that are being assigned for the first time
        # same thing for the closing date
        assigned_tickets = closed_tickets = self.browse()
        if vals.get('user_id'):
            assigned_tickets = self.filtered(lambda ticket: not ticket.assign_date)

        if vals.get('stage_id'):
            if self.env['helpdesk.stage'].browse(vals.get('stage_id')).fold:
                closed_tickets = self.filtered(lambda ticket: not ticket.close_date)
            else:  # auto reset the 'closed_by_partner' flag
                vals['closed_by_partner'] = False
                vals['close_date'] = False

        now = fields.Datetime.now()

        # update last stage date when changing stage
        if 'stage_id' in vals:
            vals['date_last_stage_update'] = now
            if 'kanban_state' not in vals:
                vals['kanban_state'] = 'normal'

        if 'kanban_state' in vals:
            vals['date_last_stage_update'] = now

        old_tag_ids_per_ticket_id = {}
        if 'tag_ids' in vals:
            old_tag_ids_per_ticket_id = {t.id: set(t.tag_ids.ids) for t in self}

        res = super(HelpdeskTicket, self - assigned_tickets - closed_tickets).write(vals)
        res &= super(HelpdeskTicket, assigned_tickets - closed_tickets).write(dict(vals, **{
            'assign_date': now,
        }))
        res &= super(HelpdeskTicket, closed_tickets - assigned_tickets).write(dict(vals, **{
            'close_date': now,
            'oldest_unanswered_customer_message_date': False,
        }))
        res &= super(HelpdeskTicket, assigned_tickets & closed_tickets).write(dict(vals, **{
            'assign_date': now,
            'close_date': now,
        }))

        if vals.get('partner_id'):
            self.message_subscribe([vals['partner_id']])

        # SLA business
        if not (len(vals.keys()) == 1 and 'sla_ids' in vals):  # avoid applying SLA twice (after writing sla_ids in case of stage change for example)
            self.sudo()._sla_apply(keep_reached=True)
        if 'stage_id' in vals:
            self.sudo()._sla_reach(vals['stage_id'])
            self.filtered(lambda ticket: ticket.stage_id.rating_active)._send_ticket_rating_mail(force_send=True)

        if stage_fold := ('stage_id' in vals and self.env['helpdesk.stage'].browse(vals['stage_id']).fold):
            odoobot_partner_id = self.env['ir.model.data']._xmlid_to_res_id('base.partner_root')
            for ticket in self:
                exceeded_hours = ticket.sla_status_ids.mapped('exceeded_hours')
                if exceeded_hours:
                    min_hours = min([hours for hours in exceeded_hours if hours > 0], default=min(exceeded_hours))
                    message = _("This ticket was successfully closed %s hours before its SLA deadline.", round(abs(min_hours))) if min_hours < 0 \
                        else _("This ticket was closed %s hours after its SLA deadline.", round(min_hours))
                    ticket.message_post(body=message, subtype_xmlid="mail.mt_note", author_id=odoobot_partner_id)
        elif old_tag_ids_per_ticket_id:
            unassigned_tickets_to_assign = self.filtered(
                lambda t: not t.user_id
                    and t.team_id.auto_assignment
                    and t.team_id.assign_method == 'tags'
                    and not t.stage_id.fold
            )
            if unassigned_tickets_to_assign:
                vals_list = [
                    (ticket.team_id.id, list(added_tags), {})
                    for ticket in unassigned_tickets_to_assign
                    if (added_tags := set(ticket.tag_ids.ids) - old_tag_ids_per_ticket_id[ticket.id])
                ]
                if vals_list:
                    self._assign_vals_by_tags(vals_list)
                    for ticket, vals_dict in zip(unassigned_tickets_to_assign, list(zip(*vals_list))[2]):
                        if vals_dict:
                            ticket.write(vals_dict)
        return res

    def copy_data(self, default=None):
        vals_list = super().copy_data(default=default)
        has_default_user = default and 'user_id' in default
        active_users = self.env['res.users']
        if not has_default_user:
            active_users = self.user_id.filtered('active')
        for ticket, vals in zip(self, vals_list):
            if not has_default_user and ticket.user_id and ticket.user_id not in active_users:
                vals['user_id'] = False
        return vals_list

    def _unsubscribe_portal_users(self):
        self.message_unsubscribe(partner_ids=self.message_partner_ids.filtered('user_ids.share').ids)

    def website_form_input_filter(self, request, values):
        if 'partner_id' in values:
            values.pop('partner_name', None)
            values.pop('partner_email', None)
        return values

    # ------------------------------------------------------------
    # Actions and Business methods
    # ------------------------------------------------------------

    def _sla_apply(self, keep_reached=False):
        """ Apply SLA to current tickets: erase the current SLAs, then find and link the new SLAs to each ticket.
            Note: transferring ticket to a team "not using SLA" (but with SLAs defined), SLA status of the ticket will be
            erased but nothing will be recreated.
            :returns recordset of new helpdesk.sla.status applied on current tickets
        """
        # get SLA to apply
        sla_per_tickets = self._sla_find()

        if keep_reached:
            sla_status_to_remove = self.env['helpdesk.sla.status']
            sla_status_value_list = []
            for ticket, slas in sla_per_tickets.items():
                status_to_keep_per_sla = {}
                for status in ticket.sla_status_ids.sorted('id'):
                    current_status_to_keep = status_to_keep_per_sla.get(status.sla_id.id)
                    if not current_status_to_keep:
                        status_to_keep_per_sla[status.sla_id.id] = status
                        continue
                    # Keep reached statuses in priority to preserve reached date information.
                    if status.reached_datetime and not current_status_to_keep.reached_datetime:
                        sla_status_to_remove |= current_status_to_keep
                        status_to_keep_per_sla[status.sla_id.id] = status
                    else:
                        sla_status_to_remove |= status

                kept_statuses = self.env['helpdesk.sla.status'].browse([status.id for status in status_to_keep_per_sla.values()])
                # Keep reached statuses even if the SLA no longer applies, but remove obsolete unreached ones.
                sla_status_to_remove |= kept_statuses.filtered(
                    lambda status: not status.reached_datetime and status.sla_id not in slas
                )

                missing_slas = slas - (kept_statuses - sla_status_to_remove).sla_id
                if missing_slas:
                    sla_status_value_list += ticket._sla_generate_status_values(missing_slas, keep_reached=False)

            sla_status_to_remove.unlink()
            return self.env['helpdesk.sla.status'].create(sla_status_value_list)

        # generate values of new sla status
        sla_status_value_list = []
        for tickets, slas in sla_per_tickets.items():
            sla_status_value_list += tickets._sla_generate_status_values(slas, keep_reached=keep_reached)

        sla_status_to_remove = self.mapped('sla_status_ids')
        if keep_reached:  # keep only the reached one to avoid losing reached_date info
            sla_status_to_remove = sla_status_to_remove.filtered(lambda status: not status.reached_datetime)

        # unlink status and create the new ones in 2 operations
        sla_status_to_remove.unlink()
        return self.env['helpdesk.sla.status'].create(sla_status_value_list)

    def _sla_find_domain(self):
        """
        Get domain to find matching SLAs.
        This function aims to be inherited by submodules
        :return: domain
        :rtype : list [tuple]
        """
        return Domain.AND([
            Domain('team_id', '=', self.team_id.id),
            Domain('stage_id.sequence', '>=', self.stage_id.sequence),
        ])

    def _sla_find(self):
        """ Find the SLA to apply on the current tickets
            :returns a map with the tickets linked to the SLA to apply on them
            :rtype : dict {<helpdesk.ticket>: <helpdesk.sla>}
        """
        result = {}
        for ticket in self:
            if ticket.team_id.use_sla:
                slas = self.env['helpdesk.sla'].search(ticket._sla_find_domain())
                result[ticket] = self.env['helpdesk.sla']
                for sla in slas:
                    if not sla.criteria_domain or ticket in sla.search_tickets():
                        result[ticket] |= sla
        return result

    def _sla_generate_status_values(self, slas, keep_reached=False):
        """ Return the list of values for given SLA to be applied on current ticket """
        exclude_slas_per_ticket = {}
        # generate the map of status to keep by ticket only if requested
        if keep_reached:
            exclude_slas_per_ticket = dict(self.env['helpdesk.sla.status']._read_group(
                domain=[('reached_datetime', '!=', False), ('ticket_id', 'in', self.ids)],
                groupby=['ticket_id'],
                aggregates=['sla_id:recordset'],
            ))
        result = []
        for ticket in self:
            exclude_slas = exclude_slas_per_ticket.get(ticket, self.env['helpdesk.sla'])
            for sla in slas - exclude_slas:
                result.append({
                    'ticket_id': ticket.id,
                    'sla_id': sla.id,
                    'reached_datetime': fields.Datetime.now() if ticket.stage_id == sla.stage_id else False  # in case of SLA on first stage
               })
        return result

    def _sla_reach(self, stage_id):
        """ Flag the SLA status of current ticket for the given stage_id as reached, and even the unreached SLA applied
            on stage having a sequence lower than the given one.
        """
        stage = self.env['helpdesk.stage'].browse(stage_id)
        stages = self.env['helpdesk.stage'].search([('sequence', '<=', stage.sequence), ('team_ids', 'in', self.mapped('team_id').ids)])  # take previous stages
        sla_status = self.env['helpdesk.sla.status'].search([('ticket_id', 'in', self.ids)])
        sla_not_reached = sla_status.filtered(lambda sla: not sla.reached_datetime and sla.sla_stage_id in stages)
        sla_not_reached.write({'reached_datetime': fields.Datetime.now()})
        (sla_status - sla_not_reached).filtered(lambda x: x.sla_stage_id not in stages).write({'reached_datetime': False})

    def action_open_helpdesk_ticket(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("helpdesk.helpdesk_ticket_action_main_tree")
        action.update({
            'domain': [('id', '!=', self.id), ('id', 'in', self.partner_ticket_ids.ids)],
            'context': {
                **ast.literal_eval(action.get('context', {})),
                'create': False,
            },
        })
        return action

    def action_open_ratings(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('helpdesk.rating_rating_action_helpdesk')
        if self.rating_count == 1:
            action.update({
                'view_mode': 'form',
                'res_id': self.rating_ids[0].id,
                'views': [(view_id, view_type) for view_id, view_type in action['views'] if view_type == 'form'],
            })
        return action

    # ------------------------------------------------------------
    # Messaging API
    # ------------------------------------------------------------

    def _get_customer_information(self):
        email_keys_to_values = super()._get_customer_information()

        for ticket in self:
            email_key = tools.email_normalize(ticket.partner_email) or ticket.partner_email
            # do not fill Falsy with random data, unless monorecord (= always correct)
            if not email_key and len(self) > 1:
                continue
            email_keys_to_values.setdefault(email_key, {}).update({
                'company_id': ticket.company_id.id,
                'name': ticket.partner_name or tools.parse_contact_from_email(ticket.partner_email)[0] or ticket.partner_email,
                'phone': ticket.partner_phone,
            })
        return email_keys_to_values

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        values = dict(custom_values or {}, partner_email=msg_dict.get('from'), partner_name=msg_dict.get('from'), partner_id=msg_dict.get('author_id'))
        partner = self.env['res.partner'].browse(values.get('partner_id'))
        team = self.env['helpdesk.team'].browse(values.get('team_id'))
        if team and partner.company_id and partner.company_id != team.company_id:
            values.pop('partner_id')
        ticket = super(HelpdeskTicket, self.with_context(mail_notify_author=True)).message_new(msg_dict, custom_values=values)
        partner_ids = ticket._partner_find_from_emails_single(tools.email_split((msg_dict.get('to') or '') + ',' + (msg_dict.get('cc') or ''))).ids
        customer_ids = ticket._partner_find_from_emails_single(tools.email_split(values['partner_email'])).ids
        partner_ids += customer_ids
        if customer_ids and not values.get('partner_id'):
            ticket.partner_id = customer_ids[0]
        if partner_ids:
            ticket.message_subscribe(partner_ids)
        return ticket

    def message_update(self, msg_dict, update_vals=None):
        for ticket in self:
            if partners := ticket._partner_find_from_emails_single(tools.email_split((msg_dict.get('to') or '') + ',' + (msg_dict.get('cc') or '')), no_create=True):
                self.message_subscribe(partners.ids)
        return super().message_update(msg_dict, update_vals=update_vals)

    def _message_compute_subject(self):
        """ Override the display name by the actual name field for communication."""
        self.ensure_one()
        return self.name

    def _message_post_after_hook(self, message):
        if not self.partner_email:
            return super()._message_post_after_hook(message)

        if self.partner_id and not self.partner_id.email:
            self.partner_id.email = self.partner_email

        if not self.partner_id:
            # we consider that posting a message with a specified recipient (not a follower, a specific one)
            # on a document without customer means that it was created through the chatter using
            # suggested recipients. This heuristic allows to avoid ugly hacks in JS.
            email_normalized = tools.email_normalize(self.partner_email)
            new_partner = message.partner_ids.filtered(
                lambda partner: partner.email == self.partner_email or (email_normalized and partner.email_normalized == email_normalized)
            )
            if new_partner:
                if new_partner[0].email_normalized:
                    email_domain = ('partner_email', 'in', [new_partner[0].email, new_partner[0].email_normalized])
                else:
                    email_domain = ('partner_email', '=', new_partner[0].email)
                self.search([
                    ('partner_id', '=', False), email_domain,
                ]).write({'partner_id': new_partner[0].id})
        # use the sanitized body of the email from the message thread to populate the ticket's description
        if (
            not self.description
            and message.subtype_id == self._creation_subtype()
            and message.message_type == 'email'
            and tools.email_normalize(self.partner_email) == tools.email_normalize(message.email_from)
            and message.body  # TDE FIXME: use html empty
        ):
            # Remove the signature from the email body
            source_html = message.body
            doc = html.fromstring(source_html)

            signature_xpath = (
                '//*[@data-o-mail-quote="1"] | '
                '//span[normalize-space(.) = "--"]'
            )

            for element in doc.xpath(signature_xpath):
                element.getparent().remove(element)

            cleaned_html = html.tostring(doc, encoding='unicode').strip()
            self.description = html_sanitize(cleaned_html)

        return super()._message_post_after_hook(message)

    def _track_template_parameters(self, tracked_fields):
        res = super()._track_template_parameters(tracked_fields)
        ticket = self[0]
        if 'stage_id' in tracked_fields and ticket.stage_id.template_id and ticket.partner_email:
            res['stage_id'] = (ticket.stage_id.template_id, {
                'auto_delete_keep_log': False,
                'subtype_id': self.env['ir.model.data']._xmlid_to_res_id('mail.mt_note'),
            }
        )
        return res

    def _creation_subtype(self):
        return self.env.ref('helpdesk.mt_ticket_new')

    def _track_log_get_default_subtype(self, track_init_values):
        self.ensure_one()
        if 'stage_id' in track_init_values:
            return self.env.ref('helpdesk.mt_ticket_stage')
        return super()._track_log_get_default_subtype(track_init_values)

    def _notify_get_reply_to(self, default=None, author_id=False):
        """ Override to set alias of tickets to their team if any. """
        aliases = self.mapped('team_id').sudo()._notify_get_reply_to(default=default, author_id=author_id)
        res = {ticket.id: aliases.get(ticket.team_id.id) for ticket in self}
        leftover = self.filtered(lambda rec: not rec.team_id)
        if leftover:
            res.update(super(HelpdeskTicket, leftover)._notify_get_reply_to(default=default, author_id=author_id))
        return res

    # ------------------------------------------------------------
    # Rating Mixin
    # ------------------------------------------------------------

    def _rating_apply_get_default_subtype_id(self):
        return self.env['ir.model.data']._xmlid_to_res_id("helpdesk.mt_ticket_rated")

    def _rating_get_parent_field_name(self):
        return 'team_id'

    def _send_ticket_rating_mail(self, force_send=False):
        current_partner = self.env.user.partner_id
        for ticket in self:
            partner = ticket.partner_id
            if partner and ticket.stage_id.rating_template_id and partner != current_partner:
                ticket.rating_send_request(
                    ticket.stage_id.rating_template_id,
                    lang=partner.lang,
                    force_send=force_send,
                )

    # ---------------------------------------------------
    # Mail gateway
    # ---------------------------------------------------

    def _mail_get_message_subtypes(self):
        res = super()._mail_get_message_subtypes()
        if len(self) == 1 and self.team_id:
            team = self.team_id
            optional_subtypes = [('use_credit_notes', self.env.ref('helpdesk.mt_ticket_refund_status')),
                                 ('use_product_returns', self.env.ref('helpdesk.mt_ticket_return_status')),
                                 ('use_product_replacements', self.env.ref('helpdesk.mt_ticket_delivery_status')),
                                 ('use_product_repairs', self.env.ref('helpdesk.mt_ticket_repair_status'))]
            for field, subtype in optional_subtypes:
                if not team[field] and subtype in res:
                    res -= subtype
        return res

    @api.constrains('company_id', 'partner_id')
    def _check_partner_id_has_the_same_company(self):
        for ticket in self:
            if ticket.partner_id.company_id and ticket.partner_id.company_id != ticket.company_id:
                raise UserError(_("The customer cannot belong to a different company than the ticket."))
