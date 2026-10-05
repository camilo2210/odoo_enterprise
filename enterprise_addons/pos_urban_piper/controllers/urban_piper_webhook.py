# Part of Odoo. See LICENSE file for full copyright and licensing details.

from werkzeug.exceptions import BadRequest, Unauthorized

from odoo import http
from odoo.http import request
from odoo.tools import consteq
from odoo.tools.json import scriptsafe as json

from ..utils.schema_validation import (
    validate_urbanpiper_schema,
    get_store_ref_id,
    URBANPIPER_WEBHOOK_EVENT_MAPPING,
)


class PosUrbanPiperController(http.Controller):

    def _get_urbanpiper_store(self, data, event_type):
        """Validate webhook payload and retrieve the corresponding UrbanPiper store."""
        log_urbanpiper = request.env['pos.config'].sudo().log_urbanpiper
        is_valid, err_msg = validate_urbanpiper_schema(event_type, data)
        if not is_valid:
            log_urbanpiper(f'UrbanPiper Webhook: Invalid schema - {err_msg}', 'UrbanPiper Invalid Webhook Schema', func='_get_urbanpiper_store')
            raise BadRequest('UrbanPiper Webhook: Invalid schema.')

        store_identifier = get_store_ref_id(data, event_type)
        if store_identifier and (
            store := request.env['pos.urbanpiper.store'].sudo()._get_by_identifier(store_identifier)
        ):
            return store
        log_urbanpiper(
            f'UrbanPiper Webhook: store not found - event type: {event_type}, identifier : {store_identifier}',
            'UrbanPiper Store Not Found',
            func='_get_urbanpiper_store'
        )
        raise BadRequest('UrbanPiper Webhook: store not found.')

    def _check_access(self, db_uuid, current_db_uuid):
        """Ensure the webhook request originates from the same database (UUID check)."""
        if not db_uuid or not consteq(current_db_uuid, db_uuid):
            # Ignore request if it's not from the same database
            request.env['pos.config'].sudo().log_urbanpiper(
                f'UrbanPiper Webhook: Invalid UUID - "{db_uuid}".',
                'UrbanPiper Webhook: Invalid UUID',
                log_xml=False,
            )
            raise Unauthorized('UrbanPiper Webhook: Invalid UUID, You may need to register the webhooks.')

    @http.route(['/pos_urban_piper/v1/<string:db_uuid>', '/pos_urban_piper/v1/dev'], type='jsonrpc', methods=['POST'], auth='public')
    def webhook_post(self, db_uuid=False):
        """
        Handle incoming UrbanPiper webhook requests.

        The endpoint with `db_uuid` is intended for production databases.
        The `/pos_urban_piper/v1/dev` endpoint is used for test and development databases
        to avoid polluting Atlas webhooks with data from temporary or non-production databases.
        """
        event_type_code = request.httprequest.headers.get('X-UPR-Event-Type')
        event_type = URBANPIPER_WEBHOOK_EVENT_MAPPING.get(event_type_code)
        data = request.get_json_data()

        store = self._get_urbanpiper_store(data, event_type)
        if not store.use_test_mode:
            current_db_uuid = request.env['ir.config_parameter'].sudo().get_str('database.uuid')
            self._check_access(db_uuid, current_db_uuid)
        self._process_webhook_data(data, event_type, store)

    @http.route('/urbanpiper/webhook/<string:event_type>', type='jsonrpc', methods=['POST'], auth='public')
    def old_webhook_post(self, event_type):
        """
        Handle legacy UrbanPiper webhook requests.

        This endpoint is kept temporarily to support older webhook integrations.
        If the event type is already configured to be handled by the new webhook
        endpoints, the request is rejected to prevent duplicate processing.
        """
        if request.env['pos.urban.piper.webhook'].sudo().search_count([('event_name', '=', event_type)], limit=1):
            raise BadRequest('UrbanPiper Webhook: Will be handled by the new webhook end-points.')

        data = request.get_json_data()
        store = self._get_urbanpiper_store(data, event_type)
        if not store.use_test_mode:
            request_uuid = request.httprequest.headers.get('X-Urbanpiper-Uuid')
            urbanpiper_uuid = request.env['ir.config_parameter'].sudo().get_str('pos_urban_piper.uuid')
            self._check_access(request_uuid, urbanpiper_uuid)
        self._process_webhook_data(data, event_type, store)

    def _process_webhook_data(self, data, event_type, store):
        PosConfig = request.env['pos.config'].sudo()
        log_urbanpiper = PosConfig.log_urbanpiper

        PosOrder = request.env['pos.order'].sudo()
        if event_type in ('order_status_update', 'rider_status_update'):
            if not (PosOrder := PosOrder.search([('delivery_identifier', '=', str(data['order_id']))], limit=1)):
                log_urbanpiper(f"UrbanPiper: Order {data['order_id']} not found for update the status.", 'UrbanPiper Order Not Found', func='_process_webhook_data')
                return

        event_method_name = f'process_urbanpiper_{event_type}'
        # Dynamically resolve and invoke the webhook handler based on the event type.
        # The handler may be implemented on either `pos.config` or `pos.order`.
        # This design allows new UrbanPiper events to be supported by simply
        # adding a corresponding `process_urbanpiper_<event_type>` method.
        # e.g. process_urbanpiper_order_placed, process_urbanpiper_store_action, etc.
        event_handler = (
            getattr(PosConfig, event_method_name, None)
            or getattr(PosOrder, event_method_name, None)
        )
        if event_handler:
            log_urbanpiper(f'Processing {event_type} webhook. {json.dumps(data)}', f'UrbanPiper Webhook received - {event_type}', 'info', func='_process_webhook_data')
            event_handler(data, store)
        else:
            log_urbanpiper(
                f'UrbanPiper Webhook: No handler implemented for event type "{event_type}".',
                'UrbanPiper Webhook Handler Missing',
                'info',
                log_xml=False,
                func='_process_webhook_data'
            )
            raise BadRequest('UrbanPiper Webhook: Invalid or unsupported webhook payload.')
