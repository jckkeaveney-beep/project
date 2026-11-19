"""Every path and setting the project uses, kept in one place."""
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
TEXT_INDEX_FILE = INDEX_FOLDER / "text_index.sqlite"

CLIP_MODEL_NAME = "ViT-B-32"
CLIP_WEIGHTS = "laion2b_s34b_b79k"

RESULTS_PER_SEARCH = 200
MAX_SHOTS_PER_VIDEO_FOR_AVS = 3
