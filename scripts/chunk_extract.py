"""Index BGM candidates in local MHWI chunkG archives. Never writes into the game."""
import argparse
import ctypes
import json
from pathlib import Path
import struct
import sys

from envutil import CHUNK_TOOLS, load, require_tools


BLOCK = 0x40000

# Key schedule for the supported MHWI chunkG format. The sequence and Oodle library
# are local inputs and are not required for the normal build path.
KEYS = tuple(map(bytes.fromhex, (
    "ac76cb97ec7500133a81038e7a82c80a", "6bb5c956e44d00bc305233cfbfaafa25",
    "8f021dccb0f2787206fbdee2390bbb5c", "da5c1e531d8359157875bd63bfaafa25",
    "1f6d31c883dd716d7e8f598ce23f1929", "4bb0de04e4e0856980ccb2942f9ce9f9",
    "8bce54dc4c11139a7875bd63bfaafa25", "ec13345966ce7312440089a2ceddcee9",
    "e4662c709c753a039a2c0f5ae23f1929", "a492fc9033949c15a033ac223735cca7",
    "25099c1f911a26e5ce9172f07a82c80a", "d1d29d7446d4fdf1a033ac223735cca7",
    "7eb268373b5d361ed6d313e2933c4dcb", "a1c7d2ea661895ac7875bd63bfaafa25",
    "82a43b2108797c6a440089a2ceddcee9", "41d055b3dd6015167e8f598ce23f1929",
)))


