"""Salvage a native FLAC by explicitly excluding diagnosed, zero-based frame indices."""
import argparse
from itertools import groupby
from pathlib import Path
from tempfile import TemporaryDirectory
import wave

from envutil import ffmpeg_path, load
from flac import inspect, segment_header
from make_mod import run


def repair(source, output, bad, trim_tail, ffmpeg):
    if output.exists():
        raise ValueError("output directory already exists")
    data = source.read_bytes()
    streaminfo, _, _, frames = inspect(data)
    if not bad and not trim_tail:
        raise ValueError("provide diagnosed --bad indices or an explicit --trim-tail")
    if not 0 <= trim_tail < len(frames) or any(i < 0 or i >= len(frames) for i in bad):
        raise ValueError("frame indices or tail count are out of range")
    retained = []
    for keep, run_frames in groupby(enumerate(frames), lambda pair: pair[0] not in bad
                                    and pair[0] < len(frames) - trim_tail):
        if not keep:
            continue
        segment = []
        for index, frame in run_frames:
            if not frame.good_crc(data):
                raise ValueError(f"retained frame #{index} has an invalid CRC; inspect with A4")
            segment.append(frame)
        retained.append(segment)
    if not retained:
        raise ValueError("all frames would be excluded")

    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as directory:
        work = Path(directory)
        decoded = []
        for i, segment in enumerate(retained):
            cut = work / f"{i}.flac"
            with cut.open("wb") as stream:
                stream.write(segment_header(streaminfo, segment))
                for frame in segment:
                    stream.write(memoryview(data)[frame.start:frame.end])
            wav = cut.with_suffix(".wav")
            run(ffmpeg, "-nostdin", "-v", "error", "-xerror", "-i", cut,
                "-ar", 48000, "-ac", 2, "-c:a", "pcm_s16le", wav)
            with wave.open(str(wav), "rb") as stream:
                sample_count = stream.getnframes()
            if not sample_count:
                raise ValueError("a salvaged segment decoded to no audio")
            decoded.append((wav, sample_count))

        current, current_samples = decoded[0]
        for i, (wav, sample_count) in enumerate(decoded[1:], 1):
            joined = work / f"join_{i}.wav"
            fade = min(1920, current_samples // 2, sample_count // 2)
            filter_graph = f"acrossfade=ns={fade}" if fade else "concat=n=2:v=0:a=1"
            run(ffmpeg, "-nostdin", "-v", "error", "-xerror", "-i", current, "-i", wav,
                "-filter_complex", f"[0:a][1:a]{filter_graph}[audio]", "-map", "[audio]",
                "-c:a", "pcm_s16le", joined)
            current, current_samples = joined, current_samples + sample_count - fade
        output.mkdir()
        current.rename(output / "repaired.wav")
        print(f"{output / 'repaired.wav'} | 48000 Hz stereo | {current_samples / 48000:.3f}s")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path, help="new directory containing repaired.wav")
    parser.add_argument("--bad", default="", help="comma-separated zero-based frame indices from A4")
    parser.add_argument("--trim-tail", default=0, type=int)
    parser.add_argument("--ffmpeg")
    parser.add_argument("--env", type=Path)
    args = parser.parse_args()
    try:
        ffmpeg = ffmpeg_path(load(args.env), args.ffmpeg)
        exclude = {int(index) for index in args.bad.split(",")} if args.bad else set()
        repair(args.source, args.output, exclude, args.trim_tail, ffmpeg)
    except (OSError, ValueError, wave.Error) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
