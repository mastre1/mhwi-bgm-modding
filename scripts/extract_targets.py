"""Extract explicit NPCK candidates from a project-local chunk index."""
import argparse
import json
from pathlib import Path

from chunk_extract import BLOCK, ChunkFile, Decoder
from delivery import safe_target
from envutil import CHUNK_TOOLS, load, require_tools
from npck import read_package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="new directory outside the game")
    parser.add_argument("--candidate", type=int, action="append", required=True, help="one-based index entry, repeatable")
    args = parser.parse_args()
    try:
        tools = require_tools(load(args.env), CHUNK_TOOLS, "chunk")
        root = tools["game"]
        if args.output.resolve().is_relative_to(root.resolve().parent):
            raise ValueError("choose an output location outside the game directory")
        decoder = Decoder(tools)
        index = json.loads(args.index.read_text(encoding="utf-8"))
        if index.get("format") != 1 or not index.get("entries"):
            raise ValueError("unsupported or empty index")
        entries = index["entries"]
        selected = args.candidate
        if len(set(selected)) != len(selected) or not all(1 <= i <= len(entries) for i in selected):
            raise ValueError("candidate indices must be unique and present")
        args.output.mkdir(parents=True, exist_ok=False)
        for i in selected:
            entry = entries[i - 1]
            name = safe_target(entry["name"].replace("\\", "/").rsplit("/", 1)[-1])
            archive = (root / entry["chunk"]).resolve()
            if archive.parent != root.resolve() or not archive.match("chunkG*.bin"):
                raise ValueError("invalid archive name in index")
            stat = archive.stat()
            if (stat.st_size, stat.st_mtime_ns) != (entry["chunk_size"], entry["chunk_mtime_ns"]):
                raise ValueError(f"{archive.name} changed; scan the current installation again")
            offset, size = entry["offset"], entry["size"]
            if offset < 0 or size < 1:
                raise ValueError("invalid candidate offset or size")
            directory = args.output / f"{i:03d}_{archive.stem}"
            directory.mkdir()
            output = directory / name
            with archive.open("rb") as source, output.open("xb") as target:
                chunk = ChunkFile(source, decoder, entry["encrypted"])
                end = offset + size
                for block in range(offset // BLOCK, (end + BLOCK - 1) // BLOCK):
                    data = chunk.load_block(block)
                    block_start = block * BLOCK
                    first = max(0, offset - block_start)
                    last = min(BLOCK, end - block_start)
                    if not first < last <= len(data):
                        raise ValueError("truncated candidate data")
                    target.write(data[first:last])
            read_package(output)
            print(f"candidate {i}: {output}")
    except (OSError, AttributeError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
