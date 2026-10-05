# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.addons.website.tools import text_from_html
from odoo.addons.website_appointment.controllers.appointment import WebsiteAppointment


class AppointmentType(models.Model):
    _name = 'appointment.type'
    _inherit = [
        'appointment.type',
        'website.seo.metadata',
        'website.published.multi.mixin',
        'website.searchable.mixin',
        'website.structured_data.mixin',
        'website.trackable.mixin',
    ]
    _website_track_field = 'appointment_type_id'

    def _compute_website_url(self):
        super()._compute_website_url()
        for appointment_type in self:
            if appointment_type.id:
                appointment_type.website_url = '/appointment/%s' % self.env['ir.http']._slug(appointment_type)
            else:
                appointment_type.website_url = False

    def create_and_get_website_url(self, **kwargs):
        if 'appointment_tz' not in kwargs:
            # appointment_tz is a mandatory field defaulting to the environment user's timezone
            # however, sometimes the current user timezone is not defined, let's use a fallback
            website_visitor = self.env['ir.http']._get_visitor_from_request(force_create=False)
            kwargs['appointment_tz'] = self.env.user.tz or website_visitor.timezone or 'UTC'

        return super().create_and_get_website_url(**kwargs)

    def copy_data(self, default=None):
        """ Force False manually for all categories of appointment type when duplicating
        even for categories that should be auto-publish. """
        default = dict(default or {})
        default['is_published'] = False
        return super().copy_data(default=default)

    def get_backend_menu_id(self):
        return self.env.ref('calendar.mail_menu_calendar').id

    @api.model
    def _search_get_detail(self, website, order, options):
        invite_token = options.get('invite_token')
        allowed_appointment_type_ids = WebsiteAppointment._fetch_and_check_private_appointment_types(
            options.get('filter_appointment_type_ids'),
            options.get('filter_staff_user_ids'),
            options.get('filter_resource_ids'),
            invite_token,
            domain=WebsiteAppointment._appointments_base_domain(
                filter_appointment_type_ids=options.get('filter_appointment_type_ids'),
                search=options.get('search'),
                invite_token=invite_token,
                additional_domain=WebsiteAppointment._appointment_website_domain(self),
                filter_countries=True,
            )
        ).ids

        domain = [[('id', 'in', allowed_appointment_type_ids)]]

        search_fields = ['name', 'message_intro']
        fetch_fields = ['name', 'website_url', 'appointment_duration_formatted', 'message_intro']
        mapping = {
            'name': {'name': 'name', 'type': 'text', 'match': True},
            'website_url': {'name': 'website_url', 'type': 'url', 'truncate': False, 'html': False},
            'search_item_metadata': {'name': 'appointment_duration_formatted', 'type': 'text', 'html': True},
            'image_url': {'name': 'image_url', 'type': 'html'},
            'description': {'name': 'message_intro', 'type': 'text', 'html': True, 'match': True},
        }

        return {
            'base_domain': domain,
            'fetch_fields': fetch_fields,
            'icon': 'calendar_today',
            'mapping': mapping,
            'model': 'appointment.type',
            'requires_sudo': bool(invite_token),
            'search_fields': search_fields,
            'group_name': self.env._("Appointments"),
            'sequence': 50,
        }

    def _prepare_jsonld_vals(self):
        self.ensure_one()
        website = self.env.website or self.env['website'].browse(self.env.context.get('host_id'))
        appointment_url = self.website_absolute_url
        provider = [{'@id': f'{website.get_base_url()}/#organization'}]
        provider += [
            {'@type': 'Person', 'name': user.name}
            for user in self.staff_user_ids
        ]
        channel = {'@type': 'ServiceChannel'}
        if self.location_id:
            if postal := self._build_postaladdress_jsonld_vals(self.location_id):
                channel['serviceLocation'] = {
                    '@type': 'Place',
                    'name': self.location_id.name,
                    'address': postal,
                }
        else:
            channel['serviceUrl'] = appointment_url
        vals = {
            '@type': 'Service',
            '@id': f'{appointment_url}/#service',
            'name': self.name,
            'url': appointment_url,
            'provider': provider[0] if len(provider) == 1 else provider,
            'availableChannel': channel,
            'offers': {
                '@type': 'Offer',
                'availability': 'https://schema.org/InStock',
            },
        }
        if description := self.message_intro and text_from_html(self.message_intro, True):
            vals['description'] = description
        return vals

    def _get_jsonld_dict(self, is_detail_page=False):
        schemas = super()._get_jsonld_dict(is_detail_page)
        if is_detail_page:
            schemas.append(self._prepare_jsonld_vals())
        elif self:
            schemas.append(self._build_collectionpage_jsonld_vals(
                self.env._("Appointment Types Selection"), '/appointment', self,
            ))
        return schemas

    def _get_breadcrumb_items(self, is_detail_page=False):
        items = super()._get_breadcrumb_items(is_detail_page)
        items.append((self.env._("Appointments"), '/appointment'))
        if is_detail_page:
            items.append((self.name, self.website_url))
        return items

    def action_share_invite(self):
        action = super().action_share_invite()
        if self.env.user.has_group('website.group_multi_website'):
            website_id = self.website_id
        else:
            website_id = self.env['website']
        action['context'].update({'default_website_id': website_id.id})
        return action

    def _prepare_calendar_event_values(
            self, asked_capacity, booking_line_values, description, duration, allday,
            appointment_invite, guests, name, customer, staff_user, start, stop
    ):
        values = super()._prepare_calendar_event_values(
            asked_capacity, booking_line_values, description, duration, allday,
            appointment_invite, guests, name, customer, staff_user, start, stop
        )
        if self.env.user._is_public() and (visitor := self.env['ir.http']._get_visitor_from_request()):
            values['visitor_id'] = visitor.id
        return values

    def _search_render_results(self, fetch_fields, mapping, icon, limit):
        results_data = super()._search_render_results(fetch_fields, mapping, icon, limit)
        for data in results_data:
            data['image_url'] = '/web/image/appointment.type/%s/image_128' % data['id']
        return results_data
