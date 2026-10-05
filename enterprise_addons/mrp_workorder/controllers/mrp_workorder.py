from odoo import http
from odoo.http import request


class MrpWorkorderController(http.Controller):

    @http.route('/mrp_workorder/rid_of_message_demo_barcodes', type='jsonrpc', auth='user')
    def rid_of_message_demo_barcodes(self, **kw):
        """ Edit the mrp_display client action so that it doesn't display the 'print demo barcodes sheet' message """
        if not request.env.user.has_group('mrp_workorder.group_mrp_wo_shop_floor'):
            return request.not_found()
        action = request.env.ref('mrp_workorder.action_mrp_display')
        action and action.sudo().write({'params': {'message_demo_barcodes': False}})
