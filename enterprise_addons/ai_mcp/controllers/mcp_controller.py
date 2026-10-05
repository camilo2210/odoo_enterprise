# Part of Odoo. See LICENSE file for full copyright and licensing details.
import time
import json
from logging import getLogger
from werkzeug.exceptions import InternalServerError

from odoo import http
from odoo.http import request
from odoo.tools.json import json_default

from odoo.addons.ai_mcp.utils.exceptions import McpMethodNotFoundError

logger = getLogger(__name__)


class McpController(http.Controller):
    # JSONRPC 2.0 Spec: https://www.jsonrpc.org/specification
    # MCP Schema Spec: https://modelcontextprotocol.io/specification/2025-11-25/schema
    @http.route('/mcp', type='http', auth='bearer', bearer_scope='mcp', csrf=False, methods=['POST'])
    def handle_mcp_request(self):
        payload = None
        result = None
        start_time = time.perf_counter()
        try:
            payload = request.get_json_data()
            result = request.env['ai.mcp.request.dispatcher']._mcp_dispatch(payload)
            self._log_mcp(payload=payload, result=result or {}, elapsed=time.perf_counter() - start_time)
            # result is None in case of a notification from the MCP client. In which case, an empty HTTP response with status 202 is returned.
            # https://modelcontextprotocol.io/specification/2025-11-25/basic/transports#sending-messages-to-the-server
            if result is None:
                return request.make_response('', status=202)
            return request.make_json_response({
                'jsonrpc': '2.0',
                'id': payload['id'],
                'result': result,
            })
        except Exception as e:
            # https://modelcontextprotocol.io/specification/2025-06-18/server/tools#error-handling
            # Exceptions are caught and a response is with isError set to True as per the MCP spec.
            # We also raise InternalServerError instead of returning JSON error response directly to be consistent
            # with the rest of the system (error status must raise exception) and to let Odoo http module correctly
            # handle post-processing and call handle_error of the dispatcher.

            # An unimplemented method must be a JSONRPC protocol error, not a tool error. MCP clients sometimes
            # use this to determine MCP version. For example, if server/discover method doesn't exist, the client
            # knows the server is an older version of MCP and falls back to use initialize method.
            logger.debug("Exception during MCP request", exc_info=True)
            self._log_mcp(payload=payload or {}, result={'isError': True}, elapsed=time.perf_counter() - start_time)

            error_response = {
                'jsonrpc': '2.0',
                'id': (payload or {}).get('id'),
            }
            if isinstance(e, McpMethodNotFoundError):
                error_response['error'] = {
                    'code': e.code,
                    'message': e.message,
                    'data': {'method': payload.get('method')},
                }
            else:
                error_response['result'] = {
                    'content': [{'type': 'text', 'text': json.dumps(str(e), default=json_default, ensure_ascii=False)}],
                    'isError': True
                }
            raise InternalServerError(response=request.make_json_response(error_response))

    def _log_mcp(self, /, payload, result, elapsed):
        method = payload.get('method', 'unknown')
        params = payload.get('params') or {}
        method = f"{method}:{params['name']}" if params.get('name') else method
        status = 'error' if result.get('isError') else 'success'
        client = request.httprequest.remote_addr or 'unknown'
        if method == 'initialize':
            client_info = params.get('clientInfo', {})
            client_name = client_info.get('name', 'unknown')
            client_version = client_info.get('version', 'unknown')
            protocol_version = params.get('protocolVersion')
            logger.info("%s %.3fs %s %s %s %s %s",
            method, elapsed, status, client, client_name, client_version, protocol_version)
        else:
            logger.info("%s %.3fs %s %s", method, elapsed, status, client)
