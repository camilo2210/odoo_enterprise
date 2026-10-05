import json
import zipfile
from datetime import timedelta
from http import HTTPStatus
from io import BytesIO
from unittest.mock import patch
from urllib.parse import urlencode

from PIL import Image
from freezegun import freeze_time
from reportlab.pdfgen import canvas
from urllib3.util import parse_url

from odoo import Command, fields
from odoo.http.stream import STATIC_CACHE_LONG
from odoo.tests.common import RecordCapturer, tagged
from odoo.tools import mute_logger
from odoo.tools.image import image_process

from odoo.addons.base.tests.common import HttpCaseWithUserDemo
from odoo.addons.base.tests.files import GIF_RAW
from odoo.addons.documents.tests.test_documents_common import TEXT_RAW, get_document_creation_message
from odoo.addons.mail.tests.common import mail_new_test_user, MailCase

from odoo.addons.documents.controllers.documents import ShareRoute
from odoo.addons.mail.controllers.attachment import AttachmentController


@tagged('post_install', '-at_install')
class TestDocumentsControllers(HttpCaseWithUserDemo, MailCase):
    def _assertPathEqual(self, first, second):
        self.assertEqual(parse_url(first).path, parse_url(second).path)

    def _assertPathIn(self, member, container):
        self.assertIn(parse_url(member).path, {parse_url(expected_url).path for expected_url in container})

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.user_portal = mail_new_test_user(cls.env,
            login='portal_test',
            groups='base.group_portal',
            company_id=cls.env.ref('base.main_company').id,
            name='portal',
            notification_type='email'
        )

        cls.user_manager = mail_new_test_user(cls.env,
            login='manager_test',
            email='manager@example.com',
            groups='documents.group_documents_manager',
            company_id=cls.env.ref('base.main_company').id,
            name='manager',
            notification_type='email'
        )

        # make sure the admin user has an avatar
        cls.user_admin.image_1920 = cls.file_read('base/static/img/partner_admin-image.webp')

        # use the Document app icon as test file
        cls.doc_icon = cls.file_read('documents/static/description/icon.png').content

        Doc = cls.env['documents.document']

        cls.test_activity_type = cls.env['mail.activity.type'].create({
            'name': 'Test Activity Type'
        })

        cls.internal_folder = Doc.create({
            'type': 'folder',
            'name': "internal folder",
            'access_internal': 'edit',
            'access_via_link': 'none',
            'owner_id': cls.user_admin.id,

            'create_activity_option': False,
            'create_activity_type_id': cls.test_activity_type.id,
            'create_activity_summary': 'test summary',
            'create_activity_note': 'test note',
            'create_activity_user_id': cls.user_admin.id,
            'create_activity_date_deadline_range_type': 'days',
            'create_activity_date_deadline_range': 5,
        })
        cls.internal_file = Doc.create({
            'type': 'binary',
            'name': "internal-file.png",
            'access_internal': 'edit',
            'access_via_link': 'none',
            'is_access_via_link_hidden': True,
            'owner_id': cls.user_admin.id,
            'folder_id': cls.internal_folder.id,
            'raw': cls.doc_icon,
        })
        cls.internal_file_textual = Doc.create({
            'type': 'binary',
            'name': "internal-file-textual.txt",
            'access_internal': 'edit',
            'access_via_link': 'none',
            'is_access_via_link_hidden': True,
            'owner_id': cls.user_admin.id,
            'folder_id': cls.internal_folder.id,
            'raw': TEXT_RAW,
        })
        cls.env['ir.config_parameter'].set_str('ir_attachment.location', 'db')  # force storing in the database
        cls.env['ir.config_parameter'].flush_model()
        cls.internal_file_textual_on_db = Doc.create({
            'type': 'binary',
            'name': 'internal-file-textual-on-db.txt',
            'access_internal': 'edit',
            'access_via_link': 'none',
            'is_access_via_link_hidden': True,
            'owner_id': cls.user_admin.id,
            'folder_id': cls.internal_folder.id,
            'raw': TEXT_RAW,
        })
        cls.env['ir.config_parameter'].set_str('ir_attachment.location', None)  # reset storing location
        cls.env['ir.config_parameter'].flush_model()
        cls.internal_hidden = Doc.create({
            'type': 'binary',
            'name': "internal-hidden.png",
            'access_internal': 'none',
            'access_via_link': 'none',
            'owner_id': cls.user_admin.id,
            'folder_id': cls.internal_folder.id,
            'raw': cls.doc_icon,
        })
        cls.internal_request = Doc.with_user(cls.user_manager).create({
            'type': 'request',
            'name': "internal-request.png",
            'access_internal': 'edit',
            'access_via_link': 'none',
            'owner_id': cls.user_admin.id,
            'folder_id': cls.internal_folder.id,
            'requestee_partner_id': cls.user_demo.partner_id.id,
        })
        cls.internal_url = Doc.create({
            'type': 'url',
            'name': "internal url",
            'access_internal': 'edit',
            'access_via_link': 'none',
            'owner_id': cls.user_admin.id,
            'folder_id': cls.internal_folder.id,
            'url': f'{cls.base_url()}/web/health',
        })

        cls.public_folder = Doc.create({
            'type': 'folder',
            'name': "public folder",
            'access_internal': 'edit',
            'access_via_link': 'edit',
            'folder_id': cls.internal_folder.id,
            'owner_id': cls.user_admin.id,
        })
        cls.public_file = Doc.create({
            'type': 'binary',
            'name': "public-file.png",
            'access_internal': 'edit',
            'access_via_link': 'view',
            'owner_id': cls.user_admin.id,
            'folder_id': cls.public_folder.id,
            'raw': cls.doc_icon,
        })
        cls.public_file_textual = Doc.create({
            'type': 'binary',
            'name': "public-file-textual.txt",
            'access_internal': 'edit',
            'access_via_link': 'view',
            'owner_id': cls.user_admin.id,
            'folder_id': cls.public_folder.id,
            'raw': TEXT_RAW,
        })
        cls.public_request = Doc.with_user(cls.user_manager).create({
            'type': 'request',
            'name': "public-request.png",
            'access_internal': 'edit',
            'access_via_link': 'edit',
            'owner_id': cls.user_admin.id,
            'folder_id': cls.public_folder.id,
            'requestee_partner_id': cls.env['res.partner'].create({'name': "Requestee"}).id,
        })
        cls.public_url = Doc.create({
            'type': 'url',
            'name': "public url",
            'access_internal': 'edit',
            'access_via_link': 'view',
            'owner_id': cls.user_admin.id,
            'folder_id': cls.public_folder.id,
            'url': f'{cls.base_url()}/web/health',
        })
        cls.internal_shortcut = cls.internal_file.action_create_shortcut(str(cls.public_folder.id))
        cls.missing_file = Doc.new()

        # Make so the demo and portal users already visited all
        # documents, so that it doesn't attempt to create the
        # documents.access record inside a read-only controller.
        # It also makes so the portal user can list those files.
        now = fields.Datetime.now()
        cls.env['documents.access'].create([
            {
                'document_id': doc.id,
                'partner_id': partner.id,
                'last_access_date': now
            }
            for doc in [
                cls.internal_folder, cls.internal_file, cls.internal_shortcut, cls.internal_hidden,
                cls.internal_request, cls.internal_url, cls.public_folder,
                cls.internal_file_textual, cls.internal_file_textual_on_db,
                cls.public_file, cls.public_request, cls.public_url, cls.public_file_textual,
            ]
            for partner in [
                cls.user_demo.partner_id,
                cls.user_portal.partner_id,
            ]
        ])

    def test_doc_ctrl_avatar(self):
        avatar_128 = self.user_admin.avatar_128.content
        placeholder = image_process(
            self.user_admin.partner_id._avatar_get_placeholder(),
            size=(128, 128),
        )

        for document, user, status, content, filename in [
            (        self.missing_file,   None, 200, placeholder, 'avatar_grey.png'),
            (         self.public_file,   None, 200,  avatar_128, '"Mitchell Admin.webp"'),
            (       self.internal_file,   None, 200, placeholder, 'avatar_grey.png'),
            (   self.internal_shortcut,   None, 200, placeholder, 'avatar_grey.png'),
            (   self.internal_shortcut, 'demo', 200,  avatar_128, '"Mitchell Admin.webp"'),
            (       self.internal_file, 'demo', 200,  avatar_128, '"Mitchell Admin.webp"'),
            # keep it last the response is reused outside the loop
        ]:
            url = f'/documents/avatar/{document.access_token}'
            session = self.authenticate(user, user)
            with self.subTest(document=document.name, user=user):
                res = self.url_open(url)
                self.assertEqual(res.status_code, status)
                if status == 200:
                    self.assertEqual(
                        res.headers.get('Content-Disposition'),
                        f'inline; filename={filename}')
                    self.assertEqual(res.content, content)
                    self.assertIn('Last-Modified', res.headers)
                    self.assertIn('ETag', res.headers)

        # reuse the last response's ETag/Last-Modified
        assert session.uid == self.user_demo.id
        assert document is self.internal_file
        res = self.url_open(url, headers={
            'If-Modified-Since': res.headers['Last-Modified'],
            'If-None-Match': res.headers['ETag'],
        })
        res.raise_for_status()
        self.assertEqual(res.status_code, HTTPStatus.NOT_MODIFIED)

    def test_doc_ctrl_avatar_portal(self):
        placeholder = image_process(
            self.user_admin.partner_id._avatar_get_placeholder(),
            size=(128, 128),
        )
        self.authenticate('portal_test', 'portal_test')
        access_portal = self.internal_file.access_ids.filtered(
            lambda access: access.partner_id == self.user_portal.partner_id
        ).ensure_one()
        access_portal.role = 'view'

        access_portal.expiration_date = fields.Datetime.now() + timedelta(hours=1)
        res = self.url_open(f'/documents/avatar/{self.internal_file.access_token}')
        res.raise_for_status()
        self.assertEqual(res.content, self.user_admin.avatar_128.content)

        access_portal.expiration_date = fields.Datetime.now() - timedelta(hours=1)
        res = self.url_open(f'/documents/avatar/{self.internal_file.access_token}')
        res.raise_for_status()
        self.assertEqual(res.content, placeholder)

    def test_doc_ctrl_avatar_shortcut(self):
        self.internal_file.action_update_access_rights(
            access_via_link='view',
            is_access_via_link_hidden=False,
        )
        for user in [None, 'demo']:
            with self.subTest(user=user):
                res = self.url_open(f'/documents/avatar/{self.internal_shortcut.access_token}')
                res.raise_for_status()
                self.assertEqual(res.content, self.user_admin.avatar_128.content)

    def test_doc_ctrl_content_binary(self):
        for document, user, dl, status, content in [
            (      self.missing_file,   None,   '1', 404,   "not found"),  # no document
            (     self.internal_file,   None,   '1', 404,   "not found"),  # access_via_link='none'
            ( self.internal_shortcut,   None,   '1', 404,   "not found"),  # access_via_link='none'
            (       self.public_file,   None,   '1', 200, self.doc_icon),  # access_via_link='view'
            (       self.public_file,   None,   '0', 200, self.doc_icon),  # access_via_link='view'
            (       self.public_file,   None, 'bad', 400,     "Use 0/1"),  # int('bad')
            (    self.public_request,   None,   '1', 404,   "not found"),  # no attachment_id
            (     self.internal_file, 'demo',   '1', 200, self.doc_icon),  # access_internal='view'
            (   self.internal_hidden, 'demo',   '1', 404,   "not found"),  # access_internal='none'
            (     self.internal_file, 'demo',   '0', 200, self.doc_icon),  # access_internal='view'
            # keep it last, the response is reused outside the loop
        ]:
            session = self.authenticate(user, user)
            url = f'/documents/content/{document.access_token}?download={dl}'
            with self.subTest(user=user, url=url):
                res = self.url_open(url)
                self.assertEqual(res.status_code, status)
                if status == 200:
                    self.assertEqual(res.content, content)
                    self.assertIn('Last-Modified', res.headers)
                    self.assertIn('ETag', res.headers)
                    self.assertEqual(
                        res.headers.get('Content-Disposition'),
                        ("attachment" if dl == "1" else "inline")
                        + f'; filename={document.name}'
                    )
                else:
                    self.assertIn(content, res.text)

        # reuse the last response's ETag/Last-Modified
        assert session.uid == self.user_demo.id
        assert url == f'/documents/content/{self.internal_file.access_token}?download=0'
        res = self.url_open(url, headers={
            'If-Modified-Since': res.headers['Last-Modified'],
            'If-None-Match': res.headers['ETag'],
        })
        res.raise_for_status()
        self.assertEqual(res.status_code, HTTPStatus.NOT_MODIFIED)  # 304

    def test_doc_ctrl_content_binary_portal(self):
        self.authenticate('portal_test', 'portal_test')
        access_portal = self.internal_file.access_ids.filtered(
            lambda access: access.partner_id == self.user_portal.partner_id
        ).ensure_one()
        access_portal.role = 'view'

        access_portal.expiration_date = fields.Datetime.now() + timedelta(hours=1)
        res = self.url_open(f'/documents/content/{self.internal_file.access_token}')
        res.raise_for_status()
        self.assertEqual(res.content, self.doc_icon)

        access_portal.expiration_date = fields.Datetime.now() - timedelta(hours=1)
        res = self.url_open(f'/documents/content/{self.internal_file.access_token}')
        self.assertEqual(res.status_code, 404)

    def test_doc_ctrl_content_binary_shortcut(self):
        self.authenticate('demo', 'demo')
        res = self.url_open(f'/documents/content/{self.internal_shortcut.access_token}')
        res.raise_for_status()
        self.assertEqual(res.content, self.doc_icon)

        # make so the public user can follow the shortcut
        self.internal_file.action_update_access_rights(
            access_via_link='view',
            is_access_via_link_hidden=False,
        )
        self.authenticate(None, None)
        res = self.url_open(f'/documents/content/{self.internal_shortcut.access_token}')
        res.raise_for_status()
        self.assertEqual(res.content, self.doc_icon)

    def test_doc_ctrl_content_folder(self):
        self.authenticate(None, None)
        res = self.url_open(f'/documents/content/{self.internal_folder.access_token}')
        self.assertEqual(res.status_code, 404)
        res = self.url_open(f'/documents/content/{self.public_folder.access_token}')
        res.raise_for_status()
        self.assertEqual(res.status_code, 200)
        with zipfile.ZipFile(BytesIO(res.content)) as reszip:
            self.assertEqual(reszip.namelist(), ['public-file.png', 'public-file-textual.txt'])
            self.assertEqual(reszip.read('public-file.png'), self.doc_icon)

        self.internal_file.action_update_access_rights(
            access_via_link='view',
            is_access_via_link_hidden=False,
        )
        res = self.url_open(f'/documents/content/{self.public_folder.access_token}')
        res.raise_for_status()
        self.assertEqual(res.status_code, 200)
        with zipfile.ZipFile(BytesIO(res.content)) as reszip:
            self.assertEqual(sorted(reszip.namelist()), ['internal-file.png', 'public-file-textual.txt', 'public-file.png'])
            self.assertEqual(reszip.read('internal-file.png'), self.doc_icon)
            self.assertEqual(reszip.read('public-file.png'), self.doc_icon)
            self.assertEqual(reszip.read('public-file-textual.txt'), TEXT_RAW)

        # check that the name are all unique
        self.public_file.action_create_shortcut(str(self.internal_folder.id))
        self.public_folder.action_create_shortcut(str(self.internal_folder.id))
        self.env['documents.document'].create([{
            'name': 'te/st.tar.gz',  # the `/` in the name should be replaced with `_`
            'folder_id': self.internal_folder.id,
            'access_internal': 'view',
            'raw': b'test',
        } for _ in range(3)] + [{
            'name': self.public_folder.name,
            'folder_id': self.public_folder.folder_id.id,
            'access_internal': 'view',
            'type': 'folder',
        } for _ in range(3)] + [{
            'name': '.hidden',
            'folder_id': self.public_folder.folder_id.id,
            'access_internal': 'view',
            'type': 'folder',
        } for _ in range(2)])

        # add nested folders with `/` in their names
        parent_id = self.public_folder.id
        for i in range(4):
            parent_id = self.env["documents.document"].create({
                'name': f'folder/test/{i}',
                'folder_id': parent_id,
                'type': 'folder',
            }).id

        self.authenticate('demo', 'demo')
        res = self.url_open(f'/documents/content/{self.internal_folder.access_token}')
        res.raise_for_status()
        self.assertEqual(res.status_code, 200)
        expected = {
            'internal-file.png',
            'internal-file-textual.txt',
            'internal-file-textual-on-db.txt',
            'public-file.png',
            'public folder/',
            # already discovered, but it's a shortcut to a file so it's ok
            'public folder/public-file.png',
            'public folder/public-file-textual.txt',
            'public folder/internal-file.png',
            'public folder-2/',
            'public folder-3/',
            'public folder-4/',
            'public folder-5/',
            'te_st.tar.gz',
            'te_st-2.tar.gz',
            'te_st-3.tar.gz',
            '.hidden/',
            '.hidden-2/',
            # the path should be correct, even if the folders have `/` in their names
            'public folder/folder_test_0/',
            'public folder/folder_test_0/folder_test_1/',
            'public folder/folder_test_0/folder_test_1/folder_test_2/',
            'public folder/folder_test_0/folder_test_1/folder_test_2/folder_test_3/',
        }
        with zipfile.ZipFile(BytesIO(res.content)) as reszip:
            self.assertEqual(set(reszip.namelist()), expected)
            self.assertEqual(reszip.read('internal-file.png'), self.doc_icon)

    def test_doc_ctrl_content_url(self):
        self.authenticate(None, None)
        res = self.url_open(f'/documents/content/{self.public_url.access_token}', allow_redirects=False)
        res.raise_for_status()
        self.assertEqual(res.status_code, HTTPStatus.TEMPORARY_REDIRECT)  # 307
        self.assertEqual(res.headers.get('Location'), self.public_url.url)
        res = self.url_open(f'/documents/content/{self.internal_url.access_token}', allow_redirects=False)
        self.assertEqual(res.status_code, 404)

        self.authenticate('demo', 'demo')
        res = self.url_open(f'/documents/content/{self.internal_url.access_token}', allow_redirects=False)
        res.raise_for_status()
        self.assertEqual(res.status_code, HTTPStatus.TEMPORARY_REDIRECT)  # 307
        self.assertEqual(res.headers.get('Location'), self.internal_url.url)

    @mute_logger('odoo.http')
    def test_doc_ctrl_cross_redirection(self):
        docs_url = f'/documents/{self.public_file.access_token}?a=1'
        odoo_url = f'/odoo{docs_url}'
        portal = self.user_portal.login
        demo = self.user_demo.login
        for login, url, code, location in [
            (     None, odoo_url, 307, docs_url),
            (   portal, odoo_url, 307, docs_url),
            (     demo, docs_url, 307, odoo_url),
            (     None, docs_url, 200, ...),
            (   portal, docs_url, 200, ...),
            (     demo, odoo_url, 303, ...),
        ]:
            with self.subTest(login=login, url=url):
                self.authenticate(login, login)
                res = self.url_open(url, allow_redirects=False)
                res.raise_for_status()
                self.assertEqual(res.status_code, code)
                if code == 307:
                    self.assertURLEqual(res.headers.get('Location'), location)

    @mute_logger('odoo.http')
    def test_doc_redirection_partner(self):
        """Test the signup flow when sharing documents."""
        # when we can read the document, we show it, but with a "Sign up" button instead of "Login"
        partner = self.env["res.partner"].create({'name': 'Test'})
        access = self.env["documents.access"].create({
            'document_id': self.public_file.id,
            'role': 'view',
            'partner_id': partner.id,
        })
        member_signup_token = access._get_member_signup_token()
        docs_url = f'/documents/{self.public_file.access_token}?member_signup_token={member_signup_token}&member_id={access.id}'
        self.public_file.access_via_link = 'view'
        res = self.url_open(docs_url)
        self.assertIn(f"/documents/signup/{self.public_file.access_token}", res.text)
        self.assertIn(member_signup_token, res.text)
        self.assertIn('public-file.png', res.text)

        # when we cannot read the document, we redirect to the signup page
        self.public_file.access_via_link = 'none'
        res = self.url_open(docs_url, allow_redirects=False)
        res.raise_for_status()
        redirect_url = res.headers.get('Location') or ''
        self.assertIn('/documents/signup/', redirect_url, f"Invalid redirect URL: {redirect_url}")
        self.assertIn(self.public_file.access_token, redirect_url)

        # test a bad token
        docs_url = f'/documents/{self.public_file.access_token}?member_signup_token=bad_token_{member_signup_token}&member_id={access.id}'
        res = self.url_open(docs_url)
        self.assertIn('This document does not exist', res.text)
        self.assertNotIn(member_signup_token, res.text)
        self.assertIn('/web/login', res.text)

        # expired token
        urls = [
            f'/documents/{self.public_file.access_token}?member_signup_token={member_signup_token}&member_id={access.id}',
            f'/documents/signup/{self.public_file.access_token}?member_signup_token={member_signup_token}&member_id={access.id}',
        ]
        access.expiration_date = fields.Datetime.now() - timedelta(days=1)
        for url in urls:
            res = self.url_open(url)
            self.assertIn('The invitation expired', res.text)

        # remove the role, should invalidate the invitation link
        access.role = False
        access.expiration_date = False
        access.last_access_date = fields.Datetime.now()
        for url in urls:
            res = self.url_open(url)
            self.assertIn('The invitation expired', res.text)

        # the token is valid, and the user registered is logged in
        self.env['res.users'].create({
            'partner_id': partner.id,
            'login': 'test_user',
            'password': 'test_user',
            'group_ids': [Command.set([self.env.ref('base.group_portal').id])],
        })
        self.authenticate('test_user', 'test_user')
        access.role = 'view'
        docs_url = f'/documents/{self.public_file.access_token}?member_signup_token={member_signup_token}&member_id={access.id}'
        res = self.url_open(docs_url)
        self.assertIn(docs_url, res.url)
        self.assertIn('o_documents_portal_view', res.text)

        # the token is valid, but the user registered and is logged out
        # redirect to the login page
        self.authenticate(None, None)
        access.role = 'view'
        res = self.url_open(docs_url)
        self.assertIn('does not exist or is not publicly available', res.text)

        # except if the document is accessible with the link
        self.public_file.access_via_link = 'view'
        res = self.url_open(docs_url)
        self.assertIn('/web/login', res.text)
        self.assertNotIn(member_signup_token, res.text)
        self.assertIn('public-file.png', res.text)
        self.assertNotIn('o_documents_portal_view', res.text)

    def test_doc_render_public_templates(self):
        self.authenticate(None, None)

        # Internal documents
        for doc in (
            self.internal_file,
            self.internal_hidden,
            self.internal_folder,
            self.internal_request,
            self.internal_url,
        ):
            with self.subTest(name=doc.name):
                res = self.url_open(doc.access_url)
                self.assertEqual(res.status_code, 404)
                self.assertIn("does not exist or is not publicly available.", res.text)

        # URL
        res = self.url_open(self.public_url.access_url, allow_redirects=False)
        res.raise_for_status()
        self.assertEqual(res.status_code, HTTPStatus.TEMPORARY_REDIRECT)

        # Folder
        res = self.url_open(self.public_folder.access_url)
        res.raise_for_status()
        self.assertIn(self.public_file.name, res.text)
        self.assertIn(self.public_request.name, res.text)
        self.assertIn(self.public_url.name, res.text)
        self.assertIn(self.public_file_textual.name, res.text)
        self.assertRegex(res.text, r"0\s+folders,\s+2\s+files")

        # Folder with visible shortcut
        self.internal_file.action_update_access_rights(
            access_via_link='view',
            is_access_via_link_hidden=False,
        )
        res = self.url_open(self.public_folder.access_url)
        res.raise_for_status()
        self.assertIn(self.public_file.name, res.text)
        self.assertIn(self.public_request.name, res.text)
        self.assertIn(self.public_url.name, res.text)
        self.assertIn(self.internal_file.name, res.text)
        self.assertRegex(res.text, r"0\s+folders,\s+3\s+files")

        # File
        res = self.url_open(self.public_file.access_url)
        res.raise_for_status()
        self.assertIn(self.public_file.name, res.text)
        self.assertIn("Download file", res.text)
        self.assertIn("Preview file", res.text)

        # Request
        res = self.url_open(self.public_request.access_url)
        res.raise_for_status()
        self.assertIn(f'<span>{self.public_request.owner_id.name}</span> is requesting', res.text)

    def test_doc_ctrl_thumbnail(self):
        placeholder = self.env['ir.binary']._placeholder(
            self.internal_file._get_placeholder_filename('thumbnail'))

        self.authenticate(None, None)
        res = self.url_open(f'/documents/thumbnail/{self.internal_file.access_token}')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content, placeholder)
        res = self.url_open(f'/documents/thumbnail/{self.public_file.access_token}')
        res.raise_for_status()
        self.assertEqual(res.status_code, 200)
        with (Image.open(BytesIO(self.doc_icon)) as image,
              Image.open(BytesIO(res.content)) as thumbnail):
            self.assertEqual(image.size, (100, 100))
            self.assertEqual(thumbnail.size, (100, 52))
        res = self.url_open(f'/documents/thumbnail/{self.public_file.access_token}?width=bad')
        self.assertEqual(res.status_code, 400)
        self.assertIn('bad', res.text)

    def test_doc_ctrl_render_email_content(self):
        """Emails are rendered by documents itself, never through the shared engine."""
        raw = b"From: test@example.com\n\n<p>Hello Email</p>" + b"_" * 1024 + b"end of email"
        document = self.env['documents.document'].create({
            'name': 'Test Email',
            'raw': raw,
            'access_via_link': 'view',
            'mimetype': 'application/documents-email',
        })
        for head in (0, 1):
            with self.subTest(head=head):
                with patch.object(AttachmentController, 'TEXTUAL_THUMBNAIL_SIZE', 1024), \
                     patch.object(AttachmentController, '_render_text_attachment') as mock_render:
                    res = self.url_open(
                        f'/documents/render_text/{document.access_token}?head={head}')
                mock_render.assert_not_called()
                self.assertEqual(res.status_code, 200)
                self.assertIn('o_email_preview_watermark', res.text)
                self.assertIn('EMAIL', res.text)
                self.assertIn('Hello Email', res.text)
                self.assertIn('end of email', res.text, 'emails are never truncated')
                self.assertEqual('scrolling="no"' in res.text, bool(head))

    def test_doc_ctrl_render_email_headers(self):
        """Test cache control and security headers specific to the email mimetype in documents."""
        render_csp = "default-src 'none'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; font-src 'self'; sandbox;"
        document = self.env['documents.document'].create({
            'name': 'Test Email',
            'raw': b"From: test@example.com\n\nHello Email",
            'access_via_link': 'view',
            'mimetype': 'application/documents-email',
        })

        for unique in (False, True):
            with self.subTest(unique=unique):
                url = f'/documents/render_text/{document.access_token}'
                if unique:
                    url += f'?unique={document.attachment_id.checksum}'
                res = self.url_open(url)
                self.assertEqual(res.status_code, 200)
                self.assertEqual(res.headers.get("Content-Type"), "text/html; charset=utf-8")
                self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
                self.assertEqual(res.headers.get("Content-Security-Policy"), render_csp)
                cache_control = res.headers.get("Cache-Control", "")
                self.assertNotIn("public", cache_control)
                self.assertIn("private", cache_control)

                if unique:
                    self.assertIn("immutable", cache_control)
                    self.assertIn(f"max-age={STATIC_CACHE_LONG}", cache_control)
                else:
                    self.assertNotIn("immutable", cache_control)
                    self.assertNotIn("max-age", cache_control)

    def test_doc_ctrl_render_text_access(self):
        for document, user, status, content in [
            (self.missing_file,           None,  404, "not found"),                # no document
            (self.public_request,         None,  400, "expected a file"),          # no attachment_id
            (self.internal_file,          None,  404, "not found"),                # access_via_link='none'
            (self.internal_shortcut,      None,  404, "not found"),                # access_via_link='none'
            (self.internal_hidden,      'demo', 404, "not found"),                # access_internal='none'
            (self.internal_file_textual,  None, 404, "not found"),                # access_internal='none'
        ]:
            self.authenticate(user, user)
            res = self.url_open(f'/documents/render_text/{document.access_token}')
            self.assertEqual(res.status_code, status)
            self.assertIn(content, res.text)

    def test_doc_ctrl_render_text_delegates_to_mail(self):
        """The documents route must delegate text rendering to the shared mail engine."""
        cases = [
            ('text/markdown', b'# Integration'),
            ('text/html', b'<b>Integration</b>'),
            ('application/json', b'{"test": "Integration"}'),
            ('text/plain', b'Integration'),
        ]
        for mimetype, raw in cases:
            with self.subTest(mimetype=mimetype):
                document = self.env['documents.document'].create({
                    'name': f'Test {mimetype.replace("/", "_")}',
                    'raw': raw,
                    'access_via_link': 'view',
                    'mimetype': mimetype,
                })
                with patch.object(AttachmentController, '_render_text_attachment', return_value="dummy") as mock_render:
                    res = self.url_open(f'/documents/render_text/{document.access_token}')
                    self.assertEqual(res.status_code, 200)
                    mock_render.assert_called_once()

    def test_doc_ctrl_thumbnail_textual(self):
        TEXT_str = TEXT_RAW.decode('utf-8')
        original_file_read = self.registry["ir.attachment"]._file_read
        file_read_patch = patch.object(self.registry["ir.attachment"], '_file_read', side_effect=original_file_read, autospec=True)
        for document, user, status, content in [
            (self.public_folder,                None,  400, "bad document type"),      # folder
            (self.public_url,                   None,  400, "bad document type"),      # url
            (self.public_file,                  None,  400, "bad document mimetype"),  # png
            (self.public_file_textual,          None,  200, TEXT_str),                 # access_via_link='view'
            (self.internal_file,               'demo', 400, "bad document mimetype"),  # png
            (self.internal_file_textual,       'demo', 200, TEXT_str),                 # access_internal='view'
            (self.internal_file_textual_on_db, 'demo', 200, TEXT_str),                 # file on db
        ]:
            self.authenticate(user, user)
            with file_read_patch as patched:
                res = self.url_open(f'/documents/render_text/{document.access_token}?head=1')
            if document is self.internal_file_textual_on_db:
                patched.assert_not_called()
            self.assertEqual(res.status_code, status)
            self.assertIn(content, res.text)

    def test_doc_ctrl_upload_folder_public(self):
        self.authenticate(None, None)

        # Check errors
        res = self.url_open(f'/documents/upload/{self.internal_folder.access_token}', data={
            'csrf_token': self.csrf_token(),
            'ufile': '',
        })
        self.assertEqual(res.status_code, 404)
        res = self.url_open(f'/documents/upload/{self.public_folder.access_token}', data={
            'csrf_token': self.csrf_token(),
            'ufile': '',
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("missing files", res.text)
        res = self.url_open(f'/documents/upload/{self.public_folder.access_token}',
            data={
                'csrf_token': self.csrf_token(),
                'res_model': 'res.users',
            },
            files={'ufile': BytesIO()})
        self.assertEqual(res.status_code, HTTPStatus.FORBIDDEN)
        self.assertIn("only internal users can provide field values", res.text)

        # Upload a text file
        with RecordCapturer(self.env['documents.document'], []) as capture:
            res = self.url_open(f'/documents/upload/{self.public_folder.access_token}',
                data={'csrf_token': self.csrf_token()},
                files={'ufile': ('hello.txt', BytesIO(b"Hello"), 'text/plain')},
                allow_redirects=False)
            res.raise_for_status()
        document = capture.records.ensure_one()
        self.assertEqual(document.name, 'hello.txt')
        self.assertEqual(document.mimetype, 'text/plain')
        self.assertEqual(document.access_internal, 'edit')
        self.assertEqual(document.access_via_link, 'view')
        self.assertEqual(document.folder_id, self.public_folder)
        self.assertEqual(document.owner_id, self.public_folder.owner_id)
        self.assertEqual(document.raw.content, b"Hello")
        self.assertRegex(document.access_token, r'[A-Za-z0-9-_]{22}')
        self.assertEqual(len(document.message_ids), 1)
        creation_msg = document.message_ids
        self.assertMessageFields(
            creation_msg, {'body_content': get_document_creation_message('Public user', 'hello.txt', 'User created')}
        )
        self.assertEqual(res.status_code, HTTPStatus.SEE_OTHER)  # 303
        self._assertPathEqual(res.headers.get('Location'), self.public_folder.access_url)
        self.url_open(res.headers['Location']).raise_for_status()

        # Upload an image but forge the filename/mimetype to pretend it is text
        with (RecordCapturer(self.env['documents.document'], []) as record_capture,
              self.assertLogs('odoo.tools.mimetypes', 'WARNING') as log_capture):
            res = self.url_open(f'/documents/upload/{self.public_folder.access_token}',
                data={'csrf_token': self.csrf_token()},
                files={'ufile': ('hello.txt', BytesIO(self.doc_icon), 'text/plain')},
                allow_redirects=False)
            res.raise_for_status()
        document = record_capture.records.ensure_one()
        self.assertEqual(document.name, 'hello.txt.png',
                         "the filename must have been neutralized")
        self.assertEqual(document.mimetype, 'image/png',
                         "the mimetype must have been neutralized")
        self.assertEqual(document.raw.content, self.doc_icon)
        self.assertEqual(log_capture.output, [
            ("WARNING:odoo.tools.mimetypes:File 'hello.txt' has an "
             "invalid extension for mimetype 'image/png', adding '.png'")
        ])
        self.url_open(res.headers['Location']).raise_for_status()

    @mute_logger('odoo.addons.documents.models.documents_document')
    def test_doc_ctrl_upload_request_public(self):
        self.env = self.env(context={**self.env.context, 'lang': 'en_US'})
        self.authenticate(None, None)
        # Check that uploading a document to a request is independent from user's access to related record
        self.public_request.write({'res_id': self.user_demo.id, 'res_model': self.user_demo._name})
        self.assertFalse(self.user_demo.check_access('read'))

        # Upload a text file
        with self.mock_mail_gateway():
            res = self.url_open(f'/documents/upload/{self.public_request.access_token}',
                data={'csrf_token': self.csrf_token()},
                files={'ufile': ('hello.txt', BytesIO(b"Hello"), 'text/plain')},
                allow_redirects=False)
            res.raise_for_status()

        self.assertEqual(self.public_request.name, 'hello.txt')
        self.assertEqual(self.public_request.mimetype, 'text/plain')
        self.assertEqual(self.public_request.access_internal, 'edit')
        self.assertEqual(self.public_request.access_via_link, 'view')
        self.assertEqual(self.public_request.owner_id, self.user_admin)
        self.assertEqual(self.public_request.raw.content, b"Hello")
        tracking_message_ids = self.public_request.message_ids.filtered(lambda m: m.message_type == 'tracking')
        self.assertMessageFields(
            tracking_message_ids, {
                'tracking_values': [('name', 'char', 'public-request.png', 'hello.txt')],
            }
        )
        other_message_ids = self.public_request.message_ids - tracking_message_ids
        self.assertEqual(len(other_message_ids), 2)
        update_msg, creation_msg = other_message_ids
        self.assertMessageFields(
            creation_msg, {'body_content': get_document_creation_message('manager', 'public-request.png', 'User created')}
        )
        # Check that requester is notified when the document is uploaded
        self.assertMailNotifications(
            update_msg,
            [{
                'content': 'Public user has uploaded the requested document',
                'message_type': 'notification',
                'notif': [{'partner': self.user_manager.partner_id, 'type': 'email'}],
                'subtype': 'mail.mt_note',
            }]
        )
        self.assertIn(
            f'(originally requested from {self.public_request.requestee_partner_id.name})',
            update_msg.body,
            "The update message should explicitly contain the requestee when the uploader is not the requestee."
        )
        self.assertEqual(res.status_code, HTTPStatus.SEE_OTHER)  # 303
        self._assertPathEqual(res.headers.get('Location'), "/documents/upload/success")
        self.url_open(res.headers['Location']).raise_for_status()

        # new request
        public_request = self.env['documents.document'].create({
            'type': 'request',
            'name': "public-request.png",
            'access_internal': 'edit',
            'access_via_link': 'edit',
            'is_access_via_link_hidden': False,
            'owner_id': self.user_admin.id,
            'folder_id': self.public_folder.id,
        })

        shortcut = public_request.action_create_shortcut()
        self.assertFalse(shortcut.thumbnail)
        self.assertFalse(public_request.thumbnail)

        # Upload an image but forge the filename/mimetype to pretend it is text
        with self.assertLogs('odoo.tools.mimetypes', 'WARNING') as log_capture:
            res = self.url_open(f'/documents/upload/{public_request.access_token}',
                data={'csrf_token': self.csrf_token()},
                files={'ufile': ('hello.txt', BytesIO(self.doc_icon), 'text/plain')},
                allow_redirects=False
            )
            res.raise_for_status()
        self.assertEqual(public_request.name, 'hello.txt.png',
                         "the filename must have been neutralized")
        self.assertEqual(public_request.mimetype, 'image/png',
                         "the mimetype must have been neutralized")
        self.assertEqual(public_request.raw.content, self.doc_icon)

        self.assertTrue(shortcut.thumbnail)
        self.assertTrue(public_request.thumbnail)

        self.assertEqual(log_capture.output, [
            ("WARNING:odoo.tools.mimetypes:File 'hello.txt' has an "
             "invalid extension for mimetype 'image/png', adding '.png'")
        ])
        self.url_open(res.headers['Location']).raise_for_status()

        # upload many files at once
        tag = self.env['documents.tag'].create({'name': 'test tag'})

        # start from a fresh request to simplify the checks bellow
        public_request = self.env['documents.document'].create({
            'type': 'request',
            'name': "public-request.png",
            'access_internal': 'edit',
            'access_via_link': 'edit',
            'owner_id': self.user_admin.id,
            'folder_id': self.public_folder.id,
            'tag_ids': tag.ids,
        })
        admin_shortcut = public_request.with_user(self.user_admin).action_create_shortcut("MY")
        admin_shortcut.access_internal = 'none'
        demo_shortcut = public_request.with_user(self.user_demo).action_create_shortcut("MY")
        demo_shortcut.access_internal = 'edit'
        partner = self.env["res.partner"].create({"name": "test"})

        public_request.action_update_access_rights(
            access_via_link='edit',
            is_access_via_link_hidden=False,
            partners={partner: ('edit', False)},
        )

        with RecordCapturer(self.env['documents.document'], []) as record_capture:
            res = self.url_open(f'/documents/upload/{public_request.access_token}',
                data={'csrf_token': self.csrf_token()},
                files=[
                    ('ufile', ('hello1.txt', BytesIO(b"Hello 1"), 'text/plain')),
                    ('ufile', ('hello2.txt', BytesIO(b"Hello 2"), 'text/plain')),
                ],
                allow_redirects=False,
            )
            res.raise_for_status()

        new_shortcuts = record_capture.records.filtered('shortcut_document_id.id')
        new_doc = record_capture.records - new_shortcuts
        self.assertEqual(len(new_doc), 1, "One new record should have been created")
        self.assertNotEqual(new_doc, public_request)
        self.assertEqual(public_request.type, "binary")
        self.assertEqual(new_doc.type, "binary")
        self.assertNotEqual(new_doc.attachment_id, public_request.attachment_id)
        self.assertEqual(public_request.name, 'hello1.txt')
        self.assertEqual(new_doc.name, 'hello2.txt')
        self.assertEqual(public_request.raw.content, b'Hello 1')
        self.assertEqual(new_doc.raw.content, b'Hello 2')
        self.assertEqual(public_request.tag_ids, tag)
        self.assertEqual(new_doc.tag_ids, tag)
        self.assertEqual(public_request.owner_id, self.user_admin)
        self.assertEqual(new_doc.owner_id, self.user_admin)

        self.assertEqual(len(new_shortcuts), 2, "Should have copied the shortcuts of both user")
        admin_copy = new_shortcuts.filtered(lambda d: d.owner_id == self.user_admin)
        demo_copy = new_shortcuts.filtered(lambda d: d.owner_id == self.user_demo)
        self.assertEqual(len(admin_copy), 1)
        self.assertEqual(len(demo_copy), 1)
        self.assertEqual(admin_copy.access_internal, 'none')
        self.assertEqual(demo_copy.access_internal, 'edit')

        # keep the information of who upload at least in `create_uid`
        self.assertEqual(new_doc.create_uid, self.env.ref('base.public_user'))
        self.assertEqual(admin_copy.create_uid, self.env.ref('base.public_user'))
        self.assertEqual(demo_copy.create_uid, self.env.ref('base.public_user'))

        # check that the access are also copied, and that no new access have been added
        self.assertEqual(public_request.access_ids.partner_id, partner | self.user_admin.partner_id)
        self.assertEqual(new_doc.access_ids.partner_id, partner | self.user_admin.partner_id)
        self.assertEqual(admin_copy.access_ids.partner_id, partner | self.user_admin.partner_id)
        self.assertEqual(demo_copy.access_ids.partner_id, partner | self.user_demo.partner_id | self.user_admin.partner_id)

        self.assertEqual(admin_shortcut.shortcut_document_id.raw.content, b'Hello 1')
        self.assertEqual(demo_shortcut.shortcut_document_id.raw.content, b'Hello 1')
        self.assertEqual(admin_copy.shortcut_document_id.raw.content, b'Hello 2')
        self.assertEqual(demo_copy.shortcut_document_id.raw.content, b'Hello 2')

        self.assertEqual(admin_shortcut.shortcut_document_id.name, 'hello1.txt')
        self.assertEqual(demo_shortcut.shortcut_document_id.name, 'hello1.txt')
        self.assertEqual(admin_copy.shortcut_document_id.name, 'hello2.txt')
        self.assertEqual(demo_copy.shortcut_document_id.name, 'hello2.txt')

    @freeze_time('2022-07-24 08:00:00')
    def test_doc_upload_folder_user(self):
        self.authenticate('demo', 'demo')

        # Errors
        res = self.url_open(f'/documents/upload/{self.internal_folder.access_token}',
            data={
                'csrf_token': self.csrf_token(),
                'res_id': 'bad'
            },
            files={'ufile': BytesIO()},
            allow_redirects=False,
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn('bad', res.text)

        # Upload a test file
        self.internal_folder.create_activity_option = True
        with (RecordCapturer(self.env['documents.document'], []) as capture,
              RecordCapturer(self.env['mail.activity'], [
                ('res_model', '=', 'documents.document')
              ]) as capture_activity):
            res = self.url_open(f'/documents/upload/{self.internal_folder.access_token}',
                data={'csrf_token': self.csrf_token()},
                files={'ufile': ('hello.txt', b"Hello", 'text/plain')},
                allow_redirects=False,
            )
            res.raise_for_status()

        document = capture.records.ensure_one()
        self.assertEqual(document.name, 'hello.txt')
        self.assertEqual(document.mimetype, 'text/plain')
        self.assertEqual(document.owner_id, self.user_demo)
        self.assertFalse(document.res_id)
        self.assertFalse(document.res_model)
        self.assertEqual(document.attachment_id.res_id, document.id)
        self.assertEqual(document.attachment_id.res_model, 'documents.document')
        self.assertEqual(len(document.message_ids), 1)
        creation_msg = document.message_ids
        self.assertMessageFields(
            creation_msg, {'body_content': get_document_creation_message('Marc Demo', 'hello.txt', 'User created')}
        )
        self.assertFalse(capture_activity.records, 'Activities should only be created when using the mail gateway')

        # Upload a fake text file that actually is an image on the demo user
        self.internal_folder.create_activity_option = False
        with (RecordCapturer(self.env['documents.document'], []) as capture,
              RecordCapturer(self.env['mail.activity'], [
                ('res_model', '=', 'documents.document')
              ]) as capture_activity):
            res = self.url_open(f'/documents/upload/{self.internal_folder.access_token}',
                data={
                    'csrf_token': self.csrf_token(),
                    'res_id': self.user_demo.partner_id.id,
                    'res_model': 'res.partner',
                },
                files={'ufile': ('hello.txt', self.doc_icon, 'text/plain')},
            )
            res.raise_for_status()

        self.assertFalse(capture_activity.records)
        document = capture.records.ensure_one()
        self.assertEqual(document.name, 'hello.txt',
            "the filename must not have been neutralized")
        self.assertEqual(document.mimetype, 'text/plain',
            "the mimetype must not have been neutralized")
        self.assertEqual(document.res_id, self.user_demo.partner_id.id)
        self.assertEqual(document.res_model, 'res.partner')
        self.assertEqual(document.attachment_id.res_id, self.user_demo.partner_id.id)
        self.assertEqual(document.attachment_id.res_model, 'res.partner')

    def test_doc_upload_request_user(self):
        self.env = self.env(context={**self.env.context, 'lang': 'en_US'})
        self.authenticate('demo', 'demo')

        with self.mock_mail_gateway():
            # res_model/res_id should be ignored
            res = self.url_open(f'/documents/upload/{self.internal_request.access_token}',
                data={
                    'res_id': self.user_demo.id,
                    'res_model': 'res.users',
                    'csrf_token': self.csrf_token(),
                },
                files={'ufile': ('hello.txt', BytesIO(b"Hello"), 'text/plain')},
                allow_redirects=False
            )
            res.raise_for_status()

        self.assertEqual(self.internal_request.name, 'hello.txt')
        self.assertEqual(self.internal_request.mimetype, 'text/plain')
        self.assertFalse(self.internal_request.res_id)
        self.assertFalse(self.internal_request.res_model)
        self.assertEqual(self.internal_request.attachment_id.res_id, self.internal_request.id)
        self.assertEqual(self.internal_request.attachment_id.res_model, 'documents.document')
        self.assertEqual(self.internal_request.raw.content, b"Hello")
        tracking_message_ids = self.internal_request.message_ids.filtered(lambda msg: msg.message_type == 'tracking')
        self.assertMessageFields(
            tracking_message_ids, {
                'tracking_values': [('name', 'char', 'internal-request.png', 'hello.txt')],
            }
        )
        other_message_ids = self.internal_request.message_ids - tracking_message_ids
        self.assertEqual(len(other_message_ids), 2)
        update_msg, creation_msg = other_message_ids
        self.assertMessageFields(
            creation_msg, {'body_content': get_document_creation_message('manager', 'internal-request.png', 'User created')}
        )
        # Check that requester is notified when the document is uploaded
        self.assertMailNotifications(
            update_msg,
            [{
                'content': f'{self.user_demo.name} has uploaded the requested document',
                'message_type': 'notification',
                'notif': [{'partner': self.user_manager.partner_id, 'type': 'email'}],
                'subtype': 'mail.mt_note',
            }]
        )

        # test that uploading a document requested by self doesn't notify
        request = self.internal_request.copy({'requestee_partner_id': self.user_portal.partner_id.id})
        with self.assertMsgWithoutNotifications():
            # uploading the document
            res = self.url_open(f'/documents/upload/{request.access_token}',
                data={
                    'res_id': self.user_demo.id,
                    'res_model': 'res.users',
                    'csrf_token': self.csrf_token(),
                },
                files={'ufile': ('hello.txt', BytesIO(b"Hello"), 'text/plain')},
                allow_redirects=False
            )
            res.raise_for_status()

        # attempt to upload on the admin's file
        res = self.url_open(f'/documents/upload/{self.internal_hidden.access_token}',
            data={'csrf_token': self.csrf_token()},
            files={'ufile': ('hello.txt', BytesIO(b"Hello"), 'text/plain')},
        )
        self.assertEqual(res.status_code, 404)

        # Check that the images are not compressed
        img_byte = BytesIO()
        Image.new(mode='RGB', size=(10_000, 2_000)).save(img_byte, format='PNG')
        img_byte = img_byte.getvalue()

        res = self.url_open(f'/documents/upload/{self.internal_request.access_token}',
            data={
                'res_id': self.user_demo.id,
                'res_model': 'res.users',
                'csrf_token': self.csrf_token(),
            },
            files={'ufile': ('test.bmp', img_byte, 'image/bmp')},
            allow_redirects=False,
        )
        res.raise_for_status()
        self.assertEqual(self.internal_request.name, 'test.bmp')
        self.assertEqual(self.internal_request.raw.content, img_byte)

    def test_doc_ctrl_upload_shortcut(self):
        self.env = self.env(context={**self.env.context, 'lang': 'en_US'})
        self.authenticate(None, None)
        self.internal_file.action_update_access_rights(access_via_link='edit')
        for access_via_link, hidden in [
            ('none', True),
            ('view', True),
            ('edit', True),
            ('none', False),
            ('view', False),
        ]:
            with self.subTest(access_via_link=access_via_link, hidden=hidden):
                self.internal_file.action_update_access_rights(
                    access_via_link=access_via_link,
                    is_access_via_link_hidden=hidden,
                )
                res = self.url_open(
                    f'/documents/upload/{self.internal_shortcut.access_token}',
                    data={'csrf_token': self.csrf_token()},
                    files={'ufile': ('hello.txt', BytesIO(b"Hello"), 'text/plain')},
                    allow_redirects=False
                )
                self.assertEqual(res.status_code, 404)

        self.internal_file.action_update_access_rights(
            access_via_link='edit',
            is_access_via_link_hidden=False,
        )
        res = self.url_open(
            f'/documents/upload/{self.internal_shortcut.access_token}',
            data={'csrf_token': self.csrf_token()},
            files={'ufile': ('hello.txt', BytesIO(b"Hello"), 'text/plain')},
            allow_redirects=False
        )
        res.raise_for_status()
        self.assertEqual(res.status_code, 303)
        self._assertPathIn(res.headers.get('Location'), {
            self.internal_file.access_url,
            self.internal_shortcut.access_url,
        })
        self.assertEqual(self.internal_file.access_via_link, 'edit')
        self.assertEqual(self.internal_file.name, 'hello.txt')
        self.assertEqual(self.internal_file.mimetype, 'text/plain')
        self.assertFalse(self.internal_file.res_id)
        self.assertFalse(self.internal_file.res_model)
        self.assertEqual(self.internal_file.attachment_id.res_id, self.internal_file.id)
        self.assertEqual(self.internal_file.attachment_id.res_model, 'documents.document')
        self.assertEqual(self.internal_file.raw.content, b"Hello")
        tracking_message_ids = self.internal_file.message_ids.filtered(lambda m: m.message_type == 'tracking')
        self.assertMessageFields(
            tracking_message_ids, {
                'tracking_values': [('name', 'char', 'internal-file.png', 'hello.txt')],
            }
        )
        other_message_ids = self.internal_file.message_ids - tracking_message_ids
        self.assertEqual(len(other_message_ids), 2)
        update_msg, creation_msg = other_message_ids
        self.assertMessageFields(
            creation_msg, {'body_content': get_document_creation_message('OdooBot', 'internal-file.png', 'User created')}
        )
        self.assertMessageFields(update_msg, {'body_content': "<p>Attachment updated by Public user</p>"})
        self.url_open(res.headers['Location']).raise_for_status()

    def test_doc_ctrl_zip(self):
        # the internal user can access all access_internal=view files
        self.authenticate('demo', 'demo')
        res = self.url_open('/documents/zip?' + urlencode({
            'zip_name': 'file.zip',
            'file_ids': f'{self.public_file.id},{self.internal_file.id}',
        }))
        res.raise_for_status()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get('Content-Disposition'),
                         "attachment; filename*=UTF-8''file.zip")
        with BytesIO(res.content) as resfile, zipfile.ZipFile(resfile) as reszip:
            self.assertEqual(sorted(reszip.namelist()), ['internal-file.png', 'public-file.png'])
            self.assertEqual(reszip.read('internal-file.png'), self.doc_icon)
            self.assertEqual(reszip.read('public-file.png'), self.doc_icon)

        # the portal user can only access files that he is not member of
        self.authenticate('portal_test', 'portal_test')
        with self.assertLogs('odoo.http', 'WARNING'):
            res = self.url_open('/documents/zip?' + urlencode({
                'zip_name': 'file.zip',
                'file_ids': f'{self.public_file.id},{self.internal_file.id}',
            }))
            self.assertEqual(res.status_code, HTTPStatus.FORBIDDEN)
        res = self.url_open('/documents/zip?' + urlencode({
            'zip_name': 'file.zip',
            'file_ids': f'{self.public_file.id}',
        }))
        res.raise_for_status()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get('Content-Disposition'),
                         "attachment; filename*=UTF-8''file.zip")
        with BytesIO(res.content) as resfile, zipfile.ZipFile(resfile) as reszip:
            self.assertEqual(reszip.namelist(), ['public-file.png'])
            self.assertEqual(reszip.read('public-file.png'), self.doc_icon)

    def test_web_ctrl_documents(self):
        public_url = f'/web/content/documents.document/{self.public_file.id}/raw'
        internal_url = f'/web/content/documents.document/{self.internal_file.id}/raw'

        with self.subTest(user=None):
            self.authenticate(None, None)
            res = self.url_open(public_url)
            self.assertEqual(res.status_code, 404)

        with self.subTest(user='portal_test'):
            self.authenticate('portal_test', 'portal_test')

            res = self.url_open(public_url)
            res.raise_for_status()
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.content, self.doc_icon)

            res = self.url_open(internal_url)
            self.assertEqual(res.status_code, 404)

            self.internal_file.access_ids.filtered(
                lambda access: access.partner_id == self.user_portal.partner_id
            ).role = 'view'
            res = self.url_open(internal_url)
            res.raise_for_status()
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.content, self.doc_icon)

        with self.subTest(user='demo'):
            self.authenticate('demo', 'demo')
            res = self.url_open(internal_url)
            res.raise_for_status()
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.content, self.doc_icon)

    def test_documents_get_init_data(self):
        """Test computed init data depending on access rights."""
        shared_portal_values = {'access_ids': [
            Command.create({'partner_id': self.user_portal.partner_id.id, 'role': 'view'})
        ], 'raw': 'test'}
        shared_manager_values = {'access_ids': [
            Command.create({'partner_id': self.user_manager.partner_id.id, 'role': 'edit'})
        ], 'raw': 'test'}
        internal_folder = self.env['documents.document'].create([
            {'type': 'folder', 'name': 'Internal', 'access_internal': 'edit'},
        ])
        doc_as_demo = self.env['documents.document'].with_user(self.user_demo)
        restricted_folder = doc_as_demo.create({
            'folder_id': internal_folder.id,
            'type': 'folder',
            'name': 'Restricted Folder',
            'access_internal': 'none',
        })
        demo_personal, company_portal, company_child_portal, restricted_portal, restricted_manager, shared_via_link = (
            doc_as_demo.create([
                shared_portal_values | {'name': 'demo_personal_share_portal'},
                shared_portal_values | {'name': 'company_share_portal'},
                shared_portal_values | {'name': 'company_child_share_portal', 'folder_id': internal_folder.id},
                shared_portal_values | {'name': 'restricted_share_portal', 'folder_id': restricted_folder.id},
                shared_manager_values | {'name': 'restricted_manager', 'folder_id': restricted_folder.id},
                {'name': 'restricted_shared_link', 'folder_id': restricted_folder.id, 'access_via_link': 'view', 'raw': 'test'},
            ])
        )
        (internal_folder | company_portal).sudo().user_folder_id = "COMPANY"
        archived_doc, archived_folder = archived = doc_as_demo.create([
            {'type': doc_type, 'name': f'Archived {doc_type}', 'raw': 'test' if doc_type == 'binary' else None}
            for doc_type in ('binary', 'folder')
        ])
        archived_doc_shortcut, archived_folder_shortcut = archived.action_create_shortcut()
        archived.action_archive()

        for user in (self.user_portal, self.user_manager):
            self.env['documents.document'].with_user(user)._upsert_last_access_date(shared_via_link)

        for document, user, expected_folder_id, expected_document_id in [
            (demo_personal, self.user_demo, 'MY', demo_personal.id),
            (demo_personal, self.user_portal, False, demo_personal.id),
            (demo_personal, self.user_manager, False, demo_personal.id),
            (company_portal, self.user_demo, 'COMPANY', company_portal.id),  # as would any other internal user
            (company_portal, self.user_portal, False, company_portal.id),
            (company_child_portal, self.user_demo, internal_folder.id, company_child_portal.id),
            (company_child_portal, self.user_portal, False, company_child_portal.id),
            (company_child_portal, self.user_manager, internal_folder.id, company_child_portal.id),  # same comment
            (restricted_portal, self.user_demo, restricted_folder.id, restricted_portal.id),
            (restricted_portal, self.user_portal, False, restricted_portal.id),
            (restricted_manager, self.user_demo, restricted_folder.id, restricted_manager.id),
            (restricted_manager, self.user_manager, 'SHARED', restricted_manager.id),
            (shared_via_link, self.user_portal, False, shared_via_link.id),
            (shared_via_link, self.user_manager, 'SHARED', shared_via_link.id),
            (archived_doc, self.user_demo, 'TRASH', archived_doc.id),
            (archived_folder, self.user_demo, 'TRASH', archived_folder.id),
            (archived_doc_shortcut, self.user_demo, 'MY', archived_doc_shortcut.id),
            (archived_folder_shortcut, self.user_demo, 'MY', archived_folder_shortcut.id),
            (internal_folder, self.user_demo, internal_folder.id, None),
        ]:
            document.invalidate_recordset()
            with self.subTest(document_name=document.name, username=user.name):
                data = ShareRoute._documents_get_init_data(document.with_user(user), user)
                self.assertEqual(data['user_folder_id'], str(expected_folder_id) if expected_folder_id else expected_folder_id)
                self.assertEqual(data.get('document_id'), expected_document_id)

    def test_from_access_token(self):
        """Check that _from_access_token doesn't raise on a non-existent record"""
        url = self.env['documents.document'].create({'name': 'url', 'type': 'url', 'url': 'https://www.odoo.com/'})
        access_token = url.access_token
        url.unlink()
        self.authenticate('admin', 'admin')
        res = self.url_open(
            f'/documents/touch/{access_token}',
            data=json.dumps({}),
            headers={"Content-Type": "application/json"}
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.text, '{"jsonrpc": "2.0", "id": null, "result": {}}')

    def test_upload_internal_multi_company_defaults(self):
        main_company = self.env.ref('base.main_company')
        comp = self.env['res.company'].create({'name': 'Company 2'})
        company_field = self.env['ir.model.fields'].search([('model', '=', 'documents.document'), ('name', '=', 'company_id')], limit=1)
        self.env['ir.default'].create([
            {
                'field_id': company_field.id,
                'company_id': comp.id,
                'json_value': comp.id,
            },
            {
                'field_id': company_field.id,
                'company_id': main_company.id,
                'json_value': main_company.id,
            }
        ])

        self.user_admin.write({'company_ids': [Command.link(comp.id)]})
        # assert admin has access to both companies
        self.assertGreaterEqual(self.user_admin.company_ids, main_company | comp)

        self.authenticate('admin', 'admin')
        with RecordCapturer(self.env['documents.document'], []) as record_capture:
            res = self.url_open(f'/documents/upload',
                data={
                    'csrf_token': self.csrf_token(),
                    'allowed_company_ids': f'[{comp.id}]',
                    'user_folder_id': 'COMPANY',
                },
                files={'ufile': ('testingfile.txt', BytesIO(b"Hello"), 'text/plain')},
                allow_redirects=False,
            )
            res.raise_for_status()
        document1 = record_capture.records.ensure_one()
        self.assertEqual(document1.company_id, comp)

        with RecordCapturer(self.env['documents.document'], []) as record_capture:
            res = self.url_open(f'/documents/upload',
                data={
                    'csrf_token': self.csrf_token(),
                    'allowed_company_ids': f'[{main_company.id}]',
                    'user_folder_id': 'COMPANY',
                },
                files={'ufile': ('testingfile2.txt', BytesIO(b"Hello2"), 'text/plain')},
                allow_redirects=False,
            )
            res.raise_for_status()
        document2 = record_capture.records.ensure_one()
        self.assertEqual(document2.company_id, main_company)

    def test_custom_mimetype_content_routes(self):
        """Check content routes for 'application/documents-email' mimetype do
            not render the attachment as html in web browsers"""
        attachment = self.env['ir.attachment'].create({
            'name': "An Email without attachment",
            'type': 'binary',
            'raw': b'<p>A mail body</p>',
            'mimetype': 'application/documents-email',
            'res_model': 'documents.document',
        })
        document = self.env['documents.document'].create({
            'name': "An Email without attachment",
            'access_internal': 'edit',
            'access_via_link': 'view',
            'owner_id': self.user_admin.id,
            'folder_id': self.public_folder.id,
            'attachment_id': attachment.id,
        })
        self.authenticate('admin', 'admin')
        urls = (f'/documents/content/{document.access_token}',
                f'/web/content/documents.document/{document.id}/raw',
                f'/web/content/{attachment.id}')
        for url in urls:
            res = self.url_open(f"{url}?download=0")
            self.assertEqual(res.content, b'<p>A mail body</p>')
            self.assertEqual(res.headers.get('Content-Type'), "text/plain; charset=utf-8")
            self.assertTrue('inline;' in res.headers.get('Content-Disposition'),
                "attachment is displayed as plain text in browser.")
            res = self.url_open(f"{url}?download=1")
            self.assertTrue('attachment;' in res.headers.get('Content-Disposition'),
                "attachment is downloaded")

    def test_upload_traceback(self):
        """
        Check that route find the correct support_folder, create the
        traceback file and return the access url
        """
        url = '/documents/upload_traceback'
        self.authenticate('admin', 'admin')
        with RecordCapturer(self.env["documents.document"], []) as capture:
            res = self.url_open(url, data={"csrf_token": self.csrf_token()}, files={'ufile': ('TEST_traceback.txt', BytesIO(b"TEST traceback"), 'text/plain')})
            res.raise_for_status()
            self.assertEqual(res.headers['Content-Type'], 'application/json; charset=utf-8')
            self.assertIsNotNone(res.json()[0])
            res = self.url_open(url, data={"csrf_token": self.csrf_token()}, files={'ufile': ('TEST_traceback2.txt', BytesIO(b"TEST traceback"), 'text/plain')})
            res.raise_for_status()
            self.assertEqual(res.headers['Content-Type'], 'application/json; charset=utf-8')
            self.assertIsNotNone(res.json()[0])
        documents = capture.records
        self.assertEqual(len(documents), 3)
        self.assertEqual(documents[0].type, 'folder')
        self.assertEqual(documents[0].name, 'Support')
        self.assertEqual(documents[1].type, 'binary')
        self.assertEqual(documents[1].name, 'TEST_traceback.txt')
        self.assertEqual(documents[1].mimetype, 'text/plain')
        self.assertEqual(documents[1].raw.content, b"TEST traceback")
        self.assertEqual(documents[1].folder_id, documents[0])
        self.assertEqual(documents[2].type, 'binary')
        self.assertEqual(documents[2].name, 'TEST_traceback2.txt')
        self.assertEqual(documents[2].mimetype, 'text/plain')
        self.assertEqual(documents[2].raw.content, b"TEST traceback")
        self.assertEqual(documents[2].folder_id, documents[0])


