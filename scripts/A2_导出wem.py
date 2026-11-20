"""Export selected WEM slots to a new directory for local inspection."""
import argparse
from pathlib import Path

from npck import read_package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("outdir", type=Path)
    parser.add_argument("--slot", type=int, action="append", help="one-based slot (repeatable); default: all")
    args = parser.parse_args()
    try:
        slots = read_package(args.file)
        selected = args.slot if args.slot else range(1, len(slots) + 1)
        if any(index < 1 or index > len(slots) for index in selected):
            raise ValueError("requested slot is outside the package")
        if len(set(selected)) != len(selected):
            raise ValueError("duplicate slot")
        args.outdir.mkdir(parents=True, exist_ok=False)
        with args.file.open("rb") as source:
            for index in selected:
                slot = slots[index - 1]
                source.seek(slot.offset)
                path = args.outdir / f"{index}.wem"
                path.write_bytes(source.read(slot.riff_size))
                print(path)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
