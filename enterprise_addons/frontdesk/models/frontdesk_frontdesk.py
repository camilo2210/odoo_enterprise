# Part of Odoo. See LICENSE file for full copyright and licensing details.

import uuid

from datetime import datetime

from odoo import models, fields, api, tools, _
from odoo.exceptions import ValidationError
from odoo.tools import single_email_re
from odoo.tools.urls import urljoin as url_join


class FrontdeskFrontdesk(models.Model):
    _name = 'frontdesk.frontdesk'
    _description = 'Frontdesk'
    _inherit = ['mail.thread', 'hr.mixin']
    _order = 'is_favorite desc'

    name = fields.Char('Frontdesk Name', required=True)
    responsible_ids = fields.Many2many(
        'res.users',
        string='Responsibles',
        required=True, help="Responsibles are notified if no host is selected."
    )
    host_ids = fields.Many2many('hr.employee', string='Hosts', check_company=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    theme = fields.Selection(selection=[("light", "Light"), ("dark", "Dark")], default='light')
    image = fields.Image("Image", help="This image will be used as the kiosk background.")
    host_selection = fields.Boolean(
        'Host Selection',
        groups='frontdesk.frontdesk_group_user',
        help="Restrict the hosts available from the client to choose from."
    )
    authenticate_guest = fields.Boolean('Guest Details', default=True, groups='frontdesk.frontdesk_group_user')
    ask_phone = fields.Boolean(string='Phone', default=True)
    ask_company = fields.Boolean(string='Organization', default=False)
    ask_email = fields.Boolean(string='Email', default=False)
    notify_email = fields.Boolean('Notify by email', groups='frontdesk.frontdesk_group_user')
    mail_template_id = fields.Many2one(
        'mail.template',
        string='Email Template',
        domain="[('model', '=', 'frontdesk.visitor')]",
        default=lambda self: self.env.ref('frontdesk.frontdesk_visitor_mail_template', raise_if_not_found=False),
        ondelete='restrict',
    )
    self_check_in = fields.Boolean('Self Check-In', groups='frontdesk.frontdesk_group_user',
        help='Shows a QR code in the interface, for guests to check in from their mobile phone.'
    )
    auto_checkout_hours = fields.Float(string="Auto-Checkout")
    notify_discuss = fields.Boolean('Notify by discuss', default=True, groups='frontdesk.frontdesk_group_user')
    description = fields.Html(groups='frontdesk.frontdesk_group_user')
    visitor_ids = fields.One2many('frontdesk.visitor', 'station_id', string='Visitors')
    guest_on_site = fields.Integer('Guests On Site', compute='_compute_dashboard_data')
    latest_check_in = fields.Char(compute='_compute_dashboard_data')
    access_token = fields.Char("Security Token", default=lambda self: str(uuid.uuid4()), required=True, copy=False, readonly=True)
    kiosk_url = fields.Char('Kiosk URL', compute='_compute_kiosk_url', groups='frontdesk.frontdesk_group_user')
    is_favorite = fields.Boolean()
    privacy_notice = fields.Text()
    privacy_notice_details = fields.Text()
    active = fields.Boolean(default=True)

    _check_auto_checkout_positive = models.Constraint(
        'CHECK(auto_checkout_hours >= 0.0)',
        "The Auto-Checkout value should be positive.",
    )

    @api.constrains('host_ids', 'notify_email')
    def _check_valid_hosts(self):
        for frontdesk in self:
            if frontdesk.notify_email and (invalid_hosts := frontdesk.host_ids.filtered(
                lambda host: not (host.work_email and single_email_re.match(host.work_email))
            )):
                raise ValidationError(self.env._(
                        "%(host_names)s must have a valid Email to be informed about visitor arrival.",
                        host_names=", ".join(invalid_hosts.mapped('name')),
                ))

    @api.onchange('company_id')
    def _onchange_company_id(self):
        """ Ensure that the public user has access to the selected company. """
        if self.company_id and self.company_id != self.env.company:
            public_user = self.env.ref('base.public_user')
            if self.company_id not in public_user.company_ids:
                public_user.company_ids = [(4, self.company_id.id)]

    def _compute_dashboard_data(self):
        """ This method computes the number of guests currently on site and the time of the latest check-in. """
        visitor_data = self.env['frontdesk.visitor']._read_group([
                ('state', '=', 'checked_in'),
                ('station_id', 'in', self.ids),
            ], ['station_id'], ['__count'])
        checked_in_mapped = {station.id: count for station, count in visitor_data}
        for frontdesk in self:
            guest_on_site = 0
            latest_check_in = False
            if frontdesk.visitor_ids:
                guest_on_site = checked_in_mapped.get(frontdesk.id, 0)
                last_visitors = frontdesk.visitor_ids.filtered(lambda v: v.state == 'checked_in')
                latest_check_in_time = last_visitors and last_visitors[-1].check_in
                if latest_check_in_time:
                    total_seconds = (datetime.now() - latest_check_in_time).total_seconds()
                    time_diff = int(total_seconds / 60) if total_seconds < 3600 else int(total_seconds / 3600)
                    latest_check_in = _("Last Check-In: %s minutes ago", time_diff) if total_seconds < 3600 \
                        else _("Last Check-In: %s hours ago", time_diff)
            frontdesk.update({
                'guest_on_site': guest_on_site,
                'latest_check_in': latest_check_in,
            })

    @api.depends('access_token')
    def _compute_kiosk_url(self):
        for frontdesk in self:
            frontdesk.kiosk_url = url_join(self.env['frontdesk.frontdesk'].get_base_url(), '/kiosk/%s/%s' % (frontdesk.id, frontdesk.access_token))

    def action_open_kiosk(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': self.kiosk_url,
            'target': 'self',
        }

    def install_kiosk(self):
        return {
            "type": "ir.actions.act_url",
            "url": f"/scoped_app?app_id=frontdesk&path=kiosk/{self.id}/{self.access_token}",
            "target": "new",
        }

    def action_open_visitors(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Visitors"),
            'res_model': 'frontdesk.visitor',
            'view_mode': 'list,form,kanban,graph,pivot,calendar,gantt',
            'context': {
                "search_default_state_is_checked_in": 1,
                "search_default_check_in": "today",
                "default_station_id": self.id,
            },
            'domain': [('station_id.id', '=', self.id)],
        }

    def get_kiosk_url(self):
        return self.kiosk_url

    def _get_frontdesk_field(self):
        return ['id', 'name', 'description', 'host_selection', 'self_check_in', 'theme',
          'ask_email', 'ask_phone', 'ask_company', 'authenticate_guest', 'privacy_notice',
          'privacy_notice_details']

    def _get_frontdesk_data(self):
        """ Returns the data to the frontend. """
        self.ensure_one()
        data = {
            'company': {'name': self.company_id.name, 'id': self.company_id.id},
            'langs': [{'code': lang[0], 'name': lang[1]} for lang in self.env['res.lang'].get_installed()],
            'station': self.search_read([('id', '=', self.id)], self._get_frontdesk_field()),
        }
        data['station'][0]['has_image'] = bool(self.image)
        return data

    def _get_tmp_code(self):
        self.ensure_one()
        return tools.hmac(self.env(su=True), 'kiosk-mobile', (self.id, fields.Date.to_string(fields.Datetime.now())))
