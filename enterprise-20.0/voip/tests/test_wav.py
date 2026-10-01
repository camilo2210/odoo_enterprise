import struct

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.voip.tools.wav import (
    decode_wav,
    decode_wav_samples,
    encode_wav,
    pack_int16_samples,
    resample_wav_samples,
)


def _fmt_chunk(
    audio_format=1, channels=1, frame_rate=8000, bits_per_sample=16, block_align=None,
):
    if block_align is None:
        block_align = channels * (bits_per_sample // 8)
    byte_rate = frame_rate * block_align
    return b"fmt " + struct.pack("<I", 16) + struct.pack(
        "<HHIIHH", audio_format, channels, frame_rate, byte_rate, block_align, bits_per_sample,
    )


def _wav(fmt_chunk, data_chunk):
    body = b"WAVE" + fmt_chunk + data_chunk
    return b"RIFF" + struct.pack("<I", len(body)) + body


def _data_chunk(frames):
    return b"data" + struct.pack("<I", len(frames)) + frames


@tagged("voip", "post_install", "-at_install")
class TestWav(TransactionCase):
    def test_encode_decode_wav_round_trip(self):
        frames = pack_int16_samples([0, 100, -100, 32767, -32768])
        content = encode_wav(frames, channels=1, sample_width=2, frame_rate=8000)

        decoded_frames, channels, sample_width, frame_rate = decode_wav(content)

        self.assertEqual(decoded_frames, frames)
        self.assertEqual(channels, 1)
        self.assertEqual(sample_width, 2)
        self.assertEqual(frame_rate, 8000)

    def test_decode_wav_rejects_too_short_or_bad_magic(self):
        with self.assertRaisesRegex(UserError, "valid WAV file"):
            decode_wav(b"tooshort")
        with self.assertRaisesRegex(UserError, "valid WAV file"):
            decode_wav(b"XXXX" + struct.pack("<I", 4) + b"XXXX")

    def test_decode_wav_rejects_chunk_overrunning_the_buffer(self):
        malformed = b"RIFF" + struct.pack("<I", 100) + b"WAVE" + b"fmt " + struct.pack("<I", 1000)
        with self.assertRaisesRegex(UserError, "valid WAV file"):
            decode_wav(malformed)

    def test_decode_wav_rejects_missing_data_chunk(self):
        content = _wav(_fmt_chunk(), b"")
        with self.assertRaisesRegex(UserError, "valid WAV file"):
            decode_wav(content)

    def test_decode_wav_accepts_open_ended_data_chunk(self):
        frames = pack_int16_samples([0, 100, -100])
        for chunk_size in (0x7FFFFFFF, 0xFFFFFFFF):
            with self.subTest(chunk_size=chunk_size):
                content = _wav(
                    _fmt_chunk(),
                    b"data" + struct.pack("<I", chunk_size) + frames,
                )

                decoded_frames, channels, sample_width, frame_rate = decode_wav(content)

                self.assertEqual(decoded_frames, frames)
                self.assertEqual(channels, 1)
                self.assertEqual(sample_width, 2)
                self.assertEqual(frame_rate, 8000)

    def test_decode_wav_rejects_missing_fmt_chunk(self):
        content = _wav(b"", _data_chunk(pack_int16_samples([1, 2, 3])))
        with self.assertRaisesRegex(UserError, "valid WAV file"):
            decode_wav(content)

    def test_decode_wav_rejects_non_pcm_format(self):
        # audio_format=3 is IEEE float, not the PCM (1) this module supports.
        content = _wav(
            _fmt_chunk(audio_format=3), _data_chunk(pack_int16_samples([1, 2, 3])),
        )
        with self.assertRaisesRegex(UserError, "uncompressed"):
            decode_wav(content)

    def test_decode_wav_rejects_frame_length_not_matching_block_align(self):
        content = _wav(_fmt_chunk(channels=2), _data_chunk(b"\x00\x01\x02"))
        with self.assertRaisesRegex(UserError, "uncompressed"):
            decode_wav(content)

    def test_decode_wav_samples_8_bit_is_centered_on_128(self):
        # 8-bit WAV samples are unsigned, centered on 128; 0 and 255 are the
        # extremes and must map to the most negative/positive 16-bit values.
        samples = decode_wav_samples(bytes([128, 0, 255]), sample_width=1, channels=1)
        self.assertEqual(samples, [0, -32768, 32512])

    def test_decode_wav_samples_32_bit_keeps_the_high_16_bits(self):
        frames = struct.pack("<2i", 1 << 20, -(1 << 20))
        samples = decode_wav_samples(frames, sample_width=4, channels=1)
        self.assertEqual(samples, [16, -16])

    def test_decode_wav_samples_rejects_unsupported_sample_width(self):
        with self.assertRaisesRegex(UserError, "8, 16, or 32-bit"):
            decode_wav_samples(b"\x00\x00\x00", sample_width=3, channels=1)

    def test_decode_wav_samples_downmixes_multiple_channels_to_mono(self):
        frames = pack_int16_samples([100, 200, -100, -300])
        samples = decode_wav_samples(frames, sample_width=2, channels=2)
        self.assertEqual(samples, [150, -200])

    def test_pack_int16_samples_empty_list_yields_no_frames(self):
        self.assertEqual(pack_int16_samples([]), b"")

    def test_resample_wav_samples_edge_cases_are_returned_unchanged(self):
        self.assertEqual(resample_wav_samples([], 8000, 16000), [])
        self.assertEqual(resample_wav_samples([42], 8000, 16000), [42])

    def test_resample_wav_samples_upsamples_linearly(self):
        resampled = resample_wav_samples([0, 100], 8000, 16000)
        self.assertEqual(len(resampled), 4)
        self.assertEqual(resampled[0], 0)
        self.assertEqual(resampled[-1], 100)

    def test_resample_wav_samples_downsamples(self):
        resampled = resample_wav_samples([0, 100, 200, 300], 16000, 8000)
        self.assertEqual(len(resampled), 2)
        self.assertEqual(resampled[0], 0)
        self.assertEqual(resampled[-1], 200)
