from odoo.exceptions import ValidationError
from odoo.tools import BinaryBytes, mute_logger

from odoo.addons.voip.tools.wav import encode_wav, pack_int16_samples
from odoo.addons.voip.tests.common_voip import (
    VoipPhoneServiceCase,
    calls_for,
    capture_pbx_calls,
    tts_sound_values,
)


def _wav_data(n_frames=8):
    return BinaryBytes(encode_wav(
        pack_int16_samples([0] * n_frames), channels=1, sample_width=2, frame_rate=8000,
    ))


class TestVoipMusicOnHold(VoipPhoneServiceCase):
    def _create_audio_message(self, name="Track"):
        return self.env["voip.sound"].with_context(voip_skip_pbx_sync=True).create({
            "name": name,
            "source_type": "upload",
            "data": _wav_data(),
            "data_filename": f"{name}.wav",
        })

    def test_create_syncs_pbx_and_stores_uuid_and_name(self):
        track_message = self._create_audio_message()

        calls, patcher = capture_pbx_calls()
        with patcher:
            moh = self.env["voip.music.on.hold"].create({
                "name": "Waiting music",
                "track_ids": [(0, 0, {"audio_message_id": track_message.id})],
            })

        self.assertEqual(moh.pbx_moh_uuid, "pbx-moh-uuid")
        # "moh_name" is echoed back by the mock (like the real PBX would).
        self.assertEqual(moh.pbx_moh_name, "Waiting music")
        sync_calls = calls_for(calls, "sync_moh")
        self.assertEqual(len(sync_calls), 1)

    def test_sync_pbx_files_are_numbered_and_sorted_by_sequence(self):
        first_track = self._create_audio_message("First")
        second_track = self._create_audio_message("Second")
        moh = self.env["voip.music.on.hold"].create({
            "name": "Waiting music",
            "track_ids": [
                (0, 0, {"audio_message_id": second_track.id, "sequence": 20}),
                (0, 0, {"audio_message_id": first_track.id, "sequence": 10}),
            ],
        })

        calls, patcher = capture_pbx_calls()
        with patcher:
            moh._sync_pbx()

        sync_call, = calls_for(calls, "sync_moh")
        filenames = [file["filename"] for file in sync_call["params"]["files"]]
        self.assertEqual(filenames, [
            f"001_odoo_audio_{first_track.id}.wav",
            f"002_odoo_audio_{second_track.id}.wav",
        ])

    def test_write_relevant_field_resyncs_pbx(self):
        track_message = self._create_audio_message()
        moh = self.env["voip.music.on.hold"].create({
            "name": "Waiting music",
            "track_ids": [(0, 0, {"audio_message_id": track_message.id})],
        })

        calls, patcher = capture_pbx_calls()
        with patcher:
            moh.name = "Renamed waiting music"

        self.assertEqual(len(calls_for(calls, "sync_moh")), 1)

    def test_unlink_deletes_pbx_resource(self):
        track_message = self._create_audio_message()
        moh = self.env["voip.music.on.hold"].create({
            "name": "Waiting music",
            "track_ids": [(0, 0, {"audio_message_id": track_message.id})],
        })

        calls, patcher = capture_pbx_calls()
        with patcher:
            moh.unlink()
            self.assertFalse(calls_for(calls, "delete_moh"))
            self.env.cr.postcommit.run()

        delete_call, = calls_for(calls, "delete_moh")
        self.assertEqual(delete_call["params"]["moh_uuid"], "pbx-moh-uuid")

    @mute_logger("odoo.sql_db")
    def test_unlink_still_fails_when_another_record_still_uses_it(self):
        """The Odoo-side rejection (enforced by a real DB foreign key on
        voip.queue.music_on_hold_id) must keep happening exactly as before.

        A caller could catch that failure inside its own savepoint and still
        commit the outer transaction; unlike a full Cursor.rollback(), a
        savepoint rollback doesn't clear postcommit (see Savepoint.rollback
        in odoo/sql_db.py), so the delete_moh call deferred by moh.unlink()
        would otherwise still reach Wazo for a deletion that, in the end,
        never happened. _call_after_commit_for_deleted guards against that
        by re-checking existence once the callback actually runs - proven
        here directly, without needing an outer commit."""
        track_message = self._create_audio_message()
        moh = self.env["voip.music.on.hold"].create({
            "name": "Waiting music",
            "track_ids": [(0, 0, {"audio_message_id": track_message.id})],
        })
        queue = self.env["voip.queue"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Blocking queue",
            "music_on_hold_id": moh.id,
        })

        calls, patcher = capture_pbx_calls()
        with patcher:
            with self.assertRaises(Exception):
                with self.env.cr.savepoint():
                    moh.unlink()
            self.env.cr.postcommit.run()

        self.assertFalse(calls_for(calls, "delete_moh"))
        self.assertTrue(moh.exists())
        self.assertEqual(queue.music_on_hold_id, moh)

    def test_track_requires_a_wav_audio_message(self):
        # The filename deliberately does not identify a WAV file.
        non_wav_message = self.env["voip.sound"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "name": "Not a WAV",
            **tts_sound_values("Hello"),
            "data_filename": "not-a-wav.mp3",
        })
        moh = self.env["voip.music.on.hold"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Waiting music",
        })

        with self.assertRaisesRegex(ValidationError, "WAV audio files"):
            self.env["voip.music.on.hold.track"].create({
                "music_on_hold_id": moh.id,
                "audio_message_id": non_wav_message.id,
            })
