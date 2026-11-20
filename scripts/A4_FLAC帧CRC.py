"""Report zero-based indices of FLAC frames with invalid CRCs."""
import argparse
from pathlib import Path

from flac import inspect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    try:
        data = args.source.read_bytes()
        _, rate, _, frames = inspect(data)
        position = 0
        bad = []
        for i, frame in enumerate(frames):
            if not frame.good_crc(data):
                bad.append(i)
                print(f"frame #{i}: bytes [{frame.start}, {frame.end}), {position / rate:.3f}s")
            position += frame.samples
        print("bad frames: " + (",".join(map(str, bad)) if bad else "none"))
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
