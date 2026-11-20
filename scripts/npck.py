"""Read and validate the little-endian, media-only AKPK layout used by MHWI BGM."""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import struct


@dataclass(frozen=True)
class Slot:
    media_id: int
    offset: int
    size: int
    riff_size: int
    channels: int
    sample_rate: int


def read_wem(stream, offset, size):
    stream.seek(offset)
    header = stream.read(12)
    if len(header) != 12:
        raise ValueError("WEM header is truncated")
    magic, length, form = struct.unpack("<4sI4s", header)
    riff_size = length + 8
    if magic != b"RIFF" or form != b"WAVE" or not 12 <= riff_size <= size:
        raise ValueError("invalid RIFF/WAVE signature or length")
    cursor = offset + 12
    end = offset + riff_size
    audio_format = None
    has_data = False
    while cursor + 8 <= end:
        stream.seek(cursor)
        tag, length = struct.unpack("<4sI", stream.read(8))
        cursor += 8 + length
        if cursor > end:
            raise ValueError("RIFF chunk extends past WEM")
        if tag == b"fmt ":
            if length < 16 or audio_format is not None:
                raise ValueError("incomplete or duplicate WEM fmt chunk")
            _, channels, rate = struct.unpack("<HHI", stream.read(8))
            if not channels or not rate:
                raise ValueError("invalid WEM channel count or sample rate")
            audio_format = channels, rate
        elif tag == b"data":
            if not length or has_data:
                raise ValueError("empty or duplicate WEM data chunk")
            has_data = True
        if length & 1 and cursor < end:
            cursor += 1
    if audio_format is None or not has_data or cursor != end:
        raise ValueError("missing WEM fmt or data chunk, or malformed RIFF padding")
    return (riff_size, *audio_format)


def zero_padding(stream, start, end):
    stream.seek(start)
    while start < end:
        block = stream.read(min(65536, end - start))
        if not block or any(block):
            return False
        start += len(block)
    return True


def read_package(path):
    with path.open("rb") as stream:
        total = stream.seek(0, 2)
        stream.seek(0)
        header = stream.read(28)
        if len(header) != 28:
            raise ValueError("truncated AKPK header")
        magic, header_size, version, languages, banks, media, external = struct.unpack("<4s6I", header)
        media_start = 28 + languages + banks
        header_end = media_start + media + external
        if (magic != b"AKPK" or version != 1 or banks != 4 or external != 4
                or media < 24 or header_end != header_size + 8 or header_end > total):
            raise ValueError("unsupported AKPK layout (expected MHWI media-only BGM NPCK)")
        stream.seek(media_start - 4)
        if stream.read(4) != bytes(4):
            raise ValueError("bank table is not empty")
        (count,) = struct.unpack("<I", stream.read(4))
        if media != 4 + 20 * count:
            raise ValueError("media table size does not match its entry count")
        entries = [struct.unpack("<5I", stream.read(20)) for _ in range(count)]
        if stream.read(4) != bytes(4):
            raise ValueError("external table is not empty")

        slots = []
        ids = set()
        end = header_end
        for index, (media_id, alignment, size, offset, reserved) in enumerate(entries, 1):
            if media_id in ids or alignment != 1 or reserved != 0:
                raise ValueError(f"slot {index}: duplicate ID or unsupported entry layout")
            if offset < end or size < 12 or offset + size > total:
                raise ValueError(f"slot {index}: overlapping or out-of-bounds media")
            if not zero_padding(stream, end, offset):
                raise ValueError(f"slot {index}: unexpected bytes before media")
            try:
                riff_size, channels, rate = read_wem(stream, offset, size)
            except ValueError as error:
                raise ValueError(f"slot {index}: {error}") from error
            if not zero_padding(stream, offset + riff_size, offset + size):
                raise ValueError(f"slot {index}: nonzero padding inside media entry")
            slots.append(Slot(media_id, offset, size, riff_size, channels, rate))
            ids.add(media_id)
            end = offset + size
        if end != total:
            raise ValueError("media end does not match file size")
        return slots


def media_digest(stream, slot):
    stream.seek(slot.offset)
    remaining = slot.riff_size
    digest = hashlib.sha256()
    while remaining:
        chunk = stream.read(min(1 << 20, remaining))
        if not chunk:
            raise ValueError("media changed while reading package")
        digest.update(chunk)
        remaining -= len(chunk)
    return digest.digest()


def validate_against(output, reference, modified=None):
    actual = read_package(output)
    expected = read_package(reference)
    if len(actual) != len(expected):
        raise ValueError(f"entry count differs: {len(actual)} vs {len(expected)}")
    if modified is not None and not modified.keys() <= set(range(1, len(expected) + 1)):
        raise ValueError("replacement slot is outside the reference")
    with output.open("rb") as result, reference.open("rb") as original:
        for index, (new, old) in enumerate(zip(actual, expected), 1):
            if (new.media_id, new.channels, new.sample_rate) != (old.media_id, old.channels, old.sample_rate):
                raise ValueError(f"slot {index}: media ID, channels or sample rate differs")
            if modified is not None:
                wanted = modified[index] if index in modified else media_digest(original, old)
                if media_digest(result, new) != wanted:
                    raise ValueError(f"slot {index}: media bytes differ from expected")
    return actual
