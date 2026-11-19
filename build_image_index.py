"""Run once: turn every shot thumbnail into a CLIP vector and save them to disk."""
import io
import zipfile
from pathlib import Path
from typing import Iterator

import numpy as np
from PIL import Image

from clip_encoder import ClipEncoder
from config import IMAGE_VECTORS_FILE, INDEX_FOLDER, SHOT_IDS_FILE, THUMBNAIL_FOLDER
from shots import shot_id_in_file_name

BATCH_SIZE = 64


def read_thumbnails(zip_path: Path) -> Iterator[tuple[str, Image.Image]]:
    with zipfile.ZipFile(zip_path) as archive:
        for file_name in sorted(archive.namelist()):
            shot_id = shot_id_in_file_name(file_name)
            if shot_id:
                image = Image.open(io.BytesIO(archive.read(file_name))).convert("RGB")
                yield shot_id, image


def all_thumbnails() -> Iterator[tuple[str, Image.Image]]:
    for zip_path in sorted(THUMBNAIL_FOLDER.glob("*.zip")):
        yield from read_thumbnails(zip_path)


def in_batches(items: Iterator, batch_size: int) -> Iterator[list]:
    batch = []
    for item in items:
        batch.append(item)
        if len(batch) == batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def save_index(shot_ids: list[str], vectors: np.ndarray) -> None:
    INDEX_FOLDER.mkdir(exist_ok=True)
    np.save(IMAGE_VECTORS_FILE, vectors)
    SHOT_IDS_FILE.write_text("\n".join(shot_ids))


def build_image_index() -> None:
    encoder = ClipEncoder()
    shot_ids, vector_batches = [], []
    for batch in in_batches(all_thumbnails(), BATCH_SIZE):
        batch_shot_ids, batch_images = zip(*batch)
        shot_ids.extend(batch_shot_ids)
        vector_batches.append(encoder.encode_images(list(batch_images)))
        print(f"Encoded {len(shot_ids)} shots", end="\r")
    save_index(shot_ids, np.concatenate(vector_batches))


if __name__ == "__main__":
    build_image_index()
