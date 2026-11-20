"""Run once: store what is said in each shot, plus its video's title and tags,
in a SQLite full-text index."""
import json
import sqlite3
from dataclasses import dataclass

from config import INDEX_FOLDER, METADATA_FILE, TEXT_INDEX_FILE, TRANSCRIPT_FOLDER
from shots import MS_PER_SECOND, Shot, load_all_shots

# Check these against videos_metadata.md before running.
VIDEO_ID_FIELD = "v3cId"
TITLE_FIELD = "title"
TAGS_FIELD = "tags"
TAG_SEPARATOR = "; "


@dataclass(frozen=True)
class SpokenSegment:
    start_ms: int
    end_ms: int
    text: str


def srt_timestamp_to_ms(timestamp: str) -> int:
    hours, minutes, seconds_and_ms = timestamp.strip().split(":")
    seconds, milliseconds = seconds_and_ms.split(",")
    total_seconds = (int(hours) * 60 + int(minutes)) * 60 + int(seconds)
    return total_seconds * MS_PER_SECOND + int(milliseconds)


def load_spoken_segments(video_id: str) -> list[SpokenSegment]:
    # Each SRT block is: a counter line, "start --> end", then one or more lines of text.
    transcript_path = TRANSCRIPT_FOLDER / f"{video_id}.srt"
    if not transcript_path.exists():
        return []
    segments = []
    for block in transcript_path.read_text(encoding="utf-8").strip().split("\n\n"):
        lines = block.splitlines()
        if len(lines) < 3:
            continue
        start, end = lines[1].split(" --> ")
        segments.append(
            SpokenSegment(srt_timestamp_to_ms(start), srt_timestamp_to_ms(end), " ".join(lines[2:]))
        )
    return segments


def words_spoken_during(shot: Shot, segments: list[SpokenSegment]) -> str:
    overlapping = [
        segment.text
        for segment in segments
        if segment.start_ms < shot.end_ms and segment.end_ms > shot.start_ms
    ]
    return " ".join(overlapping)


def load_video_descriptions() -> dict[str, str]:
    videos = json.loads(METADATA_FILE.read_text(encoding="utf-8"))
    return {
        video[VIDEO_ID_FIELD]: f"{video[TITLE_FIELD]} {video[TAGS_FIELD].replace(TAG_SEPARATOR, ' ')}"
        for video in videos
    }


def create_empty_index() -> sqlite3.Connection:
    INDEX_FOLDER.mkdir(exist_ok=True)
    TEXT_INDEX_FILE.unlink(missing_ok=True)
    database = sqlite3.connect(TEXT_INDEX_FILE)
    database.execute(
        "CREATE VIRTUAL TABLE shot_text USING fts5(shot_id UNINDEXED, spoken, video_info)"
    )
    return database


def build_text_index() -> None:
    database = create_empty_index()
    video_descriptions = load_video_descriptions()
    segments_by_video = {}
    for shot in load_all_shots().values():
        if shot.video_id not in segments_by_video:
            segments_by_video[shot.video_id] = load_spoken_segments(shot.video_id)
        database.execute(
            "INSERT INTO shot_text VALUES (?, ?, ?)",
            (
                shot.shot_id,
                words_spoken_during(shot, segments_by_video[shot.video_id]),
                video_descriptions.get(shot.video_id, ""),
            ),
        )
    database.commit()
    database.close()


if __name__ == "__main__":
    build_text_index()
