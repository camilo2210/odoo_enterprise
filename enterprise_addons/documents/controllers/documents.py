import io
import json
import logging
import pathlib
import zipfile
from collections import defaultdict
from contextlib import ExitStack
from http import HTTPStatus
from typing import NamedTuple
from urllib.parse import quote

from werkzeug.exceptions import BadRequest, Forbidden

from odoo import _, http
from odoo.exceptions import MissingError
from odoo.fields import Domain
from odoo.http import request
from odoo.http.stream import STATIC_CACHE_LONG, content_disposition
from odoo.tools import consteq, replace_exceptions, str2bool
from odoo.tools.mimetypes import fix_filename_extension

from odoo.addons.base.models.ir_qweb import keep_query
from odoo.addons.mail.controllers.attachment import AttachmentController

logger = logging.getLogger(__name__)

try:
    from markdown2 import markdown
except ImportError:
    markdown = None
    logger.warning("markdown2 is not installed, markdown won't be rendered")


class ShareRoute(http.Controller):

    # util methods #################################################################################
    def _max_content_length(self):
        return request.env['documents.document'].get_document_max_upload_limit()

    @classmethod
    def _get_folder_children(cls, folder_sudo):
        if request.env.user._is_public():
            permission_domain = Domain.AND([
                [('is_access_via_link_hidden', '=', False)],
                [('access_via_link', 'in', ('edit', 'view'))],
                # public user cannot access a request, unless access_via_link='edit'
                Domain.OR([
                    [('type', '!=', 'request')],
                    [('access_via_link', '=', 'edit')],
                ]),
            ])
        else:
            permission_domain = Domain('user_permission', '!=', 'none')  # needed for search in sudo

        children_sudo = request.env['documents.document'].sudo().search(
            Domain('folder_id', '=', folder_sudo.id) & permission_domain,
            order='name',
        )

        return children_sudo

    def _make_zip(self, name, documents):
        """
        Create a zip file in memory out of the given ``documents``,
        recursively exploring the folders, get an HTTP response to
        download that zip file.

        :param str name: the name to give to the zip file
        :param odoo.models.Model documents: documents to load in the ZIP
        :return: a http response to download the zip file
        """
        class Item(NamedTuple):
            path: str
            content: str

        seen_folders = set()  # because of shortcuts, we can have loops
        # many documents can have the same name
        seen_names = defaultdict(int)

        def unique(pathname):
            # files inside a zip can not have the same name
            # (files in the documents application can)
            seen_names[pathname] += 1
            if seen_names[pathname] <= 1:
                return pathname

            ext = ''.join(pathlib.Path(pathname).suffixes)
            return f'{pathname.removesuffix(ext)}-{seen_names[pathname]}{ext}'

        def make_zip_item(document, folder):
            if document.type == 'url':
                raise ValueError("cannot create a zip item out of an url")
            if document.type == 'folder':
                document_name = document.name.replace('/', '_')
                # it is the ending slash that makes it appears as a
                # folder inside the zip file.
                return Item(unique(f'{folder.path}{document_name}') + '/', '')
            try:
                stream = self._documents_content_stream(document.shortcut_document_id or document)
                download_name = stream.download_name.replace('/', '_')
            except (ValueError, MissingError):
                return None  # skip
            return Item(unique(f'{folder.path}{download_name}'), stream.read())

        def generate_zip_items(documents_sudo, folder):
            documents_sudo = documents_sudo.sorted(lambda d: d.id)

            yield from (
                item
                for doc in documents_sudo
                if doc.type == 'binary'
                if (item := make_zip_item(doc, folder)) is not None
            )
            for folder_sudo in documents_sudo:
                if folder_sudo.type != 'folder' or folder_sudo in seen_folders:
                    continue
                seen_folders.add(folder_sudo)

                yield (sub_folder := make_zip_item(folder_sudo, folder))
                for sub_document_sudo in self._get_folder_children(folder_sudo):
                    yield from generate_zip_items(sub_document_sudo, sub_folder)

        # TODO: zip on-the-fly while streaming instead of loading the
        #       entire zip in memory and sending it all at once.

        stream = io.BytesIO()
        root_folder = Item('', '')
        try:
            with zipfile.ZipFile(stream, 'w') as doc_zip:
                for (path, content) in generate_zip_items(documents, root_folder):
                    doc_zip.writestr(path, content, compress_type=zipfile.ZIP_DEFLATED)
        except zipfile.BadZipfile:
            logger.exception("BadZipfile exception")

        content = stream.getvalue()
        headers = [
            ('Content-Type', 'zip'),
            ('X-Content-Type-Options', 'nosniff'),
            ('Content-Length', len(content)),
            ('Content-Disposition', content_disposition(name))
        ]
        return request.make_response(content, headers)

    # Download & upload routes #####################################################################
    @http.route('/documents/pdf_split', type='http', methods=['POST'], auth="user")
    def pdf_split(self, new_files=None, ufile=None, archive=False, vals=None):
        """Used to split and/or merge pdf documents.

        The data can come from different sources: multiple existing documents
        (at least one must be provided) and any number of extra uploaded files.

        :param new_files: the array that represents the new pdf structure:
            [{
                'name': 'New File Name',
                'new_pages': [{
                    'old_file_type': 'document' or 'file',
                    'old_file_index': document_id or index in ufile,
                    'old_page_number': 5,
                }],
            }]
        :param ufile: extra uploaded files that are not existing documents
        :param archive: whether to archive the original documents
        :param vals: values for the create of the new documents.
        """
        vals = json.loads(vals)
        new_files = json.loads(new_files)
        # find original documents
        document_ids = set()
        for new_file in new_files:
            for page in new_file['new_pages']:
                if page['old_file_type'] == 'document':
                    document_ids.add(page['old_file_index'])
        documents = request.env['documents.document'].browse(document_ids)
        documents.check_access('read')

        with ExitStack() as stack:
            files = request.httprequest.files.getlist('ufile')
            open_files = [stack.enter_context(io.BytesIO(file.read())) for file in files]

            # merge together data from existing documents and from extra uploads
            document_id_index_map = {}
            current_index = len(open_files)
            for document in documents:
                open_files.append(stack.enter_context(document.raw.open()))
                document_id_index_map[document.id] = current_index
                current_index += 1

            # update new_files structure with the new indices from documents
            for new_file in new_files:
                for page in new_file['new_pages']:
                    if page.pop('old_file_type') == 'document':
                        page['old_file_index'] = document_id_index_map[page['old_file_index']]

            # apply the split/merge
            new_documents = documents._pdf_split(new_files=new_files, open_files=open_files, vals=vals)

        # archive original documents if needed
        if archive == 'true':
            documents.write({'active': False})

        response = request.make_response(json.dumps(new_documents.ids), [('Content-Type', 'application/json')])
        return response

    @http.route(['/my/documents', '/documents/<access_token>'], type='http', auth='public')
    def documents_home(self, access_token='', member_signup_token=None, member_id=None):
        document_sudo = request.env['documents.document']._from_access_token(access_token)

        if not document_sudo:
            Redirect = request.env['documents.redirect'].sudo()
            if document_sudo := Redirect._get_redirection(access_token):
                return request.redirect(
                    f'/documents/{quote(document_sudo.access_token, safe="")}?{keep_query("*")}',
                    HTTPStatus.MOVED_PERMANENTLY,
                )

        if request.env.user._is_public():
            return self._documents_render_public_view(document_sudo, access_token, member_signup_token, member_id)
        elif request.env.user._is_portal():
            return self._documents_render_portal_view(document_sudo)
        else:  # assume internal user
            # Internal users use the /odoo/documents/<access_token> route
            return request.redirect(
                f'/odoo/documents/{quote(access_token, safe="")}?{keep_query("*")}',
                HTTPStatus.TEMPORARY_REDIRECT,
            )

    def _documents_render_public_view(self, document_sudo, access_token, member_signup_token, member_id):
        """Render the document page for the public user.

        :param document_sudo: The document found with the token
        :param access_token: The access_token of document
            (in case it's in access_via_link = none, to redirect
            the user after the sign-up)
        :param member_signup_token: The invitation token if any, so the
            user can create an account linked to the partner set on
            the member
        :param member_id: The ID of the `documents.access`
        """
        target_sudo = document_sudo.shortcut_document_id
        if (
            target_sudo
            and target_sudo.access_via_link != 'none'
            and not target_sudo.is_access_via_link_hidden
        ):
            return request.redirect(
                f'/odoo/documents/{quote(target_sudo.access_token, safe="")}?{keep_query("*")}')
        if target_sudo:
            return request.render('documents.not_available', status=404)

        # get the signup URL if the token member is valid
        # (even if the token is expired, to show an error page)
        member_sudo = signup_url = None
        if member_id and member_signup_token:
            member_sudo = request.env['documents.access']._get_member_from_token(
                int(member_id), member_signup_token)
            if member_sudo and not member_sudo.partner_id.user_ids:
                signup_url = f'/documents/signup/{access_token}?{keep_query("*")}'

        if not document_sudo and member_sudo and signup_url:
            # Document requires a member to access (not "access_via_link")
            # and we have a signup token -> redirect user to signup
            return request.redirect(signup_url)
        if not document_sudo:
            # the document is not accessible via link
            # or the user already registered using the member token and is logged out
            return request.render('documents.not_available', status=404)
        if document_sudo.type == 'url':
            return request.redirect(
                document_sudo.url, code=HTTPStatus.TEMPORARY_REDIRECT, local=False)
        render_vals = {'quote': lambda v: quote(v, safe=''), 'signup_url': signup_url}
        if document_sudo.type == 'binary':
            return request.render('documents.share_file', {'document': document_sudo, **render_vals})
        if document_sudo.type == 'request':
            return request.render('documents.document_request_page', {'document': document_sudo, 'quote': lambda v: quote(v, safe='')})
        if document_sudo.type == 'folder':
            sub_documents_sudo = ShareRoute._get_folder_children(document_sudo)
            return request.render('documents.public_folder_page', {
                'folder': document_sudo,
                'documents': sub_documents_sudo,
                'subfolders': {
                    sub_folder_sudo.id: ShareRoute._get_folder_children(sub_folder_sudo)
                    for sub_folder_sudo in sub_documents_sudo
                    if sub_folder_sudo.type == 'folder'
                },
                **render_vals,
            })
        raise NotImplementedError(f"unknown document type {document_sudo.type}")

    def _documents_render_portal_view(self, document):
        """ Render the portal version (stripped version of the backend Documents app). """
        # We build the session information necessary for the web client to load
        session_info = request.env['ir.http'].session_info()

        session_info.update(
            user_companies={
                'current_company': request.env.company.id,
                'allowed_companies': {
                    request.env.company.id: {
                        'id': request.env.company.id,
                        'name': request.env.company.name,
                    },
                },
            },
            documents_init=self._documents_get_init_data(document, request.env.user),
        )

        return request.render(
            'documents.document_portal_view',
            {'session_info': session_info},
        )

    @http.route('/documents/signup/<access_token>', type='http', auth='public')
    def documents_signup(self, access_token, member_signup_token, member_id):
        """Build the signup URL for the given public member.

        We use a custom route for it, so we don't generate the signup
        token if the user doesn't try to register
        (see @_get_signup_url_for_action).

        :param access_token: Token of the document (used to redirect
            the user after they signed up)
        :param member_signup_token: Token of the `documents.access`
        :param member_id: ID of the `documents.access`
        """
        if not member_id or not member_signup_token or not access_token:
            raise BadRequest()

        # need to get the document from the member, because `_from_access_token`
        # won't return the document if it's in `access_via_link == 'none'`
        member_sudo = request.env['documents.access']._get_member_from_token(
            int(member_id), member_signup_token)
        if (
            not member_sudo
            or not member_sudo._is_signup_available()
            or not consteq(access_token, member_sudo.document_id.access_token)
        ):
            if self.env['res.users'].sudo()._get_signup_invitation_scope() != 'b2c':
                # signup has been disabled after the email has been sent
                return request.render('documents.not_available', status=404)
            return request.render('documents.invitation_expired', status=404)

        member_sudo.partner_id.signup_get_auth_param()
        redirect_url = member_sudo.partner_id._get_signup_url_for_action(
            url=f'/documents/{quote(access_token, safe="")}?{keep_query("*")}')[member_sudo.partner_id.id]
        return request.redirect(redirect_url)

    @classmethod
    def _documents_get_init_data(cls, document, user):
        """ Get initialization data to restore the interface on the selected document. """
        if not document or not user:
            return {}

        document.ensure_one()
        documents_init = {'user_folder_id': document.user_folder_id, 'document_id': document.id}
        if not document.active:
            pass
        # Shortcuts to archived folders behave like binary documents because these folders cannot be browsed.
        elif document.type == "folder" and (not document.shortcut_document_id or document.shortcut_document_id.active):
            documents_init = {'user_folder_id': str(document.id)}
        elif document.type == 'binary':
            documents_init['open_preview'] = True
        return documents_init

    @http.route('/documents/avatar/<access_token>',
                type='http', auth='public', readonly=True)
    def documents_avatar(self, access_token):
        """Show the avatar of the document's owner, or the avatar placeholder.

        :param access_token: the access token to the document record
        """
        partner_sudo = request.env['documents.document']._from_access_token(access_token, skip_log=True).owner_id.partner_id
        return request.env['ir.binary']._get_image_stream_from(
            partner_sudo, 'avatar_128', placeholder=partner_sudo._avatar_get_placeholder_path()
        ).get_response(as_attachment=False)

    @http.route('/documents/content/<access_token>',
                type='http', auth='public', readonly=True)
    def documents_content(self, access_token, download=True):
        """Serve the file of the document.

        :param access_token: the access token to the document record
        :param download: whether to download the document on the user's
            file system or to preview the document within the browser
        """
        document_sudo = request.env['documents.document']._from_access_token(access_token, skip_log=True)
        if not document_sudo:
            Redirect = request.env['documents.redirect'].sudo()
            if document_sudo := Redirect._get_redirection(access_token):
                return request.redirect(
                    f'/odoo/documents/{quote(document_sudo.access_token, safe="")}',
                    HTTPStatus.MOVED_PERMANENTLY,
                )
            raise request.not_found()
        if document_sudo.type == 'url':
            return request.redirect(
                document_sudo.url, code=HTTPStatus.TEMPORARY_REDIRECT, local=False)
        if document_sudo.type == 'folder':
            return self._make_zip(
                f'{document_sudo.name}.zip',
                self._get_folder_children(document_sudo),
            )
        if document_sudo.type == 'request':
            raise request.not_found()
        if document_sudo.type == 'binary':
            with replace_exceptions(ValueError, by=BadRequest):
                download = str2bool(download)
            with replace_exceptions(ValueError, MissingError, by=request.not_found()):
                stream = self._documents_content_stream(document_sudo)
            return stream.get_response(as_attachment=download)
        e = f"unknown document type {document_sudo.type!r}"
        raise NotImplementedError(e)

    def _documents_content_stream(self, document_sudo):
        return request.env['ir.binary']._get_stream_from(document_sudo)

    @http.route('/documents/redirect/<access_token>', type='http', auth='public', readonly=True)
    def documents_redirect(self, access_token):
        return request.redirect(f'/odoo/documents/{quote(access_token, safe="")}', HTTPStatus.MOVED_PERMANENTLY)

    @http.route('/documents/touch/<access_token>', type='jsonrpc', auth='user')
    def documents_touch(self, access_token):
        doc = request.env['documents.document']._from_access_token(access_token)
        if doc.env.context.get('document_newly_accessible'):
            return {'reload': True}
        return {}

    @http.route(['/documents/thumbnail/<access_token>',
                 '/documents/thumbnail/<access_token>/<int:width>x<int:height>'],
                type='http', auth='public', readonly=True)
    def documents_thumbnail(self, access_token, width='0', height='0', unique=''):
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
        document_sudo = request.env['documents.document']._from_access_token(access_token, skip_log=True)
        return request.env['ir.binary']._get_image_stream_from(
            document_sudo, 'thumbnail', width=width, height=height
        ).get_response(as_attachment=False, **send_file_kwargs)

    @http.route(['/documents/document/<int:document_id>/update_thumbnail'], type='jsonrpc', auth='user')
    def documents_update_thumbnail(self, document_id, thumbnail):
        """Update the thumbnail of the document (after it has been generated by the browser).

        We update the thumbnail in SUDO, after checking the read access, so it will work
        if the user that generates the thumbnail is not the user who uploaded the document.
        """
        document = request.env['documents.document'].browse(document_id)
        document.check_access('read')
        if document.thumbnail_status != 'client_generated':
            return
        document.sudo().write({
            'thumbnail': thumbnail,
            'thumbnail_status': 'present' if thumbnail else 'error',
        })

    @http.route(['/documents/zip'], type='http', auth='user')
    def documents_zip(self, file_ids, zip_name, **kw):
        """Select many files / folders in the interface and click on download.

        :param file_ids: if of the files to zip.
        :param zip_name: name of the zip file.
        """
        ids_list = [int(x) for x in file_ids.split(',')]
        documents = request.env['documents.document'].browse(ids_list)
        documents.check_access('read')
        return self._make_zip(zip_name, documents)

    @http.route([
        '/document/download/all/<int:share_id>/<access_token>',
        '/document/download/all/<access_token>'], type='http', auth='public')
    def documents_download_all_legacy(self, access_token=None, share_id=None):
        logger.warning("Deprecated since Odoo 18. Please access /documents/content/<access_token> instead.")
        return request.redirect(f'/documents/content/{quote(access_token or "", safe="")}', HTTPStatus.MOVED_PERMANENTLY)

    @http.route([
        '/document/share/<int:share_id>/<token>',
        '/document/share/<token>'], type='http', auth='public')
    def share_portal(self, share_id=None, token=None):
        logger.warning("Deprecated since Odoo 18. Please access /odoo/documents/<access_token> instead.")
        return request.redirect(f'/odoo/documents/{quote(token or "", safe="")}', code=HTTPStatus.MOVED_PERMANENTLY)

    @http.route(['/documents/upload/', '/documents/upload/<access_token>'],
                type='http', auth='public', methods=['POST'],
                max_content_length=_max_content_length)
    def documents_upload(
        self,
        ufile,
        access_token='',
        user_folder_id='',
        owner_id='',
        partner_id='',
        res_id='',
        res_model=False,
        allowed_company_ids='',
        active_model=''
    ):
        """
        Replace an existing document or create new ones.

        :param ufile: a list of multipart/form-data files.
        :param access_token: the access token to a folder in which to
            create new documents, or the access token to an existing
            document where to upload/replace its attachment.
            A falsy value means no folder_id and is allowed to
            enable authorized users to upload at the root of
            user_folder_id (My Drive for internal users, Company for
            documents managers)
        :param owner_id, partner_id, res_id, res_model: field values
            when creating new documents, for internal users only
        """
        if active_model:
            request.update_context(active_model=active_model)
        if allowed_company_ids:
            request.update_context(allowed_company_ids=json.loads(allowed_company_ids))
        if access_token and user_folder_id or not access_token and user_folder_id not in {'COMPANY', 'MY'}:
            raise BadRequest("Incorrect token/user_folder_id values")
        is_internal_user = request.env.user._is_internal()
        if is_internal_user and not access_token:
            document_sudo = request.env['documents.document'].sudo()
        else:
            document_sudo = request.env['documents.document']._from_access_token(access_token)
            if (
                not document_sudo
                or (document_sudo.user_permission != 'edit'
                    and document_sudo.access_via_link != 'edit')
                or document_sudo.type not in ('binary', 'request', 'folder')
            ):
                raise request.not_found()

        files = request.httprequest.files.getlist('ufile')
        if not files:
            raise BadRequest("missing files")
        if len(files) > 1 and document_sudo.type not in (False, 'folder', 'request'):
            raise BadRequest("cannot save multiple files inside a single document")

        if is_internal_user:
            with replace_exceptions(ValueError, by=BadRequest):
                owner_id = int(owner_id) if owner_id else request.env.user.id if not user_folder_id else None
                partner_id = int(partner_id) if partner_id else None
                res_id = int(res_id) if res_id else False
        elif owner_id or partner_id or res_id or res_model:
            raise Forbidden("only internal users can provide field values")
        else:
            owner_id = document_sudo.owner_id.id if request.env.user.is_public else request.env.user.id
            partner_id = None
            res_model = False
            res_id = False

        previous_attachment_id = document_sudo.attachment_id
        document_ids = self._documents_upload(
            document_sudo, files, owner_id, user_folder_id, partner_id, res_id, res_model)
        if document_sudo.type != 'folder' and len(document_ids) == 1:
            document_sudo = document_sudo.browse(document_ids)

        if request.env.user._is_public():
            if document_sudo.type == 'folder' or previous_attachment_id:
                return request.redirect(document_sudo.access_url)
            return request.redirect('/documents/upload/success')
        else:
            return request.make_json_response(document_ids)

    def _documents_upload(self,
            document_sudo, files, owner_id, user_folder_id, partner_id, res_id, res_model):
        """ Replace an existing document or upload a new one. """
        is_internal_user = request.env.user._is_internal()

        document_ids = []
        AttachmentSudo = request.env["ir.attachment"].sudo().with_context(image_no_postprocess=True)

        if document_sudo.type in ('binary', 'request'):
            if document_sudo.type == 'request' and len(files) > 1:
                # duplicate the requests for all files we upload
                copy_vals = {"request_activity_id": False, "owner_id": document_sudo.owner_id.id}
                documents_sudo = [
                    document_sudo,
                    *(document_sudo._copy_with_access(copy_vals) for __ in range(len(files) - 1)),
                ]
                # duplicate the shortcuts to the request
                for new_document_sudo in documents_sudo[1:]:
                    # for each new document, we need to duplicate the shortcuts
                    for owner, shortcuts in document_sudo.shortcut_ids.grouped("owner_id").items():
                        shortcuts._copy_with_access({
                            "shortcut_document_id": new_document_sudo.id,
                            "owner_id": owner.id,
                        })

            else:
                documents_sudo = [document_sudo]
                files = [files[0]]

            for file, doc_sudo in zip(files, documents_sudo, strict=True):
                if is_internal_user:
                    # Trust the provided filename and content-type.
                    attachment_sudo = AttachmentSudo._upload_file(file, {
                        'name': file.filename,
                        'mimetype': file.content_type,
                    })
                else:
                    # Portal user, use neither the filename extension nor the content-type,
                    # use guess_mimetype on the content and fix the filename accordingly.
                    attachment_sudo = AttachmentSudo._upload_file(file, {'name': 'upload.bin'})
                    attachment_sudo.name = fix_filename_extension(
                        file.filename, attachment_sudo.mimetype)
                attachment_sudo.with_context(no_document=True).write({
                    'res_model': doc_sudo.res_model or 'documents.document',
                    'res_id': doc_sudo.res_id if doc_sudo.res_model else doc_sudo.id,
                })
                values = {'attachment_id': attachment_sudo.id}
                if doc_sudo.type == 'request' and doc_sudo.access_via_link == 'edit':
                    values['access_via_link'] = 'view'
                self._documents_upload_create_write(doc_sudo, values)
                document_ids.append(doc_sudo.id)
        else:
            folder_sudo = document_sudo
            location = {'user_folder_id': user_folder_id} if user_folder_id else {'folder_id': folder_sudo.id}
            for file in files:
                if is_internal_user:
                    # Trust the provided filename and content-type.
                    attachment_sudo = AttachmentSudo._upload_file(file, {
                        'name': file.filename,
                        'mimetype': file.content_type,
                    })
                else:
                    # Portal user, use neither the filename extension nor the content-type,
                    # use guess_mimetype on the content and fix the filename accordingly.
                    attachment_sudo = AttachmentSudo._upload_file(file, {'name': 'upload.bin'})
                    attachment_sudo.name = fix_filename_extension(
                        file.filename, attachment_sudo.mimetype)

                document_sudo = self._documents_upload_create_write(folder_sudo, {
                    'attachment_id': attachment_sudo.id,
                    'type': 'binary',
                    'access_via_link': 'none' if folder_sudo.access_via_link in (False, 'none') else 'view',
                    **location,
                    'owner_id': owner_id,
                } | (  # Avoid to force res_model, res_id as it can be inherited from the folder where it is uploaded
                    {'res_model': res_model or False, 'res_id': res_id} if res_model or res_id
                    else {}
                ) | (
                    {'partner_id': partner_id} if partner_id is not None else {}
                ))
                document_ids.append(document_sudo.id)

            # Make sure uploader can access documents in "Company"
            document_sudo.filtered(
                lambda d: not d.folder_id and d.owner_id == request.env.ref('base.user_root')
            ).action_update_access_rights(partners={request.env.user.partner_id: ('edit', False)})

        return document_ids

    def _documents_upload_create_write(self, document_sudo, vals):
        """
        The actual function that either write vals on a binary document
        or create a new document with vals inside a folder document.
        """
        if document_sudo.type in ('binary', 'request'):
            # requests messages are handled inside write, binary type documents are handled here
            if document_sudo.type != 'request' or self.env.user == document_sudo.create_uid:
                document_sudo.message_post(body=_("Attachment updated by %(user)s", user=request.env.user.name))
            document_sudo.write(vals)
        else:
            vals.setdefault('folder_id', document_sudo.id)
            document_sudo = document_sudo.create(vals)

        return document_sudo

    @http.route('/documents/upload/success', type='http', auth='public')
    def documents_upload_success(self):
        return request.render('documents.document_request_done_page')

    @http.route('/documents/upload_traceback', type='http', methods=['POST'], auth='user')
    def documents_upload_traceback(self, ufile, max_content_length=1 << 20):  # 1MiB
        if not request.env.user._is_internal():
            raise Forbidden()

        folder_sudo = request.env['documents.document']._get_traceback_folder_sudo()

        files = request.httprequest.files.getlist('ufile')
        if not files:
            raise BadRequest("missing files")
        if len(files) > 1:
            raise BadRequest("This route only accepts one file at a time.")

        traceback_sudo = self._documents_upload_create_write(folder_sudo, {
            'attachment_id': request.env['ir.attachment']._upload_file(files[0], {
                'name': fix_filename_extension(files[0].filename, 'text/plain'),
                'mimetype': 'text/plain',
            }).id,
            'type': 'binary',
            'access_internal': 'none',
            'access_via_link': 'view',
            'folder_id': folder_sudo.id,
            'owner_id': False,
        })

        return request.make_json_response([traceback_sudo.access_url])


