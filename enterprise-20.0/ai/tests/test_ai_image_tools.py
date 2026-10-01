# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
from unittest.mock import patch, MagicMock, mock_open

from odoo.tools import file_open
from odoo.tests import TransactionCase
from odoo.exceptions import AccessError


from odoo.addons.ai.utils.ai_image_tools import (
    closest_aspect_ratio,
    _calculate_aspect_ratio,
    field_to_image_path,
    _retrieve_record_args_from_path,
    _retrieve_image_parts_from_file,
    _retrieve_image_src_and_mimetype_from_record,
    retrieve_image_data_from_record,
    retrieve_image_parts_from_path,
)
from odoo.addons.base.tests.files import PNG_RAW


class TestImageTools(TransactionCase):

    def test_calculate_aspect_ratio(self):
        self.assertEqual(_calculate_aspect_ratio(1024, 1024), "1:1")
        self.assertEqual(_calculate_aspect_ratio(800, 600), "4:3")
        self.assertEqual(_calculate_aspect_ratio(1920, 1080), "16:9")
        self.assertEqual(_calculate_aspect_ratio(None, 100), "1:1")
        self.assertEqual(_calculate_aspect_ratio(100, 0), "1:1")

        self.assertEqual(_calculate_aspect_ratio(19, 17), "19:17")
        self.assertEqual(_calculate_aspect_ratio(500, 300), "5:3")

    def test_closest_aspect_ratio(self):
        self.assertEqual(closest_aspect_ratio(width=1024, height=1024), "1:1")
        self.assertEqual(closest_aspect_ratio(width=1920, height=1080), "16:9")
        self.assertEqual(closest_aspect_ratio(width=800, height=600), "4:3")

        # Arbitrary dimensions 719x512
        # 719/512 = 1.404...
        # 4:3 is 1.333... (diff 0.071)
        # 3:2 is 1.5 (diff 0.096)
        # So it should be 4:3.
        self.assertEqual(closest_aspect_ratio(width=719, height=512), "4:3")

    def test_field_to_image_path(self):
        record = self.env['ai.agent'].browse(1)
        path = field_to_image_path(record, 'image_1024')
        self.assertEqual(path, "/web/image/ai.agent/1/image_1024")

    def test_retrieve_record_args_from_path(self):
        cases = [
            # '/web/image/<string:xmlid>'
            ("/web/image/ai.abc123", {'xmlid': 'ai.abc123'}),

            # '/web/image/<string:xmlid>/<string:filename>'
            ("/web/image/ai.abc123/image_128", {'xmlid': 'ai.abc123'}),

            # '/web/image/<string:xmlid>/<int:width>x<int:height>'
            ("/web/image/ai.abc123/1024x1024", {'xmlid': 'ai.abc123'}),

            # '/web/image/<string:xmlid>/<int:width>x<int:height>/<string:filename>'
            ("/web/image/ai.abc123/1024x1024/image_128", {'xmlid': 'ai.abc123'}),

            # '/web/image/<string:model>/<int:id>/<string:field>'
            ("/web/image/res.partner/123/image_128", {'model': 'res.partner', 'id': 123, 'field': 'image_128'}),

            # '/web/image/<string:model>/<int:id>/<string:field>/<string:filename>'
            ("/web/image/res.partner/123/image_128/image_128", {'model': 'res.partner', 'id': 123, 'field': 'image_128'}),

            # '/web/image/<string:model>/<int:id>/<string:field>/<int:width>x<int:height>'
            ("/web/image/res.partner/123/image_128/1024x1024", {'model': 'res.partner', 'id': 123, 'field': 'image_128'}),

            # '/web/image/<string:model>/<int:id>/<string:field>/<int:width>x<int:height>/<string:filename>'
            ("/web/image/res.partner/123/image_128/1024x1024/image_128", {'model': 'res.partner', 'id': 123, 'field': 'image_128'}),

            # '/web/image/<int:id>'
            ("/web/image/123", {'model': 'ir.attachment', 'id': 123, 'field': 'raw'}),

            # '/web/image/<int:id>/<string:filename>'
            ("/web/image/123/image_128", {'model': 'ir.attachment', 'id': 123, 'field': 'raw'}),

            # '/web/image/<int:id>/<int:width>x<int:height>'
            ("/web/image/123/100x100", {'model': 'ir.attachment', 'id': 123, 'field': 'raw'}),

            # '/web/image/<int:id>/<int:width>x<int:height>/<string:filename>'
            ("/web/image/123/100x100/image_128", {'model': 'ir.attachment', 'id': 123, 'field': 'raw'}),

            # '/web/image/<int:id>-<string:unique>'
            ("/web/image/123-abc", {'model': 'ir.attachment', 'id': 123, 'field': 'raw'}),

            # '/web/image/<int:id>-<string:unique>/<string:filename>'
            ("/web/image/123-abc/image_128", {'model': 'ir.attachment', 'id': 123, 'field': 'raw'}),

            # '/web/image/<int:id>-<string:unique>/<int:width>x<int:height>'
            ("/web/image/123-abc/100x100", {'model': 'ir.attachment', 'id': 123, 'field': 'raw'}),

            # '/web/image/<int:id>-<string:unique>/<int:width>x<int:height>/<string:filename>'
            ("/web/image/123-abc/100x100/image_128", {'model': 'ir.attachment', 'id': 123, 'field': 'raw'}),
        ]
        for path, expected in cases:
            args = _retrieve_record_args_from_path(path)
            for key, val in expected.items():
                self.assertEqual(args.get(key), val, f"Failed for {path} at key {key}. Got {args}")

    def test_retrieve_image_parts_from_file(self):
        # Mocking file_open and mimetypes to isolate filesystem dependencies
        with patch('odoo.addons.ai.utils.ai_image_tools.file_open', mock_open(read_data=PNG_RAW)), \
             patch('mimetypes.guess_type', return_value=('image/png', None)):
            parts = _retrieve_image_parts_from_file("/ai/static/src/img/test.png")
            self.assertEqual(len(parts), 1)
            self.assertEqual(parts[0]['type'], 'inline_data')
            self.assertEqual(parts[0]['mimetype'], 'image/png')
            self.assertEqual(parts[0]['data'], base64.b64encode(PNG_RAW).decode())
            self.assertEqual(parts[0]['metadata']['image_path'], "/ai/static/src/img/test.png")

    def test_retrieve_image_data_from_attachment(self):
        attachment = self.env['ir.attachment'].create({
            'name': 'test.png',
            'raw': PNG_RAW,
            'mimetype': 'image/png',
            'store_fname': False,
        })
        data = retrieve_image_data_from_record(attachment, 'raw')
        self.assertEqual(data['content'], PNG_RAW)
        self.assertEqual(data['mimetype'], 'image/png')

    def test_retrieve_image_data_from_attachment_external_url(self):
        """Test retrieval of data from an attachment withURL. The retrieved data is actually an image."""
        attachment = self.env['ir.attachment'].create({
            'name': 'test.png',
            'type': 'url',
            'url': 'https://example.com/image.png',
            'mimetype': 'image/png',
        })
        mock_response = MagicMock()
        mock_response.content = b"external content"

        with patch('requests.request', return_value=mock_response), patch('odoo.addons.ai.utils.ai_image_tools.ImageProcess'):
            data = retrieve_image_data_from_record(attachment, 'raw')
            self.assertEqual(data['content'], b"external content")

    def test_attachment_external_url_not_image(self):
        """Test retrieval of data from an attachment withURL. The retrieved data is not an image."""
        attachment = self.env['ir.attachment'].create({
            'name': 'test.png',
            'type': 'url',
            'url': 'https://example.com/image.png',
            'mimetype': 'image/png',
        })
        mock_response = MagicMock()
        mock_response.content = b"external content"

        with patch('requests.request', return_value=mock_response):
            data = retrieve_image_data_from_record(attachment, 'raw')
            self.assertEqual(data['content'], b"")
            self.assertEqual(data['mimetype'], "application/x-empty")

    def test_no_crash_on_non_existent_image_field(self):
        """Retrieving an image from a field that doesn't exist on the model shouldn't crash."""
        record = self.env['res.partner.category'].create({'name': 'Test Category'})
        self.assertNotIn('image_1024', record._fields)

        image_src = _retrieve_image_src_and_mimetype_from_record(record, 'image_1024')
        self.assertEqual(image_src, {'data': b'', 'mimetype': 'application/x-empty'})

        data = retrieve_image_data_from_record(record, 'image_1024')
        self.assertEqual(data['content'], b'')
        self.assertEqual(data['mimetype'], 'application/x-empty')

    def test_retrieve_image_parts_from_path(self):
        # Case 1: image_path represents a file from an odoo module (an addon)
        image_path = "/ai/static/description/icon.png"
        with file_open(image_path[1:], 'rb') as f:
            content = f.read()
        parts = retrieve_image_parts_from_path(self.env, image_path)
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0]['type'], 'inline_data')
        self.assertEqual(parts[0]['mimetype'], 'image/png')
        self.assertEqual(parts[0]['metadata']['image_path'], image_path)
        self.assertEqual(parts[0]['data'], base64.b64encode(content).decode())

        # Case 2: Database record URL
        attachment = self.env['ir.attachment'].create({
            'name': 'test.png',
            'raw': PNG_RAW,
            'mimetype': 'image/png',
        })
        image_path = f"/web/image/ir.attachment/{attachment.id}/raw"
        parts = retrieve_image_parts_from_path(self.env, image_path)
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0]['type'], 'inline_data')
        self.assertEqual(parts[0]['mimetype'], 'image/png')
        self.assertEqual(parts[0]['metadata']['image_path'], image_path)
        self.assertEqual(parts[0]['data'], base64.b64encode(PNG_RAW).decode())

    def test_retrieve_image_parts_from_path_access(self):
        attachment = self.env['ir.attachment'].create({
            'name': 'secret.png',
            'raw': PNG_RAW,
            'mimetype': 'image/png',
        })
        image_path = f"/web/image/ir.attachment/{attachment.id}/raw"

        restricted_user = self.env['res.users'].create({
            'name': 'Restricted User',
            'login': 'restricted_user',
        })

        with self.with_user(restricted_user.login):
            with self.assertRaises(AccessError):
                retrieve_image_parts_from_path(self.env, image_path)

        parts = retrieve_image_parts_from_path(self.env, image_path)
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0]['data'], base64.b64encode(PNG_RAW).decode())
        self.assertEqual(parts[0]['mimetype'], 'image/png')
        self.assertEqual(parts[0]['metadata']['image_path'], image_path)