@tagged('post_install', '-at_install')
class TestCaseSecurityRoutes(HttpCaseWithUserDemo):

    def setUp(self):
        super().setUp()

        self.raw_gif = GIF_RAW
        pdf_buffer = BytesIO()
        canva = canvas.Canvas(pdf_buffer, pagesize=(600, 800))
        canva.drawString(100, 750, "Minimal PDF")
        canva.save()
        self.raw_pdf = pdf_buffer.getvalue()

        self.user_attachment_gif, self.admin_attachment_gif, \
        self.user_attachment_pdf, self.admin_attachment_pdf = self.env['ir.attachment'].create([
            {
                'raw': self.raw_gif,
                'name': 'attachmentGif_A.gif',
                'res_model': False,
                'res_id': False,
            },
            {
                'raw': self.raw_gif,
                'name': 'attachmentGif_B.gif',
                'res_model': False,
                'res_id': False,
            },
            {
                'raw': self.raw_pdf,
                'name': 'attachmentPdf_A.pdf',
                'mimetype': 'application/pdf',
                'res_model': False,
                'res_id': False,
            },
            {
                'raw': self.raw_pdf,
                'name': 'attachmentPdf_B.pdf',
                'mimetype': 'application/pdf',
                'res_model': False,
                'res_id': False,
            }
        ])
        self.user_document_gif, self.admin_document_gif, \
        self.user_document_pdf, self.admin_document_pdf = self.env['documents.document'].create([
            {
                'name': 'GIF A',
                'attachment_id': self.user_attachment_gif.id,
            },
            {
                'name': 'GIF B',
                'attachment_id': self.admin_attachment_gif.id,
            },
            {
                'name': 'PDF A',
                'attachment_id': self.user_attachment_pdf.id,
            },
            {
                'name': 'PDF B',
                'attachment_id': self.admin_attachment_pdf.id,
            }
        ])
        self.document_user = self.env['res.users'].create({
            'name': "user",
            'login': "user",
            'password': "useruser",
            'email': "user@yourcompany.com",
            'group_ids': [(6, 0, [self.ref('documents.group_documents_user')])]
        })

    @mute_logger('odoo.http')
    def test_documents_zip_access(self):
        self.authenticate("user", "useruser")
        response = self.url_open('/document/zip', data={
            'file_ids': ','.join(map(str, [self.user_document_gif.id, self.admin_document_gif.id])),
            'zip_name': 'testZip.zip',
            'csrf_token': self.csrf_token(),
        })
        self.assertNotEqual(response.status_code, 200)

    @mute_logger('odoo.http')
    def test_documents_split_access(self):
        self.authenticate("user", "useruser")
        response = self.url_open('/documents/pdf_split', data={
            'vals': json.dumps({
                "tag_ids": [],
                "owner_id": self.document_user.id,
                "active": True
            }),
            'new_files': json.dumps([{
                "name": "Test",
                "new_pages": [{
                    "old_file_type": "document",
                    "old_file_index": self.admin_document_pdf.id,
                    "old_page_number": 1
                }]
            }]),
            'archive': False,
            'csrf_token': self.csrf_token(),
        })
        self.assertNotEqual(response.status_code, 200)