class DocumentsAttachmentController(AttachmentController):

    @http.route()
    def mail_attachment_upload(self, *args, **kw):
        """ Override to prevent the creation of a document when uploading
            an attachment from an activity already linked to a document."""
        if kw.get('activity_id'):
            document = request.env['documents.document'].search([('request_activity_id', '=', int(kw['activity_id']))])
            if document:
                request.update_context(no_document=True)
        return super().mail_attachment_upload(*args, **kw)

    @http.route(
        "/documents/content/pdf_first_page/<access_token>",
        methods=["GET"],
        type="http",
        auth="public",
        readonly=True,
    )
    def document_attachment_pdf_first_page(self, access_token=None):
        """Returns the first page of a pdf."""
        document_sudo = request.env['documents.document']._from_access_token(access_token, skip_log=True)
        if not document_sudo.attachment_id:
            raise request.not_found()
        return self._get_pdf_first_page_response(document_sudo.attachment_id)

    @http.route(['/documents/render_text/<access_token>'],
                type='http', auth='public', readonly=True)
    def documents_render_text(self, access_token, head=False, unique=False):
        """Render the text content for preview and thumbnail.

        Render the document content / preview for
        - Simple text
        - HTML
        - XML
        - JSON
        - Markdown
        - Email

        :param access_token: the access token to the document record
        :param head: show the thumbnail (first 4kiB) of text-like documents
        :param str unique: Indicates if the response can be cached
        """
        document_sudo = request.env['documents.document']._from_access_token(access_token, skip_log=True)
        if not document_sudo:
            raise request.not_found()
        if document_sudo.type != 'binary':
            e = f"bad document type: expected a file (binary) document, found a {document_sudo.type} document"
            raise BadRequest(e)
        if not document_sudo.attachment_id:
            raise request.not_found()
        if document_sudo.attachment_id.mimetype == 'application/documents-email':
            response = request.render("documents.content_email", {
                'content': document_sudo.attachment_id.raw.content.decode(errors='replace'),
                'is_thumbnail': str2bool(head, False),
            })
            immutable = bool(unique) and unique == document_sudo.attachment_id.checksum
            return self._set_render_with_headers(response, immutable)

        return self._render_text_attachment(document_sudo.attachment_id, str2bool(head, False), unique)
