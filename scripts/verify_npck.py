"""Validate a finished BGM NPCK against its vanilla reference."""
import argparse
from pathlib import Path
import sys

from npck import validate_against


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("reference", type=Path)
    args = parser.parse_args()
    try:
        slots = validate_against(args.output, args.reference)
    except (OSError, ValueError) as error:
        print(f"RESULT: PROBLEM FOUND — {error}", file=sys.stderr)
        return 1
    print(f"entries: {len(slots)}")
    for index, slot in enumerate(slots, 1):
        print(f"  e{index:02} id={slot.media_id:#010x} ch={slot.channels} sr={slot.sample_rate} RIFF-OK idOK")
    print("RESULT: ALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
