# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.delivery_sendcloud.models.sendcloud_service import SendCloud, _sendcloud_send_request

LOCATION_URL = "https://servicepoints.sendcloud.sc/api/v2/"


class SendcloudLocationsRequest(SendCloud):

    def get_close_locations(self, partner_address, distance, carrier):
        if carrier == 'sendcloud':
            carrier = ''
        params = {"country": partner_address.country_code,
                  "address": f'{partner_address.zip} {partner_address.city or ""}',
                  "radius": distance,
                  "carrier": carrier}
        return _sendcloud_send_request(self, 'service-points', params=params, route=LOCATION_URL)
