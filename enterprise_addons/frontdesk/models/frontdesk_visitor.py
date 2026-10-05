# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta, UTC, datetime

from markupsafe import Markup

from odoo import models, fields, api, SUPERUSER_ID


class FrontdeskVisitor(models.Model):
    _name = 'frontdesk.visitor'
    _description = 'Frontdesk Visitor'
    _inherit = ['mail.thread', 'hr.mixin']
    _order = 'check_in'

    def _get_default_station(self):
        """Assign station by default if only one exists"""
        stations = self.env['frontdesk.frontdesk'].search([], limit=2)
        return stations.id if len(stations) == 1 else False

    active = fields.Boolean(default=True)
    name = fields.Char('Name', required=True)
    phone = fields.Char('Phone')
    email = fields.Char('Email')
    company = fields.Char('Visitor Company')
    station_host_ids = fields.Many2many('hr.employee', related='station_id.host_ids')
    host_id = fields.Many2one('hr.employee', string='Host Name', check_company=True)
    check_in = fields.Datetime(string='Check In', default=fields.Datetime.now)
    check_out = fields.Datetime(string='Check Out')
    duration = fields.Float('Duration', compute="_compute_duration", store=True, default=1.0)
    state = fields.Selection(string='Status',
        selection=[('checked_in', 'Checked-In'),
                   ('checked_out', 'Checked-Out')
        ],
        default='checked_in', tracking=True
    )
    auto_checkout_time = fields.Datetime('Auto-Checkout Time', compute="_compute_auto_checkout_time")
    station_id = fields.Many2one('frontdesk.frontdesk', required=True, index=True, default=_get_default_station)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        checked_in = res.filtered(lambda v: v.state == 'checked_in')
        checked_in._plan_auto_checkout()
        checked_in._notify()
        res._check_and_notify_visitor()
        return res

    def write(self, vals):
        if vals.get('state') == 'checked_in':
            vals['check_in'] = fields.Datetime.now()
            self._notify()
        elif vals.get('state') == 'checked_out':
            vals['check_out'] = fields.Datetime.now()
        res = super().write(vals)
        if vals.get('state') == 'checked_in':
            self._plan_auto_checkout(once_per_frontdesk=False)
        return res

    @api.depends('check_in', 'check_out')
    def _compute_duration(self):
        for visitor in self:
            if visitor.check_in and visitor.check_out:
                visitor.duration = (visitor.check_out - visitor.check_in).total_seconds() / 3600

    @api.depends('station_id.auto_checkout_hours', 'check_in')
    def _compute_auto_checkout_time(self):
        for record in self:
            if record.check_in and record.station_id.auto_checkout_hours:
                record.auto_checkout_time = record.check_in + timedelta(hours=record.station_id.auto_checkout_hours)
            else:
                record.auto_checkout_time = False

    def _cron_auto_checkout(self):
        self.env["frontdesk.visitor"].search([("state", "=", "checked_in")]).filtered(
            lambda visitor: (
                visitor.auto_checkout_time and visitor.auto_checkout_time <= datetime.now()
            )).state = 'checked_out'

    def action_check_out(self):
        self.state = 'checked_out'

    def _plan_auto_checkout(self, once_per_frontdesk=True):
        planned_frontdesks = []
        for record in self:
            if (not once_per_frontdesk or record.station_id.id not in planned_frontdesks) and record.auto_checkout_time:
                self.env.ref('frontdesk.cron_auto_checkout_visitors')._trigger(at=record.auto_checkout_time)
                planned_frontdesks.append(record.station_id.id)

    def _notify(self):
        """ Send a notification to the frontdesk's responsible users and the visitor's hosts when the visitor checks in. """
        for visitor in self:
            msg = ""
            visitor_name = visitor.name
            visitor_name += f" ({visitor.phone})" if visitor.phone else ""
            visitor_name += f" ({visitor.company})" if visitor.company else ""
            station = visitor.station_id
            host = visitor.host_id
            if station.responsible_ids:
                if visitor.host_id:
                    msg = self.env._("%(station)s Check-In: %(visitor)s to meet %(host)s", station=station.name, visitor=visitor_name, host=host.name)
                else:
                    msg = self.env._("%(station)s Check-In: %(visitor)s", station=station.name, visitor=visitor_name)
                visitor._notify_by_discuss(station.responsible_ids, msg)
            if station.host_selection and host:
                notified_by_discuss = False
                if station.notify_discuss and host.user_id:
                    msg = self.env._("%s just checked-in.", visitor_name)
                    visitor._notify_by_discuss([host], msg, True)
                    notified_by_discuss = True
                if station.notify_email or (station.mail_template_id and host.work_email and not notified_by_discuss):
                    visitor._notify_by_email()

    def _notify_by_discuss(self, recipients, msg, is_host=False):
        for recipient in recipients:
            if is_host and (not recipient.user_id or not recipient.user_id.partner_id):
                continue
            odoobot_id = self.env.ref("base.partner_root").id
            partners_to = [recipient.user_partner_id.id] if is_host else [recipient.partner_id.id]
            channel = self.env["discuss.channel"].with_user(SUPERUSER_ID)._get_or_create_chat(partners_to)
            channel.message_post(body=msg, author_id=odoobot_id, message_type="comment", subtype_xmlid="mail.mt_comment")

    def _notify_by_email(self):
        host = self.host_id
        if host.work_email:
            odoobot = self.env.ref('base.partner_root')
            mail_template = self.station_id.mail_template_id
            ctx = {'host_name': host.name, 'lang': host.user_partner_id.lang}
            body = mail_template.with_context(ctx)._render_field('body_html', self.ids, compute_lang=True)[self.id]
            subject = mail_template.with_context(ctx)._render_field('subject', self.ids, compute_lang=True)[self.id]
            self.message_post(
                email_from=odoobot.email_formatted,
                author_id=self.env.user.partner_id.id,
                body=body,
                subject=subject,
                partner_ids=host.work_contact_id.ids,
                message_type='email',
                subtype_xmlid='mail.mt_comment',
                email_layout_xmlid='mail.mail_notification_light',
                force_send=True,
            )

    def _get_host_name(self):
        return self.host_id.name or ""

    def _check_resources_leave(self, resources, check_in):
        if not resources or not check_in:
            return []
        start = check_in.replace(tzinfo=UTC)
        stop = start + timedelta(minutes=1)
        calendar = self.env.company.resource_calendar_id
        resources_per_tz = resources._get_resources_per_tz()
        leaves = calendar._leave_intervals_batch(start, stop, resources_per_tz=resources_per_tz)
        resource_on_leave = [resource.id for resource in resources if leaves[resource.id]._items]
        return resource_on_leave

    def _prepare_unavailability_body(self, hosts_on_leave):
        self.ensure_one()
        return Markup(
            """<div>
                <p>%(greeting)s</p>
                <p>%(message)s</p>
                <ul>
                    %(host_details)s
                </ul>
                <p>%(footer_contact)s</p>
                <p>%(footer)s</p>
            </div>"""
        ) % {
            "greeting": self.env._("Dear %(visitor_name)s,", visitor_name=self.name),
            "message": self.env._(
                "We regret to inform you that the following %(host_status)s currently unavailable:",
                host_status=self.env._('host is') if len(hosts_on_leave) == 1 else self.env._('hosts are')
            ),
            "host_details": Markup().join(
                Markup("<li><strong>%(host_name)s</strong>%(manager_info)s</li>") % {
                    "host_name": host.name,
                    "manager_info": self.env._(' - Manager: %(manager_name)s', manager_name=host.parent_id.name)
                    if host.parent_id else ''
                }
                for host in hosts_on_leave
            ),
            "footer_contact": self.env._(
                "You can contact the host's manager or frontdesk responsible for further assistance."
            ),
            "footer": self.env._("Thanks for your understanding.")
        }

    def _check_and_notify_visitor(self):
        for visitor in self:
            host = visitor.host_id
            if not (host and visitor.email and visitor.station_id.ask_email):
                continue
            if self._check_resources_leave(host.resource_id, visitor.check_in):
                body = visitor._prepare_unavailability_body(host)
                visitor.message_post(
                    body=body,
                    subject=self.env._("Your host isn't available"),
                    author_id=visitor.station_id.company_id.partner_id.id,
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment"
                )
