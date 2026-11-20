"""Build and verify one Monster Hunter World: Iceborne PC BGM replacement."""
import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET

from delivery import safe_target, write_zip
from envutil import BUILD_TOOLS, load, require_tools, tool_issue
from npck import read_package, read_wem, validate_against


RATE = 48000


def run(*command):
    process = subprocess.run([str(arg) for arg in command], capture_output=True,
                             encoding="utf-8", errors="replace")
    if process.returncode:
        detail = (process.stderr or process.stdout).strip()
        raise ValueError(f"{Path(command[0]).name} returned {process.returncode}\n{detail[-2200:]}")
    return process.stdout


def wav_duration(ffprobe, path):
    info = json.loads(run(ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", path))
    try:
        return float(info["format"]["duration"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"unable to read WAV duration: {path.name}") from error


def process_audio(args, workspace, tools, channels):
    ffmpeg = tools["ffmpeg"]
    normalized = workspace / "normalized.wav"
    end = ["-t", str(args.trim_end - args.trim_start)] if args.trim_end is not None else []
    run(ffmpeg, "-nostdin", "-hide_banner", "-v", "error", "-xerror",
        "-i", args.source, "-ss", str(args.trim_start), *end, "-map", "0:a:0",
        "-ar", RATE, "-ac", 2, "-c:a", "pcm_s16le", normalized)
    duration = wav_duration(tools["ffprobe"], normalized)
    if duration <= 0:
        raise ValueError("audio is empty after trimming")
    fade_in = min(args.fade_in, duration / 2)
    fade_out = min(args.fade_out, duration / 2)
    peak = 10 ** (args.peak_db / 20)
    filters = [f"volume={args.gain_db}dB", f"alimiter=limit={peak}:level=false:latency=true"]
    if fade_in:
        filters.append(f"afade=t=in:d={fade_in}")
    if fade_out:
        filters.append(f"afade=t=out:st={duration-fade_out}:d={fade_out}")
    stereo = workspace / "replacement_2ch.wav"
    run(ffmpeg, "-nostdin", "-hide_banner", "-v", "error", "-xerror",
        "-i", normalized, "-af", ",".join(filters), "-c:a", "pcm_s16le", stereo)
    inputs = {}
    if 2 in channels:
        inputs[2] = stereo
    if 4 in channels:
        quad = workspace / "replacement_4ch.wav"
        run(ffmpeg, "-nostdin", "-hide_banner", "-v", "error", "-xerror",
            "-i", stereo, "-af", "pan=quad|FL=FL|FR=FR|BL=FL|BR=FR", "-c:a", "pcm_s16le", quad)
        inputs[4] = quad
    return stereo, inputs


def encode_wems(workspace, tools, inputs):
    wwise = tools["wwise"]
    project = workspace / "Bgm" / "Bgm.wproj"
    run(wwise, "create-new-project", project, "--platform", "Windows", "--quiet")
    sources = workspace / "conversion.wsources"
    root = ET.Element("ExternalSourcesList", SchemaVersion="1", Root=str(workspace))
    for path in inputs.values():
        ET.SubElement(root, "Source", Path=path.name, Conversion="Vorbis Quality High")
    ET.ElementTree(root).write(sources, encoding="utf-8", xml_declaration=True)
    output = workspace / "encoded"
    run(wwise, "convert-external-source", project, "--platform", "Windows",
        "--source-file", sources, "--output", output)
    result = {}
    for channels, path in inputs.items():
        candidates = list(output.rglob(path.with_suffix(".wem").name))
        if len(candidates) != 1:
            raise ValueError(f"Wwise did not create exactly one WEM for {path.name}")
        wem = candidates[0]
        with wem.open("rb") as stream:
            length, encoded_channels, rate = read_wem(stream, 0, wem.stat().st_size)
        if (encoded_channels, rate) != (channels, RATE):
            raise ValueError(f"Wwise encoding used unexpected channels or rate: {wem.name}")
        result[channels] = (wem, sha256(wem.read_bytes()[:length]).digest())
    return result


def verify_audio(workspace, tools, wems, inputs):
    duration_by_channels = {}
    for channels, (wem, _) in wems.items():
        ogg = workspace / f"verify_{channels}.ogg"
        run(tools["ww2ogg"], wem, "--pcb", tools["codebooks"], "-o", ogg)
        if "revorb" in tools:
            fixed = workspace / f"verify_fixed_{channels}.ogg"
            run(tools["revorb"], ogg, fixed)
            ogg = fixed
        stream_info = json.loads(run(tools["ffprobe"], "-v", "error", "-select_streams", "a:0",
                                     "-show_entries", "stream=channels,sample_rate", "-of", "json", ogg))
        streams = stream_info.get("streams", [])
        if not streams or (streams[0].get("channels"), int(streams[0].get("sample_rate", 0))) != (channels, RATE):
            raise ValueError(f"WEM roundtrip: invalid audio stream for {channels}ch")
        pcm = workspace / f"verify_{channels}.wav"
        run(tools["ffmpeg"], "-nostdin", "-hide_banner", "-v", "error", "-xerror",
            "-i", ogg, "-c:a", "pcm_s16le", pcm)
        duration = wav_duration(tools["ffprobe"], pcm)
        expected = wav_duration(tools["ffprobe"], inputs[channels])
        if duration <= 0 or abs(duration - expected) > 0.10:
            raise ValueError(f"WEM roundtrip: duration mismatch for {channels}ch ({duration:.3f} vs {expected:.3f}s)")
        duration_by_channels[str(channels)] = round(duration, 5)
    return duration_by_channels


def build(args, tools, slots, selected):
    if args.output.exists():
        raise ValueError("output directory already exists; choose a new path")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".mhwi-", dir=args.output.parent) as temp:
        workspace = Path(temp)
        audio, inputs = process_audio(args, workspace, tools, {slots[i - 1].channels for i in selected})
        wems = encode_wems(workspace, tools, inputs)
        duration = verify_audio(workspace, tools, wems, inputs)
        replacements = workspace / "slots"
        replacements.mkdir()
        media = {}
        for index in selected:
            wem, digest = wems[slots[index - 1].channels]
            shutil.copyfile(wem, replacements / f"{index}.wem")
            media[index] = digest
        package = workspace / args.target
        run(tools["wwiseutil"], "-replace", "-f", args.reference, "-t", replacements, "-o", package)
        validate_against(package, args.reference, media)

        zip_path = workspace / f"{package.stem}_mod.zip"
        write_zip(zip_path, [package])
        preview = workspace / "preview_stereo.mp3"
        run(tools["ffmpeg"], "-nostdin", "-hide_banner", "-v", "error", "-xerror",
            "-i", audio, "-c:a", "libmp3lame", "-b:a", "192k", preview)
        report = workspace / "verification.json"
        details = {"npck": args.target, "sample_rate": RATE, "reference_slots": len(slots),
                   "replaced_slots": [{"index": i, "media_id": slots[i - 1].media_id,
                                       "channels": slots[i - 1].channels} for i in selected],
                   "unchanged_slots_bytes_verified": len(slots) - len(selected),
                   "decoded_duration_seconds": duration, "game_test": "pending"}
        report.write_text(json.dumps(details, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        args.output.mkdir()
        for deliverable in (package, zip_path, preview, report):
            with deliverable.open("rb") as source, (args.output / deliverable.name).open("xb") as target:
                shutil.copyfileobj(source, target)
    print(f"RESULT: ALL OK (offline) | in-game playback: pending | {args.output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True, help="read-only vanilla NPCK")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", required=True, help="exact game filename, e.g. bgm_example.npck")
    parser.add_argument("--output", type=Path, required=True, help="new delivery directory")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all-slots", action="store_true")
    selection.add_argument("--slot", action="append", type=int, help="one-based slot, repeatable")
    parser.add_argument("--trim-start", type=float, default=0)
    parser.add_argument("--trim-end", type=float, help="end position on the original timeline")
    parser.add_argument("--gain-db", type=float, default=0)
    parser.add_argument("--peak-db", type=float, default=-1.5)
    parser.add_argument("--fade-in", type=float, default=0.15)
    parser.add_argument("--fade-out", type=float, default=1.2)
    args = parser.parse_args()
    try:
        env = load(args.env)
        tools = require_tools(env, BUILD_TOOLS, "build")
        revorb = env.get("revorb")
        if isinstance(revorb, dict) and revorb.get("status") == "ok":
            issue = tool_issue(env, "revorb")
            if issue:
                print(f"TOOL PREFLIGHT OPTIONAL (build): revorb: {issue['reason']}. Continuing without it.",
                      file=sys.stderr)
            else:
                tools["revorb"] = Path(revorb["path"])
        args.target = safe_target(args.target)
        if not args.source.is_file():
            raise ValueError("source audio is not a file")
        numbers = [args.trim_start, args.gain_db, args.peak_db, args.fade_in, args.fade_out]
        if args.trim_end is not None:
            numbers.append(args.trim_end)
        if not all(map(math.isfinite, numbers)) or min(args.trim_start, args.fade_in, args.fade_out) < 0:
            raise ValueError("invalid trim, gain, peak or fade")
        if not -24 <= args.peak_db <= 0:
            raise ValueError("--peak-db must be between -24 and 0")
        if args.trim_end is not None and args.trim_end <= args.trim_start:
            raise ValueError("--trim-end must be greater than --trim-start")
        args.output = args.output.resolve()
        args.reference = args.reference.resolve()
        args.source = args.source.resolve()
        slots = read_package(args.reference)
        selected = sorted(args.slot) if args.slot else list(range(1, len(slots) + 1))
        if len(set(selected)) != len(selected) or not all(1 <= i <= len(slots) for i in selected):
            raise ValueError("slots must be unique and within the reference table")
        if any((slots[i - 1].sample_rate != RATE or slots[i - 1].channels not in (2, 4)) for i in selected):
            raise ValueError("this build pipeline supports 48 kHz stereo and quad target slots only")
        game = env.get("game", {}).get("path")
        if game and args.output.is_relative_to(Path(game).resolve().parent):
            raise ValueError("choose an output directory outside the game installation")
        reference_name = args.reference.name.casefold().removeprefix("vanilla_")
        if reference_name.startswith("bgm_") and reference_name != args.target.casefold():
            raise ValueError("target filename differs from the known reference filename")
        build(args, tools, slots, selected)
    except (OSError, ValueError) as error:
        parser.exit(1, f"RESULT: PROBLEM FOUND — {error}\n")


if __name__ == "__main__":
    main()
