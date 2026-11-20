"""Time CLIP thumbnail encoding on this machine, to estimate how long the full index takes."""
import time
from itertools import islice

import torch

from build_image_index import BATCH_SIZE, all_thumbnails, in_batches
from clip_encoder import ClipEncoder
from config import CLIP_MODEL_NAME, CLIP_WEIGHTS
from shots import load_all_shots

BATCHES_TO_TIME = 5

encoder = ClipEncoder(CLIP_MODEL_NAME, CLIP_WEIGHTS)
print(f"model: {CLIP_MODEL_NAME} / {CLIP_WEIGHTS}")
print(f"device: {encoder.device}, torch threads: {torch.get_num_threads()}")
batches = in_batches(all_thumbnails(), BATCH_SIZE)
next(batches)  # warm-up
start = time.perf_counter()
encoded = sum(len(encoder.encode_images([image for _, image in batch])) for batch in islice(batches, BATCHES_TO_TIME))
per_second = encoded / (time.perf_counter() - start)
total = len(load_all_shots())
print(f"{per_second:.0f} thumbnails/s -> about {total / per_second / 60:.0f} min for all {total} shots")
