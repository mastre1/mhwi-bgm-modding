"""Inspect the FLAC frame timeline using the source sample rate."""
import argparse
from pathlib import Path

from flac import inspect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("seconds", type=float, nargs="?")
    args = parser.parse_args()
    try:
        _, rate, _, frames = inspect(args.source.read_bytes())
        position = 0
        for index, frame in enumerate(frames):
            start = position / rate
            position += frame.samples
            if args.seconds is not None and abs(start - args.seconds) <= 1:
                print(f"frame #{index}: [{start:.3f}, {position / rate:.3f})s, {frame.samples} samples")
        print(f"{len(frames)} frames, {position} samples at {rate} Hz, {position / rate:.3f}s")
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
