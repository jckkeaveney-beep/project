"""Load the official shot list from the msb/ TSV files.

The TSV times are in seconds. DRES wants milliseconds, so we convert once,
here, and every other file works in milliseconds only.
"""
import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from config import MSB_FOLDER

# Open one TSV and check these match its header row before running anything.
START_SECONDS_COLUMN = "starttime"
END_SECONDS_COLUMN = "endtime"
MS_PER_SECOND = 1000
SHOT_ID_PATTERN = re.compile(r"shot\d+_\d+")


@dataclass(frozen=True)
class Shot:
    video_id: str
    shot_number: int
    start_ms: int
    end_ms: int

    @property
    def shot_id(self) -> str:
        return f"shot{self.video_id}_{self.shot_number}"


def seconds_to_ms(seconds_text: str) -> int:
    return round(float(seconds_text) * MS_PER_SECOND)


def video_id_from_shot_id(shot_id: str) -> str:
    return shot_id.removeprefix("shot").split("_")[0]


def shot_id_in_file_name(file_name: str) -> Optional[str]:
    match = SHOT_ID_PATTERN.search(file_name)
    return match.group() if match else None


def load_shots_for_video(tsv_path: Path) -> list[Shot]:
    video_id = tsv_path.stem
    with tsv_path.open(newline="") as tsv_file:
        rows = csv.DictReader(tsv_file, delimiter="\t")
        return [
            Shot(
                video_id=video_id,
                shot_number=shot_number,
                start_ms=seconds_to_ms(row[START_SECONDS_COLUMN]),
                end_ms=seconds_to_ms(row[END_SECONDS_COLUMN]),
            )
            for shot_number, row in enumerate(rows, start=1)
        ]


def load_all_shots(msb_folder: Path = MSB_FOLDER) -> dict[str, Shot]:
    shots_by_id = {}
    for tsv_path in sorted(msb_folder.rglob("*.tsv")):
        for shot in load_shots_for_video(tsv_path):
            shots_by_id[shot.shot_id] = shot
    return shots_by_id
