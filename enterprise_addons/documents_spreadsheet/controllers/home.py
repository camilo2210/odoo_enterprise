# Part of Odoo. See LICENSE file for full copyright and licensing details.

from http import HTTPStatus
from urllib.parse import quote, urlencode

from odoo.http import Controller, request, route


class SpreadsheetTokenRedirect(Controller):
    # access_token have at least 24 characters: 22 char token + "o" + hex record id.
    @route([
        '/odoo/spreadsheet/<string(minlength=24):access_token>',
        '/odoo/<path:subpath>/spreadsheet/<string(minlength=24):access_token>',
    ], type='http', auth='public')
    def spreadsheet_token_redirect(self, access_token, subpath=None, **kwargs):
        """Handle direct access to a spreadsheet through a backend URL.

        Examples:
        - /odoo/spreadsheet/<access_token>
        - /odoo/crm/spreadsheet/<access_token>
        - /odoo/surveys/<id>/spreadsheet/<access_token>
        """
        if not request.env.user._is_internal():
            sheet_id = kwargs.pop('sid', None)
            url = f'/documents/{quote(access_token, safe="")}'
            if kwargs:
                url = f'{url}?{urlencode(kwargs)}'
            if sheet_id:
                url = f'{url}#{urlencode({"sid": sheet_id})}'
            return request.redirect(url, HTTPStatus.TEMPORARY_REDIRECT)

        # Grant shared-link access and resolve the spreadsheet id.
        document_sudo = request.env['documents.document']._from_access_token(
            access_token, follow_shortcut=False
        )

        # Redirect to the id-based URL handled by the regular webclient. Keeping
        # the token in the query lets the client router restore the shareable URL.
        path = f'/odoo/{subpath}/spreadsheet' if subpath else '/odoo/spreadsheet'
        kwargs['access_token'] = access_token
        return request.redirect(
            f'{path}/{document_sudo.id}?{urlencode(kwargs)}',
            HTTPStatus.TEMPORARY_REDIRECT,
        )
