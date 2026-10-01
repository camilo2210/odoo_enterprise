# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import fields, models, _
from odoo.addons.phone_validation.tools import phone_validation
from odoo.addons.whatsapp.tools import phone_validation as phone_validation_wa

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    wa_channel_count = fields.Integer(string='WhatsApp Channel Count', compute="_compute_wa_channel_count")

    def _compute_wa_channel_count(self):
        partner_channel_counts = {partner.id: 0 for partner in self}
        member_count_by_partner = self.env['discuss.channel.member']._read_group(
            domain=[
                ('channel_id.channel_type', '=', 'whatsapp'),
                ('partner_id', 'in', self.ids)
            ],
            groupby=['partner_id'],
            aggregates=['id:count'],
        )
        for partner, count in member_count_by_partner:
            partner_channel_counts[partner.id] += count
        for partner in self:
            partner.wa_channel_count = partner_channel_counts[partner.id]

    # MAIL OVERRIDES

    def _creation_message(self):
        if self.env.context.get('partner_from_whatsapp'):
            return _('Partner created by incoming WhatsApp message.')
        return super()._creation_message()

    # WHATSAPP SEARCH/CREATE

    def _find_or_create_from_whatsapp_identifiers(self, identifiers, name, wa_account_id):
        # Match on non-number identifiers first, then fall back to the
        # legacy `_find_or_create_from_number` hook for the phone number. That hook
        # stays on the inbound path so existing overrides of it keep working even
        # when the identifiers module is not installed.
        partner = self._find_from_whatsapp_identifiers(identifiers, wa_account_id=wa_account_id)
        if not partner and identifiers.get('number'):
            partner = self._find_or_create_from_number(identifiers['number'], name)
        if not partner:
            create_vals = self._get_create_values_from_whatsapp_identifiers(identifiers)
            if not create_vals:
                return self.env['res.partner']
            create_vals['name'] = name
            partner = self.env['res.partner'].with_context(partner_from_whatsapp=True).create(create_vals)
        partner._update_from_whatsapp_identifiers(identifiers, wa_account_id)
        return partner

    def _find_from_whatsapp_identifiers(self, identifiers, wa_account_id=None):
        if not identifiers.get('number'):
            return self.env['res.partner']
        formatted_number = self._format_wa_phone(identifiers['number'])
        if not formatted_number:
            return self.env['res.partner']
        region_data = phone_validation.phone_get_region_data_for_number(formatted_number)
        number_national_number = str(region_data['national_number'])
        # search partner on INTL number, then fallback on national number
        partners = self.search([('phone_mobile_search', '=', formatted_number)])
        if not partners:
            partners = self.search([('phone_mobile_search', '=like', number_national_number)])
        return partners[:1]

    def _update_from_whatsapp_identifiers(self, identifiers, wa_account_id):
        self.ensure_one()
        if not self.phone and identifiers.get('number'):
            # format the same as is done everywhere else (effectively add + at the front of the number)
            self.phone = self._format_wa_phone(identifiers['number']) or identifiers['number']

    def _get_create_values_from_whatsapp_identifiers(self, identifiers):
        vals = {}
        if number := identifiers.get('number'):
            formatted_number = self._format_wa_phone(number)
            if not formatted_number:
                return vals
            region_data = phone_validation.phone_get_region_data_for_number(formatted_number)
            number_country_code = region_data['code']
            number_phone_code = int(region_data['phone_code'])

            # do not set a country if country code is not unique as we cannot guess
            country = self.env['res.country'].search([('phone_code', '=', number_phone_code)])
            if len(country) > 1:
                country = country.filtered(lambda c: c.code.lower() == number_country_code.lower())

            return {
                'country_id': country.id if country and len(country) == 1 else False,
                'phone': formatted_number,
            }
        return vals

    def _format_wa_phone(self, number):
        search_number = number if number.startswith('+') else f'+{number}'
        try:
            formatted_number = phone_validation_wa.wa_phone_format(
                self.env.company,
                number=search_number,
                force_format='E164',
                raise_exception=True,
            )
        except Exception:  # noqa: BLE001 don't want to crash in that point, whatever the issue
            _logger.warning('WhatsApp: impossible to format incoming number %s', number)
            formatted_number = False

        return formatted_number

    def _find_or_create_from_number(self, number, name=False):
        """ Number should come currently from whatsapp and contain country info."""
        formatted_number = self._format_wa_phone(number)
        partner = self._find_from_whatsapp_identifiers({'number': number})
        if not partner and formatted_number:
            create_vals = self._get_create_values_from_whatsapp_identifiers({'number': formatted_number})
            create_vals['name'] = name or formatted_number
            partner = self.env['res.partner'].with_context(partner_from_whatsapp=True).create(create_vals)
        return partner

    def action_open_partner_wa_channels(self):
        return {
            'name': _('WhatsApp Chats'),
            'type': 'ir.actions.act_window',
            'domain': [('channel_type', '=', 'whatsapp'), ('channel_partner_ids', 'in', self.ids)],
            'res_model': 'discuss.channel',
            'views': [(self.env.ref('whatsapp.discuss_channel_view_list_whatsapp').id, 'list')],
        }
