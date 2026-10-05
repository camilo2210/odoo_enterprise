# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re
from urllib.parse import quote

from werkzeug.exceptions import BadRequest

from odoo.http import request, route
from odoo.http.stream import STATIC_CACHE_LONG
from odoo.tools import replace_exceptions

from odoo.addons.documents.controllers.documents import ShareRoute

# ends with .osheet.json or .osheet (6).json
SPREADSHEET_RE = re.compile(r'\.osheet(\s?\(\d+\))?\.json$')


class SpreadsheetShareRoute(ShareRoute):
    def _documents_render_public_view(self, document_sudo, access_token, member_signup_token, member_id):
        if document_sudo.handler in ("spreadsheet", "frozen_spreadsheet"):
            return self._documents_render_portal_view(document_sudo)

        return super()._documents_render_public_view(document_sudo, access_token, member_signup_token, member_id)

    def _documents_render_portal_view(self, document):
        if document.handler not in ("spreadsheet", "frozen_spreadsheet"):
            return super()._documents_render_portal_view(document)
        can_write = document.access_via_link == "edit" or document.sudo(False).has_access("write")
        return request.render(
            "spreadsheet.public_spreadsheet_layout",
            {
                "spreadsheet_name": document.name,
                "share": document,
                "is_frozen": document.handler == "frozen_spreadsheet",
                "session_info": request.env["ir.http"].session_info(),
                "spreadsheet_public_component": "spreadsheet_edition.PublicSpreadsheet",
                "spreadsheet_icon_src": "/spreadsheet/static/description/icon.svg",
                "props": {
                    "dataUrl": f"/spreadsheet/data/{document._name}/{document.id}/{quote(document.access_token, safe='')}",
                    "resModel": document._name,
                    "resId": document.id,
                    "accessToken": document.access_token,
                    "mode": "normal" if can_write else "readonly",
                },
            },
        )

    def _documents_content_stream(self, document_sudo):
        """
        Use the ``excel_export`` field instead of ``raw`` when
        downloading frozen spreadsheets.
        """
        if document_sudo.handler == 'frozen_spreadsheet':
            return request.env['ir.binary']._get_stream_from(document_sudo, 'excel_export')
        if document_sudo.handler == 'spreadsheet':
            e = "non-frozen spreadsheets have no content"
            raise ValueError(e)
        return super()._documents_content_stream(document_sudo)

    def _documents_upload_create_write(self, *args, **kwargs):
        """Set the correct handler when uploading a spreadsheet"""
        document_sudo = super()._documents_upload_create_write(*args, **kwargs)
        if (document_sudo.name
            and SPREADSHEET_RE.search(document_sudo.name)
            and document_sudo.mimetype == 'application/json'
            ):
            document_sudo.handler = 'spreadsheet'
            document_sudo._check_spreadsheet_data()
        return document_sudo

    @route(['/documents/display_thumbnail/<access_token>',
            '/documents/display_thumbnail/<access_token>/<int:width>x<int:height>'],
           type='http', auth='public', readonly=True)
    def documents_display_thumbnail(self, access_token, width='0', height='0', unique=''):
        """Show the thumbnail of the document, or a placeholder.

        :param access_token: the access token to the document record
        :param width: resize the thumbnail to this maximum width
        :param height: resize the thumbnail to this maximum height
        :param unique: force storing the file in the browser cache, best
            used with the checksum of the attachment
        """
        with replace_exceptions(ValueError, by=BadRequest):
            width = int(width)
            height = int(height)
        send_file_kwargs = {}
        if unique:
            send_file_kwargs['immutable'] = True
            send_file_kwargs['max_age'] = STATIC_CACHE_LONG
        spreadsheet_sudo = request.env['documents.document']._from_access_token(access_token, skip_log=True)
        return request.env['ir.binary']._get_image_stream_from(
            spreadsheet_sudo, 'display_thumbnail', width=width, height=height
        ).get_response(as_attachment=False, **send_file_kwargs)
