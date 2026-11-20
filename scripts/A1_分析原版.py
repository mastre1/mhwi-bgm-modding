"""Print the slot, media ID, channel count, and sample rate of each BGM WEM."""
import argparse
from pathlib import Path

from npck import read_package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", type=Path, nargs="+")
    args = parser.parse_args()
    try:
        for path in args.files:
            slots = read_package(path)
            print(f"{path}: {len(slots)} slots")
            for index, slot in enumerate(slots, 1):
                print(f"  e{index:02} id={slot.media_id:#010x} size={slot.size} ch={slot.channels} sr={slot.sample_rate}")
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
