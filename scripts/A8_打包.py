"""Package explicitly selected NPCKs and an optional, explicitly matched preview."""
import argparse
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from delivery import write_zip
from envutil import ffmpeg_path, load
from npck import read_package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workdir", type=Path)
    parser.add_argument("--npck", type=Path, nargs="+", required=True)
    parser.add_argument("--preview-wav", type=Path, help="optional stereo WAV matching these NPCKs")
    parser.add_argument("--output", type=Path, default=Path("delivery"), help="new directory, relative to workdir")
    parser.add_argument("--ffmpeg")
    parser.add_argument("--env", type=Path)
    args = parser.parse_args()
    try:
        ffmpeg = ffmpeg_path(load(args.env), args.ffmpeg) if args.preview_wav else None
        work = args.workdir.resolve(strict=True)
        output = (work / args.output).resolve()
        if output.exists():
            raise ValueError("output directory exists; select a new path")
        packages = [work / path for path in args.npck]
        if len({path.name.casefold() for path in packages}) != len(packages):
            raise ValueError("NPCK filenames must be unique within one mod ZIP")
        for path in packages:
            read_package(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=output.parent) as temp:
            archive = Path(temp) / "mhwi_bgm_mod.zip"
            write_zip(archive, packages)
            files = [archive]
            if args.preview_wav:
                preview = Path(temp) / "preview_stereo.mp3"
                subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-xerror",
                                "-i", str(work / args.preview_wav), "-ac", "2", "-c:a",
                                "libmp3lame", "-b:a", "192k", str(preview)], check=True)
                files.append(preview)
            output.mkdir()
            for path in files:
                path.rename(output / path.name)
        print(output)
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