class Decoder:
    def __init__(self, tools):
        try:
            self.sequence = tools["keyseq"].read_bytes()
            if len(self.sequence) <= 8:
                raise ValueError("sequence is too short")
        except (OSError, ValueError) as error:
            raise ValueError(f"keyseq: {error}. Set --keyseq in env_check.py --stage chunk.") from error
        try:
            self.library = ctypes.CDLL(str(tools["oodle"]))
            self.decompress = self.library.OodleLZ_Decompress
        except (OSError, AttributeError) as error:
            raise ValueError(f"oodle: {error}. Set --oodle in env_check.py --stage chunk.") from error
        self.decompress.argtypes = [
            ctypes.c_char_p, ctypes.c_longlong, ctypes.c_char_p, ctypes.c_longlong,
            ctypes.c_uint, ctypes.c_uint, ctypes.c_ulonglong, *([ctypes.c_uint] * 7),
        ]
        self.decompress.restype = ctypes.c_int

    def decode(self, block, index, compressed, encrypted):
        if compressed:
            output = ctypes.create_string_buffer(BLOCK)
            size = self.decompress(block, len(block), output, BLOCK, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3)
            if not 0 < size <= BLOCK:
                raise ValueError(f"Oodle failed at block {index}")
            block = output.raw[:size]
        if encrypted:
            key = KEYS[self.sequence[index + 8]]
            mask = (key * (len(block) // len(key) + 1))[:len(block)]
            block = (int.from_bytes(block, "little") ^ int.from_bytes(mask, "little")).to_bytes(len(block), "little")
        return block


class ChunkFile:
    def __init__(self, stream, decoder, encrypted):
        self.stream = stream
        self.decoder = decoder
        self.encrypted = encrypted
        self.length = stream.seek(0, 2)
        stream.seek(4)
        header = stream.read(4)
        if len(header) != 4:
            raise ValueError("truncated chunk header")
        self.count, = struct.unpack("<i", header)
        if not 0 < self.count <= (self.length - 8) // 8:
            raise ValueError("invalid block count")
        self.index = stream.read(self.count * 8)
        self.blocks = 0
        self.table = bytearray()

    def load_block(self, index):
        if not 0 <= index < self.count:
            raise ValueError(f"chunk block {index} is out of range")
        start = index * 8
        size_word = int.from_bytes(self.index[start:start + 3], "little")
        # The low nibble of the decoded size field contributes to the length.
        header_byte = self.index[start]
        size_word = size_word & ~255 | header_byte >> 4
        size = (size_word >> 4) + (size_word & 15)
        offset = int.from_bytes(self.index[start + 3:start + 8], "little")
        if not 8 + len(self.index) <= offset < self.length or offset + size > self.length:
            raise ValueError(f"invalid block location {index}")
        self.stream.seek(offset)
        data = self.stream.read(size or BLOCK)
        return self.decoder.decode(data, index, bool(size), self.encrypted)

    def ensure(self, size):
        while len(self.table) < size and self.blocks < self.count:
            self.table.extend(self.load_block(self.blocks))
            self.blocks += 1
        if len(self.table) < size:
            raise ValueError("truncated file table")


def parse_table(chunk):
    chunk.ensure(0x110)
    parents, children = struct.unpack_from("<ii", chunk.table, 0x0C)
    if not 0 <= parents <= 100_000 or not 0 <= children <= 1_000_000:
        raise ValueError("implausible file table counts")
    if not parents:
        raise ValueError("file table contains no directories")
    position = 0x100
    files = []
    for _ in range(parents):
        chunk.ensure(position + 0x3C + 24)
        _, _, _, count = struct.unpack_from("<qqii", chunk.table, position + 0x3C)
        position += 0x3C + 24
        if not 0 <= count <= 1_000_000 - len(files):
            raise ValueError("invalid child count")
        for _ in range(count):
            chunk.ensure(position + 0xA0 + 24)
            name = bytes(chunk.table[position:position + 0xA0]).split(b"\0", 1)[0].decode("ascii", "replace")
            size, offset, _, _ = struct.unpack_from("<qqii", chunk.table, position + 0xA0)
            position += 0xA0 + 24
            if not name or size < 0 or offset < 0 or offset + size > chunk.count * BLOCK:
                raise ValueError("invalid file entry")
            files.append((name, size, offset))
    return files


def scan_archive(path, decoder):
    errors = []
    for encrypted in (True, False):
        try:
            with path.open("rb") as stream:
                files = parse_table(ChunkFile(stream, decoder, encrypted))
            return files, encrypted
        except (IndexError, ValueError, struct.error) as error:
            errors.append(str(error))
    raise ValueError(f"{path.name}: cannot read file table ({'; '.join(errors)})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", type=Path, required=True, help="config from env_check.py --stage chunk")
    parser.add_argument("--index", type=Path, required=True, help="new project-local JSON file")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--target", action="append", help="exact NPCK basename; repeatable")
    selection.add_argument("--list-bgm", action="store_true", help="list possible BGM NPCKs")
    args = parser.parse_args()
    try:
        tools = require_tools(load(args.env), CHUNK_TOOLS, "chunk")
        root = tools["game"]
        if args.index.exists():
            raise ValueError("index already exists; choose a new file")
        if args.index.resolve().is_relative_to(root.resolve().parent):
            raise ValueError("choose an index location outside the game directory")
        targets = {name.casefold() for name in args.target or []}
        decoder = Decoder(tools)
        paths = sorted(root.glob("chunkG*.bin"))
        if not paths:
            raise ValueError("no supported chunkG*.bin files found")
        entries = []
        skipped = []
        for path in paths:
            try:
                table, encrypted = scan_archive(path, decoder)
            except ValueError as error:
                skipped.append(str(error))
                print(error, file=sys.stderr)
                continue
            stat = path.stat()
            count = 0
            for game_name, size, offset in table:
                name = game_name.replace("\\", "/").rsplit("/", 1)[-1].casefold()
                if name not in targets and not (args.list_bgm and name.startswith("bgm") and name.endswith(".npck")):
                    continue
                entries.append({"name": game_name, "chunk": path.name, "offset": offset,
                                "size": size, "encrypted": encrypted, "chunk_size": stat.st_size,
                                "chunk_mtime_ns": stat.st_mtime_ns})
                count += 1
            print(f"{path.name}: {count} candidates", file=sys.stderr)
        if not entries:
            raise ValueError("no matching BGM NPCK found in the scanned chunkG archives")
        with args.index.open("x", encoding="utf-8") as stream:
            json.dump({"format": 1, "entries": entries, "skipped_archives": skipped}, stream,
                      indent=2, ensure_ascii=False)
            stream.write("\n")
        print(f"{len(entries)} candidates in {args.index}")
    except (OSError, AttributeError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
