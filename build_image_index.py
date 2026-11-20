"""Run once: turn every shot thumbnail into a CLIP vector and save them to disk.

Vectors are saved per video as the build goes, so if it is interrupted, running
it again picks up where it stopped. Choose the model with the CLIP_MODEL and
CLIP_WEIGHTS environment variables (see config.py); the default is ViT-B-32.
"""
import io
import time
import zipfile
from pathlib import Path
from typing import Iterator

import numpy as np
import torch
from PIL import Image

from clip_encoder import ClipEncoder
from config import (
    CLIP_MODEL_NAME,
    CLIP_WEIGHTS,
    IMAGE_INDEX_MODEL_FILE,
    IMAGE_INDEX_PARTS_FOLDER,
    IMAGE_VECTORS_FILE,
    INDEX_FOLDER,
    SHOT_IDS_FILE,
    THUMBNAIL_FOLDER,
)
from shots import shot_id_in_file_name

BATCH_SIZE = 256 if torch.cuda.is_available() else 64


def read_thumbnails(zip_path: Path) -> Iterator[tuple[str, Image.Image]]:
    with zipfile.ZipFile(zip_path) as archive:
        for file_name in sorted(archive.namelist()):
            shot_id = shot_id_in_file_name(file_name)
            if shot_id:
                image = Image.open(io.BytesIO(archive.read(file_name))).convert("RGB")
                yield shot_id, image


def in_batches(items: Iterator, batch_size: int) -> Iterator[list]:
    batch = []
    for item in items:
        batch.append(item)
        if len(batch) == batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def all_thumbnails() -> Iterator[tuple[str, Image.Image]]:
    for zip_path in sorted(THUMBNAIL_FOLDER.glob("*.zip")):
        yield from read_thumbnails(zip_path)


def parts_folder() -> Path:
    # One folder per model, so parts from different models never get mixed.
    return IMAGE_INDEX_PARTS_FOLDER / f"{CLIP_MODEL_NAME}__{CLIP_WEIGHTS}"


def encode_video(encoder: ClipEncoder, zip_path: Path) -> tuple[list[str], np.ndarray]:
    shot_ids, vector_batches = [], []
    for batch in in_batches(read_thumbnails(zip_path), BATCH_SIZE):
        batch_shot_ids, batch_images = zip(*batch)
        shot_ids.extend(batch_shot_ids)
        vector_batches.append(encoder.encode_images(list(batch_images)))
    return shot_ids, np.concatenate(vector_batches)


def save_part(video_id: str, shot_ids: list[str], vectors: np.ndarray) -> None:
    np.save(parts_folder() / f"{video_id}.npy", vectors)
    # Written last: a part only counts as done once its shot list exists.
    (parts_folder() / f"{video_id}.txt").write_text("\n".join(shot_ids))


def combine_parts(zip_paths: list[Path]) -> None:
    shot_ids, vectors = [], []
    for zip_path in zip_paths:
        shot_ids.extend((parts_folder() / f"{zip_path.stem}.txt").read_text().splitlines())
        vectors.append(np.load(parts_folder() / f"{zip_path.stem}.npy"))
    np.save(IMAGE_VECTORS_FILE, np.concatenate(vectors))
    SHOT_IDS_FILE.write_text("\n".join(shot_ids))
    IMAGE_INDEX_MODEL_FILE.write_text(f"{CLIP_MODEL_NAME}\n{CLIP_WEIGHTS}\n")
    print(f"Saved {len(shot_ids)} shot vectors made with {CLIP_MODEL_NAME} / {CLIP_WEIGHTS}")


def build_image_index() -> None:
    parts_folder().mkdir(parents=True, exist_ok=True)
    zip_paths = sorted(THUMBNAIL_FOLDER.glob("*.zip"))
    to_do = [path for path in zip_paths if not (parts_folder() / f"{path.stem}.txt").exists()]
    print(f"{len(zip_paths) - len(to_do)} of {len(zip_paths)} videos already done")
    if to_do:
        encoder = ClipEncoder(CLIP_MODEL_NAME, CLIP_WEIGHTS)
        print(f"Encoding with {CLIP_MODEL_NAME} / {CLIP_WEIGHTS} on {encoder.device}")
        start = time.perf_counter()
        for done, zip_path in enumerate(to_do, start=1):
            save_part(zip_path.stem, *encode_video(encoder, zip_path))
            minutes_left = (time.perf_counter() - start) / done * (len(to_do) - done) / 60
            print(f"{done}/{len(to_do)} videos, about {minutes_left:.0f} min left", end="\r")
        print()
    INDEX_FOLDER.mkdir(exist_ok=True)
    combine_parts(zip_paths)


if __name__ == "__main__":
    build_image_index()
