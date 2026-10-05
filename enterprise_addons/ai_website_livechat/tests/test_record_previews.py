# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import HttpCase
from markupsafe import Markup

from .common import AIPreviewCardCase


class TestAIRecordPreviews(AIPreviewCardCase, HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agent = cls.env['ai.agent'].create({'name': 'AI Preview Agent'})
        cls.partner_1 = cls.env['res.partner'].create({'name': 'Preview Partner A'})
        cls.partner_2 = cls.env['res.partner'].create({'name': 'Preview Partner B'})

    def test_prepare_record_previews_metadata_and_message_suffix(self):
        tools_context = {'state': {}}
        result = self.env['ai.tool']._ai_tool_prepare_record_previews(
            tools_context,
            'res.partner',
            [
                {'id': self.partner_2.id},
                {'id': self.partner_1.id},
                {'id': 0},
            ],
            preview_label='Partners',
        )

        self.assertEqual(
            [item['id'] for item in result['preview_metadata']],
            [self.partner_2.id, self.partner_1.id],
        )
        self.assertIn('message_body_suffix', tools_context)
        suffix = tools_context['message_body_suffix']
        self.assertIsInstance(suffix, Markup)
        self.assertIn('o_ai_preview_data', suffix)
        self.assertIn('<span class="o_ai_preview_header">Partners</span>', suffix)
        self.assertIn('o_ai_preview_link', suffix)
        self.assertNotIn('<br', suffix)
        self.assertIn('data-oe-model="res.partner"', suffix)
        self.assertIn(f'data-oe-id="{self.partner_2.id}"', suffix)
        self.assertIn(f'data-oe-id="{self.partner_1.id}"', suffix)

    def test_preview_cards_route_rejects_invalid_and_non_preview_models(self):
        self.assertEqual(
            self.make_jsonrpc_request('/ai/preview_cards', {'model': 'missing.model', 'record_ids': [1]}),
            {'html': False, 'count': 0},
        )
        self.assertEqual(
            self.make_jsonrpc_request('/ai/preview_cards', {'model': 'res.partner', 'record_ids': [self.partner_1.id]}),
            {'html': False, 'count': 0},
        )

    def test_mail_message_extracts_record_preview_data(self):
        body = Markup("""
            <p>Here are the records.</p>
            <span class="o_ai_preview_data">
                <a href="/preview-card" data-oe-model="ai.preview.card.mixin" data-oe-id="10">Preview Card</a>
            </span>
            <span class="o_ai_preview_data">
                <span class="o_ai_preview_header">Partners</span>
                <a href="/partner" data-oe-model="res.partner" data-oe-id="11">Partner</a>
            </span>
        """)
        channel = self.agent._create_ai_chat_channel()
        message = channel.message_post(
            body=body,
            author_id=self.agent.partner_id.id,
            subtype_xmlid="mail.mt_comment",
        )

        self.assertEqual(message._ai_get_record_previews_data(), {
            'preview_sets': [
                {
                    'preview_key': 0,
                    'model': 'ai.preview.card.mixin',
                    'has_preview_cards': True,
                    'header': '',
                    'records': [
                        {'id': 10, 'url': '/preview-card', 'name': 'Preview Card'},
                    ],
                },
                {
                    'preview_key': 1,
                    'model': 'res.partner',
                    'has_preview_cards': False,
                    'header': 'Partners',
                    'records': [
                        {'id': 11, 'url': '/partner', 'name': 'Partner'},
                    ],
                },
            ],
        })

        message_without_links = channel.message_post(
            body='<p>No preview data here.</p>',
            author_id=self.agent.partner_id.id,
            subtype_xmlid="mail.mt_comment",
        )
        self.assertFalse(message_without_links._ai_get_record_previews_data())

    def test_message_store_exposes_record_previews_for_ai_messages(self):
        channel = self.agent._create_ai_chat_channel()
        message = channel.message_post(
            body=Markup("""
                <p>Done.</p>
                <span class="o_ai_preview_data">
                    <a href="#" data-oe-model="ai.preview.card.mixin" data-oe-id="10">Preview Card</a>
                </span>
            """),
            author_id=self.agent.partner_id.id,
            subtype_xmlid="mail.mt_comment",
        )

        data = message._ai_get_record_previews_data()
        self.assertEqual(data, {
            'preview_sets': [
                {
                    'preview_key': 0,
                    'model': 'ai.preview.card.mixin',
                    'has_preview_cards': True,
                    'header': '',
                    'records': [
                        {'id': 10, 'url': '#', 'name': 'Preview Card'},
                    ],
                },
            ],
        })

    def test_prepare_record_previews_empty_input(self):
        tools_context = {'state': {}}
        result = self.env['ai.tool']._ai_tool_prepare_record_previews(tools_context, 'res.partner', [])
        self.assertEqual(result, {'preview_metadata': []})
        self.assertNotIn('message_body_suffix', tools_context)
