"""Write the nativePC ZIP used by the MHWI mod manager."""
import re
from zipfile import ZIP_DEFLATED, ZipFile


def safe_target(name):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.npck", name, flags=re.IGNORECASE):
        raise ValueError("target must be the exact NPCK filename in the game, without a path")
    return name


def write_zip(archive, packages):
    with ZipFile(archive, "x", compression=ZIP_DEFLATED, compresslevel=6) as output:
        for package in packages:
            name = safe_target(package.name)
            output.write(package, f"nativePC/sound/wwise/Windows/{name}")
