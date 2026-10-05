from http import HTTPStatus
from urllib.parse import urlencode, quote

from odoo.http import Controller, request, route

from odoo.addons.base.models.ir_qweb import keep_query
from .documents import ShareRoute


class DocumentsTokenRedirect(Controller):

    # takes precedence over the more general /odoo/<*> route
    @route(['/odoo/documents/<access_token>'], type='http', auth='public')
    def documents_token_redirect(self, access_token, **kwargs):
        """ Handle direct access to a document with a backend URL (/odoo/documents/<access_token>).

        It redirects to the document either in:
        - the backend if the user is logged and has access to the Documents module
        - or a lightweight version of the backend if the user is logged and has not access
        to the Document module but well to the documents.document model
        - or the document portal otherwise

        Goal: Allow to share directly the backend URL of a document.
        """
        # Public/Portal users use the /documents/<access_token> route
        if not request.env.user._is_internal():
            return request.redirect(
                f'/documents/{quote(access_token, safe="")}?{keep_query("*")}',
                HTTPStatus.TEMPORARY_REDIRECT,
            )

        document_sudo = request.env['documents.document']._from_access_token(access_token, follow_shortcut=False)

        if not document_sudo:
            Redirect = request.env['documents.redirect'].sudo()
            if document_sudo := Redirect._get_redirection(access_token):
                return request.redirect(
                    f'/odoo/documents/{quote(document_sudo.access_token, safe="")}?{keep_query("*")}',
                    HTTPStatus.MOVED_PERMANENTLY,
                )

        # We want (1) the webclient renders the webclient template and load
        # the document action. We also want (2) the router rewrites
        # /odoo/documents/<id> to /odoo/documents/<access-token> in the
        # URL.
        # We redirect on /web to render the normal home template. We add
        # custom fragments so we can load them inside the router and
        # rewrite the URL.
        query = {}
        if request.session.debug:
            query['debug'] = request.session.debug
        fragment = {
           'action': request.env.ref("documents.document_action_preference").id,
           'menu_id': request.env.ref('documents.menu_root').id,
           'model': 'documents.document',
        }
        if document_sudo:
            fragment.update({
                f'documents_init_{key}': value
                for key, value
                in ShareRoute._documents_get_init_data(document_sudo, request.env.user).items()
            })
            if 'documents_init_open_preview' in kwargs:
                fragment['documents_init_open_preview'] = kwargs['documents_init_open_preview']
        return request.redirect(f'/web?{urlencode(query)}#{urlencode(fragment)}')
