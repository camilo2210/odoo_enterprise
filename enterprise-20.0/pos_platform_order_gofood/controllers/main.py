# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

import psycopg2

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.tools import consteq

from odoo.addons.pos_enterprise.models.data_validator import list_of, object_of

order_event_schema = object_of({
    'header': object_of({
        'event_name': True,
        'event_id': True,
        'version': True,
        'timestamp': True,
    }),
    'body': object_of({
        'customer': object_of({
            'id': True,
            'name': True,
        }),
        'driver': object_of({
            'name': True,
        }),
        'service_type': True,
        'outlet': object_of({
            'id': True,
            'external_outlet_id': True,
        }),
        'order': object_of({
            'status': True,
            'pin': True,
            'order_number': True,
            'order_total': True,
            'order_items': list_of(object_of({
                'quantity': True,
                'price': True,
                'notes': True,
                'name': True,
                'id': True,
                'external_id': True,
                'variants': list_of(object_of({
                    'id': True,
                    'name': True,
                    'external_id': True,
                })),
            })),
            'applied_promotions': list_of(object_of({
                'scope': True,
                'detail': object_of({
                    'item': object_of({
                        'id': True,
                        'external_id': True,
                    }),
                    'id': True,
                }),
            })),
            'currency': True,
            'takeaway_charges': True,
            'created_at': True,
        }),
    }),
})

_logger = logging.getLogger(__name__)


class GoFoodController(http.Controller):

    @http.route('/gofood/notification', type='jsonrpc', methods=['POST'], auth='public')
    def gofood_webhook(self):
        """Process the notification data sent by GoFood to the webhook
        """
        data = request.get_json_data()
        try:
            is_valid, error = order_event_schema(data)
            if not is_valid:
                _logger.warning("GoFood: %r", error)
                return http.Response('Invalid notification data: %s' % error, status=400)

            store_sudo = request.env['platform.order.entity'].sudo()._find_store_from_data('gofood', data)
            if not store_sudo:
                _logger.warning("GoFood: Store not found for notification data: %r", data)
                return http.Response('Store not found', status=404)
            resp = self._verify_notification_signature(store_sudo)
            if resp:
                return resp

            order_sudo = request.env['pos.order'].sudo()._find_order_from_data('gofood', data, raise_if_not_found=False)
            if not order_sudo:
                store_sudo._create_order_from_data(data)
            else:
                order_sudo._update_order_status_from_data(data)

        except ValidationError:
            return http.Response('Invalid notification data', status=400)

        return http.Response('OK', status=200)

    @staticmethod
    def _verify_notification_signature(store):
        received_signature = request.httprequest.headers.get('X_GO_SIGNATURE')
        if not received_signature:
            _logger.warning("Received notification with missing signature.")
            return http.Response(status=403)

        expected_signature = store.provider_id._gofood_calculate_signature(request.httprequest.get_data())
        if not consteq(received_signature, expected_signature):
            _logger.warning("Received notification with invalid signature.")
            return http.Response(status=403)

        idempotency_key = request.httprequest.headers.get('X_GO_IDEMPOTENCY_KEY')
        try:
            with request.env.cr.savepoint():
                request.env['gofood.idempotency.key'].sudo().create({'key': idempotency_key})
        except psycopg2.errors.UniqueViolation:
            _logger.warning("Received notification with duplicate idempotency key %s.", idempotency_key)
            return http.Response(status=403)

        return None
