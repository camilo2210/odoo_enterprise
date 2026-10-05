# Part of Odoo. See LICENSE file for full copyright and licensing details.

import hashlib
import io
import json
import logging
import pathlib
import pprint
import zipfile

import werkzeug

from odoo import http
from odoo.http import request
from odoo.http.stream import Stream
from odoo.modules import get_module_path

_logger = logging.getLogger(__name__)


def ensure_unique_name(name: str):
    existing_names = request.env['iot.box'].sudo().search([('name', 'ilike', name + '%')]).mapped('name')
    base_name = name
    suffix = 1
    while name in existing_names:
        name = f"{base_name} ({suffix})"
        suffix += 1

    return name


def _search_box(identifier: str | None = None, token: str | None = None):
    if token:
        return request.env['iot.box'].sudo()._get_by_token(token)
    return request.env['iot.box'].sudo().search([('identifier', '=', identifier)], limit=1)


class IoTController(http.Controller):
    @http.route('/iot/get_handlers', type='http', auth='public', csrf=False)
    def get_handlers(self, identifier: str, **kw):
        """Return a zip file containing all the IoT handlers for the given IoT Box.

        :param identifier: The identifier of the IoT Box.
        :return: A zip file containing all the IoT handlers.
        """
        # Check if identifier is of one of the IoT Boxes
        box = _search_box(identifier)
        if not box:
            raise werkzeug.exceptions.Unauthorized(
                description="No IoT box found with identifier '%s' or auto update disabled on the box." % identifier
            )

        # '_L.py' files for Linux and '_W.py' for Windows
        incompatible_filename = "_L.py" if box.version[0] == 'W' else "_W.py"
        module_ids = request.env['ir.module.module'].sudo().search([('state', '=', 'installed')])
        fobj = io.BytesIO()
        with zipfile.ZipFile(fobj, 'w', zipfile.ZIP_DEFLATED) as zf:
            for module in module_ids.mapped("name"):
                module_path = get_module_path(module)
                if module_path:
                    iot_handlers = pathlib.Path(module_path) / 'iot_handlers'
                    for handler in iot_handlers.glob('*/*'):
                        if handler.name.startswith(('.', '_')) or handler.name.endswith(incompatible_filename):
                            continue
                        zf.write(handler, handler.relative_to(iot_handlers))  # In order to remove the absolute path

        etag = hashlib.sha256(fobj.getvalue()).hexdigest()
        # If the file has not been modified since the last request, return a 304 (Not Modified)
        if etag == request.httprequest.headers.get('If-None-Match'):
            return request.make_response('', headers=[('ETag', etag)], status=304)

        return Stream(
            type='data',
            data=fobj.getvalue(),
            download_name='iot_handlers.zip',
            etag=etag,
            size=fobj.tell(),
            public=True,
        ).get_response()

    @http.route('/iot/keyboard_layouts', type='http', auth='public', csrf=False)
    def load_keyboard_layouts(self, available_layouts: str):
        if not request.env['iot.keyboard.layout'].sudo().search_count([]):
            request.env['iot.keyboard.layout'].sudo().create(json.loads(available_layouts))
        return ''

    @http.route('/iot/box/<string:identifier>/display_url', type='http', auth='public')
    def get_url(self, identifier: str):
        urls = {}
        iotbox = _search_box(identifier)
        if iotbox:
            iot_devices = iotbox.device_ids.filtered(lambda device: device.type == 'display')
            for device in iot_devices:
                urls[device.identifier] = device.display_url
        return json.dumps(urls)

    @http.route('/iot/box/send_websocket', type='jsonrpc', auth='public')
    def iot_box_send_websocket(self, session_id: str, iot_box_identifier: str, device_identifier: str | None, status: str, **kwargs):
        """Called by the IoT Box once an operation is over. We then forward
        the acknowledgment to the user who made the request to inform him
        of the success of the operation.

        :param session_id: ID of the operation
        :param iot_box_identifier: The IP of the IoT box (used to find the box)
        :param device_identifier: The IoT device identifier
        :param status: Status of the last action (success, error, ...)
        :param kwargs:
        """
        box = _search_box(iot_box_identifier)
        if not box:
            _logger.info("No IoT Box found with identifier: '%s'. Request ignored", iot_box_identifier)
            return

        if (
            device_identifier
            and device_identifier != box.identifier  # target the box itself
            and not request.env["iot.device"].sudo().search(
                    [('identifier', '=', device_identifier), ('iot_id', '=', box.id)], limit=1
            )
        ):
            _logger.info(
                "No IoT device found with identifier '%s' (iot_box_identifier: %s). Request ignored",
                device_identifier, iot_box_identifier
            )
            return
        request.env['iot.channel'].sudo().send_message({
            'session_id': session_id or kwargs.get("owner"),  # TODO: remove "owner" when v19.0 is deprecated
            'iot_box_identifier': iot_box_identifier,
            'device_identifier': device_identifier,
            'message': {
                'status': status,
                'message': kwargs.get('message', ''),  # required by printer status
                'result': kwargs.get('result', {}),
            },
        }, message_type='operation_confirmation')
        _logger.info('Received websocket message for iot box %s, device %s, session_id %s with status %s and kwargs %s',
                     box.name, device_identifier, session_id, status, kwargs)

    @http.route('/iot/setup', type='jsonrpc', auth='public')
    def iot_box_setup(self, iot_box: dict[str, str], devices: dict[str, dict[str, str]]):
        """Called by the IoT Box.
        It updates the "draft" IoT Box record to a real one, and sets/updates
        the associated devices according to the ones received from the IoT Box.

        The controller returns the WebSocket channel in order for the IoT Box
        to connect without a second controller call.

        :param dict iot_box: IoT Box information
        :param dict devices: IoT devices information
        :return: IoT websocket channel
        """
        iot_identifier = iot_box['identifier']  # IoT Serial number
        # search box by token OR MAC for box that just upgraded TODO: remove when v18.0 is deprecated
        box = _search_box(token=iot_box['token']) or _search_box(iot_box.get('mac'))
        if not box:
            _logger.info("Unknown IoT Box attempted to connect with identifier '%s'.", iot_identifier)
            return None
        # we created a draft box to store the token, if there was an old record with the
        # same identifier, we keep the old box but with the new token
        old_box = _search_box(identifier=iot_identifier)
        if old_box and old_box.id != box.id:
            old_box.token = box.token
            box.unlink()
            box = old_box

        new_iot_ip = iot_box['ip']
        new_iot_version = iot_box['version']
        new_iot_record = {
            'ip': new_iot_ip,
            'version': new_iot_version,
        }

        if "Connecting" in box.name:
            # Box is in "Connecting" state, we set all the values we have
            name = 'IoT Box' if new_iot_version.startswith('L') else 'Virtual IoT Box'
            new_iot_record.update({
                'name': ensure_unique_name(name),
                'identifier': iot_identifier,
            })
            box.write(new_iot_record)

        current_data = (box.identifier, box.ip, box.version)
        if (current_data) != (iot_identifier, new_iot_ip, new_iot_version):
            # Box already exists, IP or version changed, we update the record
            _logger.warning('Updating %s %s with data: %s', box.name, current_data, pprint.pformat(new_iot_record))
            box.write({
                **new_iot_record,
                'identifier': iot_identifier,  # Ensure upgrade from MAC to serial number TODO: remove when v18.0 is deprecated
            })
        # Add token to box record (update <18.3 -> 19.1) TODO: remove when v18.0 is deprecated
        if not box.token and iot_box.get("token"):
            box.token = iot_box["token"]

        _logger.info('IoT %s devices:\n%s', box, pprint.pformat(devices))
        # Update or create devices
        iot_devices_sudo = request.env['iot.device'].sudo()
        previously_connected_iot_devices = iot_devices_sudo.search([
            ('iot_id', '=', box.id),
            ('connected_status', '=', 'connected')
        ])

        iot_device_fields = request.env['iot.device']._fields
        available_types = {s[0] for s in iot_device_fields['type'].selection}
        available_connections = {s[0] for s in iot_device_fields['connection'].selection}
        for device_identifier, device_data in devices.items():
            if device_data['type'] in available_types and device_data['connection'] in available_connections:
                # Special case to handle serial port change for blackbox
                if device_data['type'] == 'fiscal_data_module' and 'BODO001' in device_data['name']:
                    existing_blackbox = iot_devices_sudo.search([
                        ('iot_id', '=', box.id), ('name', 'like', 'BODO001'), ('type', '=', 'fiscal_data_module')
                    ], limit=1)
                    if existing_blackbox:
                        existing_blackbox.write({'identifier': device_identifier})
                        iot_devices_sudo |= existing_blackbox
                        continue

                iot_device = iot_devices_sudo.search([
                    ('iot_id', '=', box.id), ('identifier', '=', device_identifier)
                ], limit=1)

                # If an `iot.device` record isn't found for this `device`, create a new one.
                if not iot_device:
                    iot_device = iot_devices_sudo.create({
                        'iot_id': box.id,
                        'name': device_data['name'],
                        'identifier': device_identifier,
                        'type': device_data['type'],
                        'connection': device_data['connection'],
                    })
                elif iot_device and iot_device.type != device_data.get('type'):
                    iot_device.write({
                        'name': device_data.get('name'),
                        'type': device_data.get('type'),
                    })

                iot_devices_sudo |= iot_device
        # Mark the received devices as connected, disconnect the others.
        iot_devices_sudo.write({'connected_status': 'connected'})
        (previously_connected_iot_devices - iot_devices_sudo).write({'connected_status': 'disconnected'})
        return request.env['iot.channel'].sudo().get_iot_channel()

    @http.route('/iot/box/update_certificate_status', type='jsonrpc', auth='public')
    def update_certificate_status(self, identifier: str, ssl_certificate_end_date: str):
        """Update the SSL certificate end date for the IoT Box.

        :param str identifier: IoT Box identifier
        :param str ssl_certificate_end_date: SSL certificate end date
        """
        box = _search_box(identifier)
        if not box:
            _logger.warning("No IoT Box found with identifier '%s'. Request ignored", identifier)
            return

        box.write({'ssl_certificate_end_date': ssl_certificate_end_date})
