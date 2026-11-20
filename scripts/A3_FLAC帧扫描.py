"""Inspect FLAC framing, sample rate, and stream length."""
import argparse
from collections import Counter
from pathlib import Path

from flac import inspect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    try:
        _, rate, declared, frames = inspect(args.source.read_bytes())
        total = sum(frame.samples for frame in frames)
        print(f"sample rate: {rate}; declared samples: {declared}; scanned samples: {total}")
        print(f"frames: {len(frames)}; block sizes: {dict(Counter(frame.samples for frame in frames))}")
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
