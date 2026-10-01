# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json

from werkzeug.datastructures import FileStorage

from odoo import Command, http
from odoo.http import request
from odoo.http.stream import content_disposition
from odoo.addons.spreadsheet.controllers.main import SpreadsheetController


class SpreadsheetEditionController(SpreadsheetController):

    @http.route([
        '/spreadsheet/<string:res_model>/<int:res_id>/dispatch',
    ], type='jsonrpc', auth='public', methods=['POST'])
    def dispatch_spreadsheet_data(self, res_model, res_id, **kw):
        cids_str = request.cookies.get('cids', str(request.env.user.company_id.id))
        cids = [int(cid) for cid in cids_str.split('-')]
        spreadsheet = request.env[res_model].browse(res_id).exists().with_context(allowed_company_ids=cids)
        if not spreadsheet:
            raise request.not_found()
        message = kw.get('message')
        access_token = kw.get("access_token")
        is_accepted = spreadsheet._dispatch_spreadsheet_message(message, access_token)
        return {'accepted': is_accepted}

    @http.route([
        '/spreadsheet/data/<string:res_model>/<int:res_id>',
        '/spreadsheet/data/<string:res_model>/<int:res_id>/<access_token>',
    ], type='http', auth='public', methods=['GET'])
    def get_spreadsheet_data(self, res_model, res_id, access_token=None, **kw):
        cids_str = request.cookies.get('cids', str(request.env.user.company_id.id))
        cids = [int(cid) for cid in cids_str.split('-')]
        spreadsheet = request.env[res_model].browse(res_id).exists().with_context(allowed_company_ids=cids)
        if not spreadsheet:
            raise request.not_found()
        body = spreadsheet._get_serialized_spreadsheet_data_body(access_token)
        headers = [
            ('Content-Length', len(body)),
            ('Cache-Control', 'no-store'),
            ('Content-Type', 'application/json; charset=utf-8'),
        ]
        return request.make_response(body, headers)

    @http.route('/spreadsheet/xlsx', type='http', auth="user", methods=["POST"], readonly=True)
    def get_xlsx_file(self, zip_name, files, **kw):
        if not request.env.user.has_group('base.group_allow_export'):
            raise request.not_found()
        if datasources := kw.get("datasources"):
            self._log_spreadsheet_export("download", request.env.uid, json.load(datasources))

        files = json.load(files) if isinstance(files, FileStorage) else json.loads(files)

        content = request.env['spreadsheet.mixin']._zip_xslx_files(files)
        headers = [
            ('Content-Length', len(content)),
            ('Content-Type', 'application/vnd.ms-excel'),
            ('X-Content-Type-Options', 'nosniff'),
            ('Content-Disposition', content_disposition(zip_name))
        ]

        response = request.make_response(content, headers)
        return response

    @http.route('/spreadsheet/<string:res_model>/<int:res_id>/upload_image', methods=['POST'], type='http', auth='user')
    def image_upload(self, ufile, res_model, res_id):
        spreadsheet = request.env[res_model].browse(res_id).exists()
        if not spreadsheet:
            raise request.not_found()
        vals = {
            'name': ufile.filename,
            'raw': ufile.read(),
        }
        attachment = request.env['ir.attachment'].create(vals)
        attachment._post_add_create()
        spreadsheet.spreadsheet_image_ids = [Command.link(attachment.id)]
        attachment.generate_access_token()
        response_body = {
            'id': attachment.id,
            'url': f'/web/image/{attachment.id}?access_token={attachment.access_token}',
        }
        return request.make_json_response(response_body)
