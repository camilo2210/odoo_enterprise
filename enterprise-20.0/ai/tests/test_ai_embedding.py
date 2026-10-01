# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.ai.tests.common import TestAICommon


@tagged("post_install", "-at_install")
class TestAIEmbedding(TestAICommon):
    def test_embedding_generation_from_new_source(self):
        """Test that adding a source to an agent triggers its embedding"""
        content_to_embed = b"content to embed"
        attachment = self.env["ir.attachment"].create({
            "name": "shared.txt",
            "raw": content_to_embed,
        })

        with (
            self.registry_test_mode(),
            self.mock_embedding_request(),
            patch("odoo.addons.ai.models.ai_embedding.AIEmbedding._get_default_embedding_model", return_value="default_embedding_model"),
        ):
            agent = self.env["ai.agent"].create({
                "name": "Agent",
            })
            valid_source = self.env["ai.agent.source"].create({
                "name": f"Source {agent.name}",
                "agent_id": agent.id,
                "type": "binary",
                "attachment_id": attachment.id,
            })
            self.env.ref('ai.ir_cron_generate_embedding').method_direct_trigger()

        self.assertEqual(valid_source.status, "indexed")

        created_embedding = self.env["ai.embedding"].search([("res_model", "=", "ir.attachment"), ("res_id", "=", attachment.id)])
        self.assertTrue(created_embedding, "An embedding should have been created for the source")
        self.assertEqual(created_embedding.embedding_model, "default_embedding_model")

        expected_content = (
            f"{content_to_embed.decode('utf-8')}"
        )
        self.assertEqual(created_embedding.content, expected_content)
        self.assertEqual(created_embedding.embedding_vector, [0.1] * 1536)

    def test_recompute_only_reprocesses_sources_on_deprecated_provider(self):
        """A source on a still-valid provider must not be affected by another
        provider's deprecated embedding, even if they share the same checksum."""

        agent_with_deprecated_embedding = self.env["ai.agent"].create({
            "name": "Deprecated agent",
            "embedding_model": "deprecated_embedding",
        })
        agent_with_valid_embedding = self.env["ai.agent"].create({
            "name": "Valid agent",
            "embedding_model": "valid_embedding",
        })
        attachment = self.env["ir.attachment"].create({
            "name": "shared.txt",
            "raw": b"some content",
        })
        attachment_2 = self.env["ir.attachment"].create({
            "name": "shared.txt",
            "raw": b"some content",
        })

        with patch("odoo.addons.ai.models.ai_agent_source.AIAgentSource._trigger_embedding_generation"):
            deprecated_source = self.env["ai.agent.source"].create({
                "name": f"Source {agent_with_deprecated_embedding.name}",
                "agent_id": agent_with_deprecated_embedding.id,
                "type": "binary",
                "attachment_id": attachment.id,
                "status": "indexed",
                "is_active": True,
            })
            valid_source = self.env["ai.agent.source"].create({
                "name": f"Source {agent_with_valid_embedding.name}",
                "agent_id": agent_with_valid_embedding.id,
                "type": "binary",
                "attachment_id": attachment_2.id,
                "status": "indexed",
                "is_active": True,
            })

        deprecated_embedding = self.env["ai.embedding"].create({
            "res_model": "ir.attachment",
            "res_id": attachment.id,
            "content": "chunk content",
            "embedding_model": "deprecated_embedding",
            "embedding_vector": [0.1] * 1536,
        })
        valid_embedding = self.env["ai.embedding"].create({
            "res_model": "ir.attachment",
            "res_id": attachment_2.id,
            "content": "chunk content",
            "embedding_model": "valid_embedding",
            "embedding_vector": [0.1] * 1536,
        })

        with (
            patch(
                "odoo.addons.ai.models.ai_embedding.AIEmbedding._get_supported_embedding_models",
                return_value=["valid_embedding"],
            ),
            patch(
                "odoo.addons.base.models.ir_cron.IrCron._trigger",
                autospec=True,
            ) as mock_trigger,
            patch(
                "odoo.addons.base.models.ir_cron.IrCron._commit_progress",
            ),
        ):
            self.env["ai.embedding"]._cron_update_deprecated_embedding_models()

        self.assertFalse(deprecated_embedding.embedding_vector, "Deprecated embedding must be removed")
        self.assertTrue(valid_embedding.embedding_vector, "Still-valid embedding must be kept")

        self.assertEqual(deprecated_source.status, "processing")
        self.assertTrue(deprecated_source.is_active, "Active status shouldn't have changed.")
        self.assertEqual(agent_with_deprecated_embedding.embedding_model, self.env["ai.embedding"]._get_default_embedding_model(), "Agent model should be reset to default")
        self.assertEqual(
            valid_source.status, "indexed",
            "Source on a still-valid provider must not be reprocessed",
        )
        self.assertTrue(valid_source.is_active)
        mock_trigger.assert_called_once()
        triggered_cron = mock_trigger.call_args.args[0]
        self.assertEqual(triggered_cron, self.env.ref("ai.ir_cron_generate_embedding"))
