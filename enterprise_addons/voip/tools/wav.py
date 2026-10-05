import struct

from odoo.exceptions import UserError
from odoo.tools import LazyTranslate


_lt = LazyTranslate(__name__, default_lang="en_US")

_OPEN_ENDED_DATA_CHUNK_SIZES = (0x7FFFFFFF, 0xFFFFFFFF)


def decode_wav(content):
    """Parse a RIFF/WAVE byte string and return (frames, channels, sample_width, frame_rate)."""
    if len(content) < 12 or content[:4] != b"RIFF" or content[8:12] != b"WAVE":
        raise UserError(_lt("The file must be a valid WAV file."))

    wav_format = None
    frames = None
    offset = 12
    while offset + 8 <= len(content):
        chunk_id, chunk_size = struct.unpack_from("<4sI", content, offset)
        offset += 8
        chunk_end = (
            len(content)
            if chunk_id == b"data" and chunk_size in _OPEN_ENDED_DATA_CHUNK_SIZES
            else offset + chunk_size
        )
        if chunk_end > len(content):
            raise UserError(_lt("The file must be a valid WAV file."))
        if chunk_id == b"fmt " and chunk_size >= 16:
            wav_format = struct.unpack_from("<HHIIHH", content, offset)
        elif chunk_id == b"data":
            frames = content[offset:chunk_end]
        offset = chunk_end + (chunk_size % 2)

    if not wav_format or frames is None:
        raise UserError(_lt("The file must be a valid WAV file."))
    audio_format, channels, frame_rate, _byte_rate, block_align, bits_per_sample = wav_format
    sample_width = bits_per_sample // 8
    if (
        audio_format != 1
        or channels <= 0
        or frame_rate <= 0
        or bits_per_sample % 8
        or block_align != channels * sample_width
        or len(frames) % block_align
    ):
        raise UserError(_lt("The WAV file must be uncompressed (PCM)."))
    return frames, channels, sample_width, frame_rate


def encode_wav(frames, *, channels, sample_width, frame_rate):
    """Build a RIFF/WAVE byte string from raw PCM frames."""
    block_align = channels * sample_width
    byte_rate = frame_rate * block_align
    return b"".join((
        b"RIFF",
        struct.pack("<I", 36 + len(frames)),
        b"WAVEfmt ",
        struct.pack(
            "<IHHIIHH",
            16,
            1,
            channels,
            frame_rate,
            byte_rate,
            block_align,
            sample_width * 8,
        ),
        b"data",
        struct.pack("<I", len(frames)),
        frames,
    ))


def pack_int16_samples(samples):
    """Pack a list of 16-bit signed samples into raw little-endian PCM frames."""
    return struct.pack(f"<{len(samples)}h", *samples) if samples else b""


def decode_wav_samples(frames, sample_width, channels):
    """Decode raw PCM frames into a flat list of 16-bit signed samples, downmixed to mono."""
    if sample_width == 1:
        samples = [(sample - 128) * 256 for sample in frames]
    elif sample_width == 2:
        samples = struct.unpack(f"<{len(frames) // sample_width}h", frames)
    elif sample_width == 4:
        # Integer division by 65536 truncates toward -inf, equivalent to an
        # arithmetic right shift by 16 bits for signed values: it keeps the
        # most significant 16 bits of each 32-bit sample.
        samples = [
            sample // 65536
            for sample in struct.unpack(f"<{len(frames) // sample_width}i", frames)
        ]
    else:
        raise UserError(_lt("The WAV file must use 8, 16, or 32-bit samples."))

    if channels == 1:
        return list(samples)

    return [
        sum(samples[index:index + channels]) // channels
        for index in range(0, len(samples), channels)
    ]


def resample_wav_samples(samples, source_frame_rate, target_frame_rate):
    """Linearly resample a list of mono samples from one frame rate to another."""
    if not samples:
        return []
    if len(samples) == 1:
        return samples

    target_length = max(1, round(len(samples) * target_frame_rate / source_frame_rate))
    ratio = source_frame_rate / target_frame_rate
    resampled = []
    for index in range(target_length):
        position = min(index * ratio, len(samples) - 1)
        left_index = int(position)
        right_index = min(left_index + 1, len(samples) - 1)
        fraction = position - left_index
        sample = round(
            samples[left_index] * (1 - fraction)
            + samples[right_index] * fraction
        )
        resampled.append(max(-32768, min(32767, sample)))
    return resampled
