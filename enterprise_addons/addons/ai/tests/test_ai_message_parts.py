# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.tests import TransactionCase, tagged
from odoo.addons.ai.utils.ai_utils import get_text_from_parts


@tagged("post_install", "-at_install")
class TestAIMessageParts(TransactionCase):

    def test_get_text_multiple_strings(self):
        parts = [
            {'type': 'text', 'text': 'This is the first line'},
            {'type': 'text', 'text': 'This is the second line'},
            {'type': 'text', 'text': 'This is the third line'},
            {'type': 'inline_data', 'mimetype': 'image/png', 'data': 'abc123'},
            {'type': 'inline_data', 'mimetype': 'application/pdf', 'data': 'xyz456'},
        ]
        self.assertEqual(get_text_from_parts(parts), 'This is the first line\nThis is the second line\nThis is the third line')

    def test_get_text_empty(self):
        parts = [
            {'type': 'inline_data', 'mimetype': 'image/png', 'data': 'abc123'},
            {'type': 'inline_data', 'mimetype': 'application/pdf', 'data': 'xyz456'},
        ]
        self.assertEqual(get_text_from_parts(parts), '')

    def test_get_text_single_string(self):
        parts = [
            {'type': 'text', 'text': 'This is the first line'},
        ]
        self.assertEqual(get_text_from_parts(parts), 'This is the first line')

    def test_get_text_single_non_string(self):
        parts = [
            {'type': 'text', 'text': ['This is the first line', 'This is the second line']},
        ]
        self.assertEqual(get_text_from_parts(parts), ['This is the first line', 'This is the second line'])
        parts = [
            {'type': 'text', 'text': {'a': 1, 'b': 2}},
        ]
        self.assertEqual(get_text_from_parts(parts), {'a': 1, 'b': 2})
