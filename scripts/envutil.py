"""Load project configuration and report tool availability before a job starts."""
import json
import os
from pathlib import Path
import shutil


SKILL_ROOT = Path(__file__).resolve().parents[1]
BUILD_TOOLS = ("wwise", "ffmpeg", "ffprobe", "wwiseutil", "ww2ogg", "codebooks")
CHUNK_TOOLS = ("game", "oodle", "keyseq")
TOOL_SOURCES = {
    "wwise": "Install Audiokinetic Wwise Authoring 2025.1.12+: https://www.audiokinetic.com/en/download/",
    "ffmpeg": "Install a full FFmpeg build: https://ffmpeg.org/download.html",
    "ffprobe": "Use ffprobe from the same FFmpeg build: https://ffmpeg.org/download.html",
    "wwiseutil": "Get the 1.1 CLI: https://github.com/hpxro7/wwiseutil/releases/tag/1.1",
    "ww2ogg": "Get the 0.22 CLI: https://github.com/hcs64/ww2ogg/releases/tag/0.22",
    "codebooks": "Use packed_codebooks_aoTuV_603.bin from ww2ogg 0.22: https://github.com/hcs64/ww2ogg/releases/tag/0.22",
    "revorb": "Use an existing trusted revorb.exe, or omit this optional tool.",
    "game": "Use the local Steam game directory containing the chunkG archives.",
    "oodle": "Use the locally available, compatible Oodle DLL.",
    "keyseq": "Use the local key sequence that matches the installed game archives.",
}


def load(explicit=None):
    named = explicit or os.environ.get("MHW_BGM_ENV")
    path = Path(named) if named else Path("env.json")
    if not named and not path.is_file():
        return {}
    try:
        with path.open(encoding="utf-8-sig") as stream:
            env = json.load(stream)
    except (OSError, ValueError) as error:
        raise ValueError(f"cannot read {path}: {error}. Regenerate it with env_check.py.") from error
    if not isinstance(env, dict):
        raise ValueError(f"invalid configuration in {path}. Regenerate it with env_check.py.")
    return env


def ffmpeg_path(env, override=None):
    record = env.get("ffmpeg")
    configured = record.get("path") if isinstance(record, dict) else None
    candidate = override or configured or "ffmpeg"
    path = Path(candidate).expanduser()
    if path.is_file():
        return str(path.resolve())
    command = shutil.which(candidate)
    if command:
        return command
    raise ValueError(f"TOOL PREFLIGHT FAILED: ffmpeg executable unavailable: {candidate}. "
                     f"Set --ffmpeg or add it to PATH. {TOOL_SOURCES['ffmpeg']}")


def tool_issue(env, name):
    record = env.get(name)
    if not isinstance(record, dict):
        reason = "not configured"
    elif record.get("status") != "ok":
        reason = record.get("status") or "invalid configuration"
    else:
        path = record.get("path")
        if not isinstance(path, str) or not Path(path).is_absolute():
            reason = "expected an absolute path in the configuration"
        elif name == "game":
            if Path(path).is_dir() and next(Path(path).glob("chunkG*.bin"), None):
                return None
            reason = f"no supported chunkG*.bin archives at {path}"
        elif Path(path).is_file():
            return None
        else:
            reason = f"file no longer exists: {path}"
    return {"tool": name, "reason": reason, "override": f"--{name}", "source": TOOL_SOURCES[name]}


def missing_tools(env, names):
    return [issue for name in names if (issue := tool_issue(env, name)) is not None]


def preflight_message(stage, issues):
    lines = [f"TOOL PREFLIGHT FAILED ({stage}):"]
    for issue in issues:
        lines.append(f"- {issue['tool']}: {issue['reason']}. "
                     f"Set {issue['override']}. {issue['source']}")
    lines.append(f"Re-run env_check.py --stage {stage} after resolving the items above.")
    return "\n".join(lines)


def require_tools(env, names, stage):
    issues = missing_tools(env, names)
    if issues:
        raise ValueError(preflight_message(stage, issues))
    return {name: Path(env[name]["path"]).resolve() for name in names}
