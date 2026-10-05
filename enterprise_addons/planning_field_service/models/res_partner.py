# Part of Odoo. See LICENSE file for full copyright and licensing details.

import urllib.parse

from odoo import models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def action_partner_navigate(self):
        self.ensure_one()
        encoded_address = urllib.parse.quote_plus(self.contact_address_complete)
        url = f"https://www.google.com/maps/dir/?api=1&destination={encoded_address}"
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new'
        }

    def _ensure_geolocalized(self):
        self.ensure_one()
        if self._is_geolocalized():
            return True
        if not self.contact_address_complete:
            return False
        self.geo_localize()
        return self._is_geolocalized()

    def _get_travel_information_between_partners(self, other_partner):
        """ Return travel time and distance between two partners using Mapbox. """
        self.ensure_one()
        other_partner.ensure_one()
        if not (self._is_geolocalized() and other_partner._is_geolocalized()):
            return None
        if self == other_partner or (self.partner_longitude == other_partner.partner_longitude and self.partner_latitude == other_partner.partner_latitude):
            return {
                'time': 0,
                'distance': 0,
            }
        route, error = self.env['planning.slot']._fetch_mapbox_driving_route(self + other_partner)
        if error:
            return {'error': error}
        if not route:
            return None
        return {
            'time': route.get('duration', 0) / 3600,
            'distance': route.get('distance', 0) / 1000,
        }
