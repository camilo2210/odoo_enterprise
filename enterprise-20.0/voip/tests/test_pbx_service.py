from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.voip.tests.common_voip import VoipPhoneServiceCase

PBX_SERVICE_LOGGER = "odoo.addons.voip.models.pbx_service"


@tagged("post_install", "-at_install")
class TestPbxServiceAfterCommit(VoipPhoneServiceCase):
    def test_call_after_commit_does_not_run_synchronously(self):
        calls = []
        self.env["voip.pbx.service"]._call_after_commit(calls.append)

        self.assertFalse(calls)

    def test_call_after_commit_runs_once_the_transaction_commits(self):
        calls = []
        self.env["voip.pbx.service"]._call_after_commit(calls.append)

        self.env.cr.postcommit.run()

        self.assertEqual(len(calls), 1)
        # A fresh environment, not the one that registered the callback:
        # by the time postcommit runs, the original cursor may already be
        # closing, and for a delete the records involved no longer exist
        # in it.
        self.assertNotEqual(calls[0], self.env)

    def test_call_after_commit_never_runs_if_the_transaction_is_discarded(self):
        """A real rollback clears postcommit without running it (see
        Cursor.rollback in odoo/sql_db.py) - simulated here directly since
        odoo/tests/common.py forbids calling cr.rollback() inside a test."""
        calls = []
        self.env["voip.pbx.service"]._call_after_commit(calls.append)

        self.env.cr.postcommit.clear()
        self.env.cr.postcommit.run()

        self.assertFalse(calls)

    @mute_logger(PBX_SERVICE_LOGGER)
    def test_call_after_commit_logs_instead_of_raising(self):
        def _boom(env):
            raise ValueError("boom")

        self.env["voip.pbx.service"]._call_after_commit(_boom)

        self.env.cr.postcommit.run()  # must not raise

    @mute_logger(PBX_SERVICE_LOGGER)
    def test_call_after_commit_does_not_persist_partial_writes_on_failure(self):
        """The exception boundary must sit outside the fresh cursor: catching
        a failure inside it would let func() exit the `with` block cleanly,
        and Cursor.__exit__ commits on a clean exit - persisting whatever
        func() wrote before it failed.

        The fresh cursor here is a TestCursor sharing this test's own
        transaction (HttpCase enables registry_test_mode, which patches
        Registry.cursor() for exactly this - see test_cursor.py), so it does
        see this record even though the test's own transaction never truly
        commits; invalidate_recordset() below forces a re-read past this
        env's cache to observe what the fresh cursor actually wrote.
        """
        queue = self.env["voip.queue"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Before failure",
        })

        def _rename_then_fail(env):
            env["voip.queue"].browse(queue.id).write({"name": "Renamed before failure"})
            raise ValueError("boom")

        self.env["voip.pbx.service"]._call_after_commit(_rename_then_fail)
        self.env.cr.postcommit.run()

        queue.invalidate_recordset()
        self.assertEqual(queue.name, "Before failure")

    def test_call_after_commit_for_deleted_only_runs_for_ids_actually_gone(self):
        # Both rows exist in this test's own (uncommitted) transaction, but
        # the fresh cursor used below shares that same transaction (see the
        # note in test_call_after_commit_does_not_persist_partial_writes_on_failure),
        # so it sees `kept` as a real row and `deleted` as genuinely gone.
        kept = self.env["voip.music.on.hold"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Kept",
        })
        deleted = self.env["voip.music.on.hold"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Deleted",
        })
        deleted_id = deleted.id
        deleted.unlink()

        calls = []
        self.env["voip.pbx.service"]._call_after_commit_for_deleted(
            "voip.music.on.hold",
            [kept.id, deleted_id],
            lambda env, record_id: calls.append(record_id),
        )
        self.env.cr.postcommit.run()

        self.assertEqual(calls, [deleted_id])

    def test_call_after_commit_for_deleted_skips_ids_a_savepoint_rollback_kept(self):
        """A caller can catch this deletion failing inside its own savepoint
        and still commit the outer transaction; a savepoint rollback doesn't
        clear postcommit (unlike a full Cursor.rollback()), so the id must be
        re-checked when the callback actually runs, not assumed gone just
        because it was queued."""
        survivor = self.env["voip.music.on.hold"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Survives a caught failure",
        })

        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                survivor.unlink()
                raise ValueError("something else in this savepoint failed")

        self.assertTrue(survivor.exists())

        calls = []
        self.env["voip.pbx.service"]._call_after_commit_for_deleted(
            "voip.music.on.hold",
            [survivor.id],
            lambda env, record_id: calls.append(record_id),
        )
        self.env.cr.postcommit.run()

        self.assertFalse(calls)

    @mute_logger(PBX_SERVICE_LOGGER)
    def test_call_after_commit_for_deleted_isolates_failures_per_id(self):
        """One id's callback failing must not stop the other id from being
        attempted, and must not leak that id's own partial ORM writes into
        the ids that succeed (each id runs in its own savepoint)."""
        first = self.env["voip.music.on.hold"].with_context(voip_skip_pbx_sync=True).create({
            "name": "First",
        })
        second = self.env["voip.music.on.hold"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Second",
        })
        bystander = self.env["voip.queue"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Before failure",
        })
        first_id, second_id = first.id, second.id
        (first + second).unlink()

        calls = []

        def _run(env, record_id):
            calls.append(record_id)
            if record_id == first_id:
                env["voip.queue"].browse(bystander.id).write({"name": "Renamed before failure"})
                raise ValueError("boom")

        self.env["voip.pbx.service"]._call_after_commit_for_deleted(
            "voip.music.on.hold", [first_id, second_id], _run,
        )
        self.env.cr.postcommit.run()

        self.assertEqual(set(calls), {first_id, second_id})
        bystander.invalidate_recordset()
        self.assertEqual(bystander.name, "Before failure")
