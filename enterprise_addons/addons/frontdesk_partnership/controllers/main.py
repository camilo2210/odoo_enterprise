# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime, timedelta

from odoo.exceptions import UserError
from odoo.http import route, request
from odoo.tools import float_repr

from odoo.addons.frontdesk.controllers.main import Frontdesk


class FrontdeskMembers(Frontdesk):
    def _get_additional_info(self, frontdesk, lang, is_mobile=False):
        response = super()._get_additional_info(frontdesk, lang, is_mobile=is_mobile)
        if frontdesk.frontdesk_type == 'members':
            response.template = 'frontdesk_partnership.FrontdeskPartnership'
        return response

    @route('/frontdesk/<int:frontdesk_id>/<string:token>/get_visitor_data', type='jsonrpc', auth='public', methods=['POST'])
    def get_visitor_data(self, frontdesk_id, token, barcode, **kwargs):
        frontdesk = request.env['frontdesk.frontdesk'].sudo().browse(frontdesk_id)
        if not frontdesk.exists() or not self._verify_token(frontdesk, token):
            return request.not_found()
        if not (partner_sudo := request.env['res.partner'].sudo().search([("barcode", "=", barcode)], limit=1)):
            raise UserError(request.env._("No partner corresponding to this barcode was found."))
        grade_ids = frontdesk.required_grade_ids if frontdesk.frontdesk_type == 'members' else False
        if not partner_sudo.grade_id or (grade_ids and partner_sudo.grade_id.id not in grade_ids.ids):
            raise UserError(request.env._("The corresponding partner does not have the correct grade to enter through this frontdesk."))
        if (
            partner_sudo.last_barcode_scan and frontdesk.passback_timeout and (
                waiting_seconds := (partner_sudo.last_barcode_scan + timedelta(minutes=frontdesk.passback_timeout) - datetime.now()).total_seconds()
            ) > 0.
        ):
            raise UserError(request.env._(
                "This barcode has been scanned recently, please wait %s minutes before scanning again.",
                float_repr(waiting_seconds / 60., 0)
            ))
        partner_sudo.last_barcode_scan = datetime.now()
        return {'name': partner_sudo.name, 'phone': partner_sudo.phone, 'email': partner_sudo.email, 'company': partner_sudo.company_id.name}
