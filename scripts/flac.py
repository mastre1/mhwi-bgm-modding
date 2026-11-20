"""Inspect native FLAC frame boundaries and CRCs for the optional salvage path."""
from dataclasses import dataclass
import struct


def crc_table(polynomial, bits):
    values = []
    for byte in range(256):
        c = byte << (bits - 8)
        for _ in range(8):
            c = (c << 1) ^ (polynomial if c & (1 << (bits - 1)) else 0)
            c &= (1 << bits) - 1
        values.append(c)
    return values


CRC8 = crc_table(7, 8)
CRC16 = crc_table(0x8005, 16)


def checksum(data, table, bits):
    crc = 0
    mask = (1 << bits) - 1
    for value in data:
        crc = ((crc << 8) & mask) ^ table[(crc >> (bits - 8)) ^ value]
    return crc


@dataclass(frozen=True)
class Frame:
    start: int
    end: int
    samples: int

    def good_crc(self, data):
        payload = memoryview(data)[self.start:self.end]
        return len(payload) >= 8 and checksum(payload, CRC16, 16) == 0


def header(data, offset):
    if offset + 6 > len(data) or data[offset] != 0xff or data[offset + 1] not in (0xf8, 0xf9):
        return None
    block, rate = divmod(data[offset + 2], 16)
    flags = data[offset + 3]
    if not block or rate == 15 or flags & 1 or flags >> 4 > 10:
        return None
    first = data[offset + 4]
    count = 1
    if first & 0x80:
        count = 0
        mask = 0x80
        while mask and first & mask:
            count += 1
            mask >>= 1
        if not 2 <= count <= 7 or (count == 7 and data[offset + 1] == 0xf8):
            return None
    position = offset + 4 + count
    if position >= len(data) or any(byte & 0xc0 != 0x80 for byte in data[offset + 5:position]):
        return None
    extra = {6: 1, 7: 2}.get(block, 0)
    crc_pos = position + extra + {12: 1, 13: 2, 14: 2}.get(rate, 0)
    if crc_pos >= len(data) or checksum(memoryview(data)[offset:crc_pos + 1], CRC8, 8):
        return None
    if extra:
        samples = int.from_bytes(data[position:position + extra], "big") + 1
        if samples == 65536:
            return None
    elif block < 6:
        samples = (0, 192, 576, 1152, 2304, 4608)[block]
    else:
        samples = 256 << (block - 8)
    return crc_pos + 1, samples


def inspect(data):
    if data[:4] != b"fLaC":
        raise ValueError("expected native FLAC (fLaC header)")
    pos = 4
    streaminfo = None
    while pos + 4 <= len(data):
        kind = data[pos]
        size = int.from_bytes(data[pos + 1:pos + 4], "big")
        end = pos + 4 + size
        if end > len(data):
            raise ValueError("truncated FLAC metadata")
        if streaminfo is None:
            if kind & 0x7f or size != 34:
                raise ValueError("missing FLAC STREAMINFO")
            streaminfo = data[pos + 4:end]
        pos = end
        if kind & 0x80:
            break
    else:
        raise ValueError("missing final metadata block")

    packed, = struct.unpack_from(">Q", streaminfo, 10)
    rate = packed >> 44
    if not rate:
        raise ValueError("invalid FLAC sample rate")
    return streaminfo, rate, packed & ((1 << 36) - 1), locate_frames(data, pos)


def locate_frames(data, offset):
    parsed = header(data, offset)
    if not parsed:
        raise ValueError("first FLAC frame header could not be established")
    frames = []
    while parsed:
        cursor, samples = parsed
        while True:
            next_frame = data.find(b"\xff", cursor)
            if next_frame < 0:
                frames.append(Frame(offset, len(data), samples))
                return frames
            parsed = header(data, next_frame)
            if parsed and data[next_frame + 1] == data[offset + 1]:
                break
            cursor = next_frame + 1
        frames.append(Frame(offset, next_frame, samples))
        offset = next_frame
    return frames


def segment_header(streaminfo, frames):
    result = bytearray(streaminfo)
    packed, = struct.unpack_from(">Q", result, 10)
    samples = sum(frame.samples for frame in frames)
    struct.pack_into(">Q", result, 10, (packed >> 36 << 36) | samples)
    result[18:34] = bytes(16)
    return b"fLaC\x80\x00\x00\x22" + result
