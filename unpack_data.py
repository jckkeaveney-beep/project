"""Run once: unpack the course downloads into assignment2_data/.

Usage (from the project folder):
    python unpack_data.py ../videos_480p.tar ../thumbnails.tar ../msb.zip ../videos_metadata.json

The .tar files from the Onedata web share have a broken first header: the
top-level folder entry claims to be as big as the whole archive (and, for
videos_480p.tar, has a bad checksum). Windows Explorer and tar.exe trust it and
show a single empty file. Python's tarfile reads the rest fine once we step over
that one 512-byte header. Files that are already unpacked are skipped, so it is
safe to run again after an interruption.
"""
import shutil
import sys
import tarfile
import zipfile
from pathlib import Path

from config import DATA_FOLDER

TAR_HEADER_BYTES = 512


def open_tar(raw_file) -> tarfile.TarFile:
    try:
        return tarfile.open(fileobj=raw_file, mode="r:")
    except tarfile.ReadError:
        raw_file.seek(TAR_HEADER_BYTES)
        return tarfile.open(fileobj=raw_file, mode="r:")


def unpack_tar(tar_path: Path) -> None:
    with tar_path.open("rb") as raw_file, open_tar(raw_file) as archive:
        for member in archive:
            if not member.isfile():
                continue
            target = DATA_FOLDER / member.name
            if target.exists() and target.stat().st_size == member.size:
                continue
            archive.extract(member, DATA_FOLDER, filter="data")
            print(f"  {member.name} ({member.size / 1e6:.0f} MB)", flush=True)


def unpack_zip(zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(DATA_FOLDER)


def unpack(path: Path) -> None:
    print(f"Unpacking {path} into {DATA_FOLDER}/", flush=True)
    if path.suffix == ".tar":
        unpack_tar(path)
    elif path.suffix == ".zip":
        unpack_zip(path)
    else:
        shutil.copy2(path, DATA_FOLDER / path.name)


if __name__ == "__main__":
    DATA_FOLDER.mkdir(exist_ok=True)
    for argument in sys.argv[1:]:
        unpack(Path(argument))
    print("Done.")
