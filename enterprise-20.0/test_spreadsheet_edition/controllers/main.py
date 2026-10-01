# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import request, Controller

from odoo.addons.spreadsheet_edition.models.spreadsheet_mixin import PUBLIC_COMMAND_PERMISSIONS


class TestSpreadsheetEditionController(Controller):

    @http.route([
        '/test/spreadsheet/public_command_permissions',
    ], type='http', auth='user', methods=['GET'])
    def get_public_command_permissions(self):
        return request.make_json_response(list(PUBLIC_COMMAND_PERMISSIONS.keys()))
