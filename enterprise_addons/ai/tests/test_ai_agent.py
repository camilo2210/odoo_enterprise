# Part of Odoo. See LICENSE file for full copyright and licensing details.
from unittest.mock import patch

from odoo.tests import new_test_user, tagged, users
from odoo.addons.ai.tests.common import TestAICommon
from odoo.addons.ai.utils.ai_utils import AI_MODELS_BLOCKLIST
from odoo.addons.base.tests.test_ir_cron import CronMixinCase


@tagged("post_install", "-at_install")
class TestAIAgent(TestAICommon, CronMixinCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.internal_user = new_test_user(cls.env, 'internal')
        cls.regular_user = new_test_user(cls.env, 'regular', groups='base.group_user,base.group_user_regular')

    def test_get_llm_response_with_sources(self):
        """Responses include source links when the LLM returns attachment ids."""
        agent = self.env["ai.agent"].create({
            "name": "Odoo Agent",
        })

        attachment = self.env["ir.attachment"].create({
            "name": "Doc 1",
            "raw": b"content text",
            "mimetype": "text/plain",
        })
        source = self.env["ai.agent.source"].create({
            "name": "Doc 1",
            "agent_id": agent.id,
            "attachment_id": attachment.id,
            "type": "binary",
            "status": "indexed",
            "is_active": True,
        })

        message = f"Here is your answer [SOURCE:{source.id}]"
        cited_llm_response = agent._get_llm_response_with_sources(message)

        self.assertNotIn("[SOURCE", cited_llm_response)
        self.assertIn("href=\"/web/content/%s\"" % (attachment.id), cited_llm_response)
        self.assertIn("[1]", cited_llm_response)

    def test_parse_domain_raises_for_ir_prefix(self):
        with self.assertRaisesRegex(ValueError, "ir.config_parameter cannot be used by AI Agents"):
            self.env['ai.tool']._parse_domain("ir.config_parameter", "[('id', '=', '1')]")

    def test_parse_domain_raises_for_blocklisted_model(self):
        for model in AI_MODELS_BLOCKLIST:
            if self.env['ir.module.module']._get('ai_agentic').state == 'installed' and model == "base.automation":
                # skip case since 'base.automation' is accessible to agents if the ai_agentic is installed
                # (Used to create/update automations, access rights checks are performed in the tools)
                continue
            with self.subTest(model=model):
                with self.assertRaisesRegex(ValueError, f"{model} cannot be used by AI Agents"):
                    self.env['ai.tool']._parse_domain(model, "[('id', '=', '1')]")

    @users("internal")
    def test_ai_tool_get_menus_as_non_admin(self):
        """_ai_tool_get_menus should work for non-admin users and exclude inaccessible menus."""
        settings_menu = self.env.ref("base.menu_administration")
        menus_csv = self.env["ai.tool"]._ai_tool_get_menus()['response']
        self.assertNotIn(
            settings_menu.name,
            menus_csv,
            "Menus the user cannot access should not appear in the available menus.",
        )

    @users("regular")
    def test_get_menu_details_as_regular_user(self):
        """_ai_tool_get_menu_details should work for non-admin users, returning details for
        accessible menus and an error for inaccessible ones.
        """
        settings_menu = self.env.ref("base.menu_administration")
        channels_menu = self.env.ref("mail.menu_channel")

        result = self.env["ai.tool"]._ai_tool_get_menu_details(
            [settings_menu.id, channels_menu.id], True,
        )['response']

        menus_by_id = {m["menu_id"]: m for m in result["menus"]}

        self.assertIn("error", menus_by_id[settings_menu.id],
            "Inaccessible menu should return an error.")
        self.assertNotIn("error", menus_by_id[channels_menu.id],
            "Accessible act_window menu should return details without an error.")

    def test_build_rag_context_with_res_field_attachment(self):
        """Ensure RAG context works by bypassing the implicit 'res_field' filter with 'skip_res_field_check', preventing KeyError."""
        admin_user = self.env.ref('base.user_admin')
        agent = self.env["ai.agent"].with_user(admin_user).create({
            "name": "RAG Agent",
        })
        attachment = self.env["ir.attachment"].create({
            "name": "Invoice PDF",
            "raw": b"pdf content",
            "res_model": "sale.order",
            "res_id": 1,
            "res_field": "invoice_pdf",
            "mimetype": "text/plain",
        })
        self.env["ai.agent.source"].create({
            "agent_id": agent.id,
            "attachment_id": attachment.id,
            "name": "Invoice source",
            "status": "indexed",
            "is_active": True,
        })
        embedding = self.env["ai.embedding"].create({
            "res_model": "ir.attachment",
            "res_id": attachment.id,
            "content": "Dummy chunk",
        })

        with patch('odoo.addons.ai.models.ai_embedding.AIEmbedding._get_similar_chunks') as mock_get_similar_chunks, \
             self.mock_embedding_request():
            mock_get_similar_chunks.return_value = self.env["ai.embedding"].browse(embedding.id)

            rag_context = agent.with_user(admin_user)._build_rag_context("Prompt")

            self.assertTrue(rag_context, "RAG context should contain a message for user")
            self.assertIn("Invoice source", rag_context)
            self.assertIn("Dummy chunk", rag_context)
