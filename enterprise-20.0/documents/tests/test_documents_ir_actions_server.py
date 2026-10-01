from odoo import Command
from odoo.addons.documents.tests.test_documents_common import TransactionCaseDocuments
from odoo.exceptions import UserError, AccessError


class TestIrActionsServer(TransactionCaseDocuments):
    def test_documents_embedded_actions_security(self):
        base_document = self.document_txt.with_user(self.internal_user).copy()

        source_folder = self.folder_a
        no_embeds_folder1 = self.folder_b
        no_embeds_folder2 = self.folder_a_a
        target_tag = self.tag_b

        source_folder.access_internal = "edit"
        no_embeds_folder1.access_internal = "edit"
        no_embeds_folder2.access_internal = "view"

        def get_add_tag_action(seq=5):
            return self.env["ir.actions.server"].create({
                "name": "Add Tag",
                "model_id": self.env["ir.model"]._get_id("documents.document"),
                "state": "object_write",
                "update_path": "tag_ids",
                "update_m2m_operation": "add",
                "resource_ref": f"documents.tag,{target_tag.id}",
                "usage": "documents_embedded",
                "sequence": seq,
            })

        def get_move_action(folder, seq=5):
            return self.env["ir.actions.server"].create({
                "name": f"Move to {folder.name}",
                "model_id": self.env["ir.model"]._get_id("documents.document"),
                "state": "object_write",
                "update_path": "folder_id",
                "resource_ref": f"documents.document,{folder.id}",
                "usage": "documents_embedded",
                "sequence": seq,
            })

        def get_code_move_action(folder, seq=5):
            return self.env["ir.actions.server"].create({
                "name": f"Code Move to {folder.name}",
                "model_id": self.env["ir.model"]._get_id("documents.document"),
                "state": "code",
                "code": f"record.write({{'folder_id': {folder.id}}})",
                "usage": "documents_embedded",
                "sequence": seq,
            })

        def run_scenario(child_ids, start_folder=source_folder, embed_multi_on=None, expect_failure=False):
            folders_to_embed = [start_folder] if embed_multi_on is None else embed_multi_on

            doc = base_document.with_user(self.internal_user).copy()
            doc.folder_id = start_folder
            doc.tag_ids = [Command.clear()]

            parent_action = self.env["ir.actions.server"].create({
                "name": "Multi Wrapper",
                "state": "multi",
                "model_id": self.env["ir.model"]._get_id("documents.document"),
                "child_ids": child_ids,
                "usage": "documents_embedded",
            })

            for folder in folders_to_embed:
                folder._embed_action(parent_action.id)

            if expect_failure:
                with self.assertRaises(UserError) as err:
                    parent_action.with_user(self.internal_user).with_context(
                        active_model="documents.document", active_id=doc.id
                    ).run()
                self.assertEqual(err.exception.args[0], "This action was not made available on the containing folder.")
            else:
                parent_action.with_user(self.internal_user).with_context(
                    active_model="documents.document", active_id=doc.id
                ).run()
                self.assertIn(target_tag, doc.tag_ids)

        with self.subTest("Standalone Action - Fail if not pinned"):
            doc = base_document.with_user(self.internal_user).copy()
            doc.folder_id = no_embeds_folder1
            with self.assertRaises(UserError) as err:
                get_add_tag_action().with_user(self.internal_user).with_context(
                    active_model="documents.document", active_id=doc.id
                ).run()
            self.assertEqual(err.exception.args[0], "This action was not made available on the containing folder.")

        with self.subTest("Standalone Action - User cannot bypass security by sending the context key via RPC."):
            doc = base_document.with_user(self.internal_user).copy()
            doc.folder_id = no_embeds_folder1
            with self.assertRaises(UserError) as err:
                get_add_tag_action().with_user(self.internal_user).with_context(
                    active_model="documents.document",
                    active_id=doc.id,
                    __documents_embedded_checked=True,
                ).run()
            self.assertEqual(err.exception.args[0], "This action was not made available on the containing folder.")

        with self.subTest("Multi Action [Tag -> Move] - Fail if not pinned on start"):
            run_scenario(
                [
                    get_add_tag_action(seq=5).id,
                    get_move_action(no_embeds_folder1, seq=10).id,
                ],
                embed_multi_on=[],
                expect_failure=True,
            )

        with self.subTest("Multi Action [Tag -> Move] - Success"):
            run_scenario([
                get_add_tag_action(seq=5).id,
                get_move_action(no_embeds_folder1, seq=10).id,
            ])

        with self.subTest("Multi Action [Tag] - Success"):
            run_scenario([
                get_add_tag_action().id,
            ])

        with self.subTest("Multi Action [Move -> Tag] - Success"):
            run_scenario([
                get_move_action(no_embeds_folder1).id,
                get_add_tag_action(seq=10).id,
            ])

        with self.subTest("Multi Action [Code Move -> Tag] - Success"):
            # Prevent regressions for solutions that'd rely only on "state": "object_write"
            run_scenario([
                get_code_move_action(no_embeds_folder1).id,
                get_add_tag_action(seq=10).id,
            ])

        with self.subTest("Multi Action [Move -> Move -> Tag -> Move] - Success"):
            run_scenario([
                get_move_action(no_embeds_folder1, seq=1).id,
                get_move_action(no_embeds_folder2).id,
                get_add_tag_action(seq=10).id,
                get_move_action(no_embeds_folder1, seq=15).id,
            ])

        nested_tag_action = self.env["ir.actions.server"].create({
            "name": "Nested Wrapper",
            "state": "multi",
            "model_id": self.env["ir.model"]._get_id("documents.document"),
            "child_ids": [get_add_tag_action().id],
        })

        with self.subTest("Deep Nested: Fail if Root is not pinned (even if move exists)"):
            run_scenario(
                [
                    get_move_action(no_embeds_folder1).id,
                    nested_tag_action.id,
                ],
                embed_multi_on=[],
                expect_failure=True,
            )

        with self.subTest("Deep Nested: Success if Root is pinned"):
            run_scenario([
                get_move_action(no_embeds_folder1).id,
                nested_tag_action.id,
            ])

        with self.subTest("We can move the documents even if we have no write access on the destination folder"):
            doc = base_document.with_user(self.internal_user).copy()
            with self.assertRaises(AccessError):
                doc.folder_id = no_embeds_folder2
            run_scenario([
                get_move_action(no_embeds_folder2).id,
                get_add_tag_action(seq=10).id,
            ])

        with self.subTest("Running child action individually fails if Root is not pinned."):
            doc = base_document.with_user(self.internal_user).copy()

            move_action = get_move_action(no_embeds_folder1, seq=1)
            tag_action = get_add_tag_action()
            parent_action = self.env["ir.actions.server"].create({
                "name": "Multi Wrapper",
                "state": "multi",
                "model_id": self.env["ir.model"]._get_id("documents.document"),
                "child_ids": [move_action.id, tag_action.id],
            })

            # Set location of doc to destination of move to prevent regressions
            # Ex: this test would fail if embed bypass would allow unpinned actions on destinations move actions
            doc.folder_id = no_embeds_folder1

            with self.assertRaises(UserError) as err:
                tag_action.with_user(self.internal_user).with_context(
                    active_model="documents.document", active_id=doc.id
                ).run()
            self.assertEqual(err.exception.args[0], "This action was not made available on the containing folder.")

            no_embeds_folder1._embed_action(parent_action.id)
            tag_action.with_user(self.internal_user).with_context(
                active_model="documents.document", active_id=doc.id
            ).run()
            self.assertIn(target_tag, doc.tag_ids)
