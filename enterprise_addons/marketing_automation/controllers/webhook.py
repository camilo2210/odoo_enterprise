from odoo import http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request, route
from odoo.tools.misc import consteq


class MarketingCampaignController(http.Controller):

    @route('/mkauto/webhook/<int:id>/<string:webhook_uuid>', type='json2', auth='public', save_session=False)
    def call_mkauto_webhook_http(self, id, webhook_uuid, search_domain=None, create_values=None, **kwargs):
        campaign = request.env['marketing.campaign'].sudo().browse(id)
        if not campaign.exists() or not consteq(campaign.webhook_uuid, webhook_uuid) or not campaign._is_webhook_enabled():
            return request.make_json_response({'status': 'error'}, status=404)

        try:
            campaign._process_webhook_payload(search_domain or {}, create_values or {})
        except (UserError, ValidationError):
            return request.make_json_response({'status': 'error'}, status=500)
        return request.make_json_response({'status': 'ok'}, status=200)

    @route('/mkauto/webhook/<int:id>/<string:webhook_uuid>/test', type='json2', auth='public', save_session=False)
    def call_mkauto_webhook_http_test(self, id, webhook_uuid, search_domain=None, create_values=None, **kwargs):
        """
            The test route evaluates the payload the same way as the standard route.
            However, it will always raise an UserError on a successful evaluation to rollback any changes.
            Certain errors are also made more explicit.
        """
        campaign = request.env['marketing.campaign'].sudo().browse([id])
        if not campaign.exists() or not consteq(campaign.webhook_uuid, webhook_uuid):
            return request.make_json_response({'status': 'error'}, status=404)

        try:
            campaign._process_webhook_payload(search_domain or {}, create_values or {}, webhook_test=True)
        except ValidationError:
            return request.make_json_response({'status': 'error'}, status=500)
        except UserError as e:
            return request.make_json_response({'status': 'ok', 'msg': e.args[0]}, status=200)
