"""Discover dependencies for an MHWI BGM job and optionally save absolute paths."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from envutil import BUILD_TOOLS, CHUNK_TOOLS, SKILL_ROOT, missing_tools, preflight_message


MIN_WWISE = (2025, 1, 12)


def resolve_candidate(candidate):
    path = Path(candidate).expanduser()
    if path.is_file():
        return path.resolve()
    resolved = shutil.which(str(candidate))
    return Path(resolved).resolve() if resolved else None


def find_tool(override, command, *candidates):
    if override:
        return resolve_candidate(override)
    for candidate in (command, *candidates):
        if candidate:
            hit = resolve_candidate(candidate)
            if hit:
                return hit
    return None


def wwise_candidates():
    root = os.environ.get("WWISEROOT")
    locations = [Path(root)] if root else []
    drive = os.environ.get("SystemDrive", "C:")
    for install_root in (Path(drive + "/Audiokinetic"),
                         Path(os.environ.get("ProgramFiles", drive + "/Program Files")) / "Audiokinetic",
                         Path(os.environ.get("ProgramFiles(x86)", drive + "/Program Files (x86)")) / "Audiokinetic"):
        locations.extend(install_root.glob("Wwise_*"))
    suffix = Path("Authoring/x64/Release/bin/WwiseConsole.exe")
    def version_key(path):
        match = re.search(r"Wwise_(\d+)\.(\d+)\.(\d+)", path.name, flags=re.IGNORECASE)
        return tuple(map(int, match.groups())) if match else MIN_WWISE

    return [path / suffix for path in sorted(locations, key=version_key, reverse=True)]


def probe(path, *args):
    try:
        return subprocess.run([str(path), *args], capture_output=True, encoding="utf-8",
                              errors="replace", timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None


def check_wwise(path):
    result = probe(path, "--version") if path else None
    output = (result.stdout + result.stderr) if result else ""
    match = re.search(r"\bWwise\s*\|\s*v?(\d+)\.(\d+)\.(\d+)", output, flags=re.IGNORECASE)
    version = tuple(map(int, match.groups())) if match else None
    if version is None or version < MIN_WWISE:
        return "need runnable WwiseConsole 2025.1.12 or newer"
    return None


def check_ffmpeg(path):
    for flag, names in (("-filters", ("pan", "afade", "volume", "alimiter", "loudnorm")),
                        ("-encoders", ("libmp3lame",))):
        result = probe(path, "-hide_banner", flag)
        if result is None or result.returncode:
            return f"unable to run ffmpeg {flag}"
        missing = [name for name in names if not re.search(r"(?m)^\s*[A-Z.]+\s+" + name + r"\s", result.stdout)]
        if missing:
            return "missing " + ", ".join(missing)
    return None


def game_chunk(path):
    if not path:
        return None
    root = Path(path).expanduser().resolve()
    for location in (root / "chunk", root):
        if location.is_dir() and next(location.glob("chunkG*.bin"), None):
            return location
    return None


def entry(path, error=None):
    return {"path": str(path) if path else None,
            "status": error or ("ok" if path else "missing")}


def collect(args):
    tools = args.tools_dir.resolve() if args.tools_dir else SKILL_ROOT / "tools"
    env = {}
    if args.stage == 'build':
        if args.game:
            env['game'] = entry(game_chunk(args.game))
        ff = find_tool(args.ffmpeg, "ffmpeg")
        sibling = ff.with_name("ffprobe.exe" if os.name == "nt" else "ffprobe") if ff else None
        fp = find_tool(args.ffprobe, "ffprobe", sibling)
        ww = find_tool(args.wwise, os.environ.get("WWISECONSOLE") or "WwiseConsole.exe", *wwise_candidates())
        packer = find_tool(args.wwiseutil, "wwiseutil.exe", tools / "wwiseutil.exe")
        decoder = find_tool(args.ww2ogg, "ww2ogg.exe", tools / "ww2ogg/ww2ogg.exe")
        books_name = "packed_codebooks_aoTuV_603.bin"
        books = find_tool(args.codebooks, books_name,
                          decoder.with_name(books_name) if decoder else None,
                          tools / "ww2ogg" / books_name)
        revorb = find_tool(args.revorb, "revorb.exe", tools / "ww2ogg/revorb.exe")
        env.update(wwise=entry(ww, check_wwise(ww) if ww else None),
                   ffmpeg=entry(ff, check_ffmpeg(ff) if ff else None),
                   ffprobe=entry(fp, None if not fp else version_status(fp)),
                   wwiseutil=entry(packer), ww2ogg=entry(decoder), codebooks=entry(books),
                   revorb=entry(revorb))
        required = BUILD_TOOLS
        if args.game:
            required += ('game',)
        if args.revorb:
            required += ("revorb",)
    else:
        required = CHUNK_TOOLS
        env.update(game=entry(game_chunk(args.game)),
                   oodle=entry(find_tool(args.oodle, "oodle.dll", tools / "chunk/oodle.dll")),
                   keyseq=entry(find_tool(args.keyseq, "keyseq.key", tools / "chunk/keyseq.key")))
    env["optional_numpy"] = importlib.util.find_spec("numpy") is not None
    return env, required


def version_status(path):
    result = probe(path, "-version")
    return None if result and result.returncode == 0 and "ffprobe version" in result.stdout else "unable to run ffprobe"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("build", "chunk"), default="build")
    parser.add_argument("--out", type=Path, help="write a new config file, including partial status on failure")
    parser.add_argument("--tools-dir", type=Path)
    for option in ("wwise", "ffmpeg", "ffprobe", "wwiseutil", "ww2ogg", "codebooks",
                   "revorb", "game", "oodle", "keyseq"):
        parser.add_argument(f"--{option}")
    args = parser.parse_args()
    env, required = collect(args)
    missing = missing_tools(env, required)
    optional = ("revorb",) if args.stage == "build" and not args.revorb else ()
    env["_preflight"] = {"stage": args.stage, "ready": not missing, "missing": missing,
                         "optional_missing": missing_tools(env, optional)}
    print(json.dumps(env, ensure_ascii=False, indent=2))
    if missing:
        print(preflight_message(args.stage, missing), file=sys.stderr)
    if args.out:
        try:
            with args.out.open("x", encoding="utf-8") as stream:
                json.dump(env, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
        except OSError as error:
            parser.exit(1, f"{error}\n")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
