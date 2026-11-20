"""Every path and setting the project uses, kept in one place."""
import os
from pathlib import Path

DATA_FOLDER = Path("assignment2_data")
MSB_FOLDER = DATA_FOLDER / "msb"
THUMBNAIL_FOLDER = DATA_FOLDER / "thumbnails"
VIDEO_FOLDER = DATA_FOLDER / "videos_480p"
METADATA_FILE = DATA_FOLDER / "videos_metadata.json"
TRANSCRIPT_FOLDER = Path("transcripts")

INDEX_FOLDER = Path("index")
IMAGE_VECTORS_FILE = INDEX_FOLDER / "image_vectors.npy"
SHOT_IDS_FILE = INDEX_FOLDER / "shot_ids.txt"
# Which CLIP model built image_vectors.npy. The app reads it back so queries are
# always encoded with the same model as the index.
IMAGE_INDEX_MODEL_FILE = INDEX_FOLDER / "image_index_model.txt"
# Per-video vectors saved while building, so an interrupted build can resume.
IMAGE_INDEX_PARTS_FOLDER = INDEX_FOLDER / "image_parts"
TEXT_INDEX_FILE = INDEX_FOLDER / "text_index.sqlite"

# The model used when BUILDING the image index. Override without editing code, e.g.
#   set CLIP_MODEL=ViT-L-14
#   set CLIP_WEIGHTS=laion2b_s32b_b82k
# (open_clip.list_pretrained() lists every valid model/weights pair.)
CLIP_MODEL_NAME = os.environ.get("CLIP_MODEL", "ViT-B-32")
CLIP_WEIGHTS = os.environ.get("CLIP_WEIGHTS", "laion2b_s34b_b79k")

RESULTS_PER_SEARCH = 200
MAX_SHOTS_PER_VIDEO_FOR_AVS = 3
