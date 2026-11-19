"""Find shots by description, by example picture, or by spoken words."""
import sqlite3
from collections import defaultdict

import numpy as np
from PIL import Image

from clip_encoder import ClipEncoder
from config import IMAGE_VECTORS_FILE, RESULTS_PER_SEARCH, SHOT_IDS_FILE, TEXT_INDEX_FILE
from shots import video_id_from_shot_id

# Standard value for reciprocal rank fusion (Cormack et al., 2009).
RANK_FUSION_CONSTANT = 60
# How much more a match in the spoken words counts than one in the title/tags.
SPOKEN_WEIGHT = 2.0
VIDEO_INFO_WEIGHT = 1.0


class ShotSearcher:
    def __init__(self):
        self.encoder = ClipEncoder()
        self.image_vectors = np.load(IMAGE_VECTORS_FILE)
        self.shot_ids = SHOT_IDS_FILE.read_text().splitlines()
        self.text_index = sqlite3.connect(TEXT_INDEX_FILE, check_same_thread=False)

    def by_description(self, description: str) -> list[str]:
        return self._closest_shots(self.encoder.encode_text(description))

    def by_example_image(self, image: Image.Image) -> list[str]:
        return self._closest_shots(self.encoder.encode_images([image])[0])

    def by_spoken_words(self, words: str) -> list[str]:
        if not words.strip():
            return []
        rows = self.text_index.execute(
            "SELECT shot_id FROM shot_text WHERE shot_text MATCH ? "
            "ORDER BY bm25(shot_text, 0, ?, ?) LIMIT ?",
            (as_any_word_query(words), SPOKEN_WEIGHT, VIDEO_INFO_WEIGHT, RESULTS_PER_SEARCH),
        )
        return [shot_id for (shot_id,) in rows]

    def by_description_and_words(self, query: str) -> list[str]:
        combined = combine_rankings(self.by_description(query), self.by_spoken_words(query))
        return combined[:RESULTS_PER_SEARCH]

    def _closest_shots(self, query_vector: np.ndarray) -> list[str]:
        similarities = self.image_vectors @ query_vector
        best_first = np.argsort(-similarities)[:RESULTS_PER_SEARCH]
        return [self.shot_ids[index] for index in best_first]


def as_any_word_query(words: str) -> str:
    quoted_words = [f'"{word}"' for word in words.replace('"', "").split()]
    return " OR ".join(quoted_words)


def combine_rankings(*rankings: list[str]) -> list[str]:
    scores = defaultdict(float)
    for ranking in rankings:
        for rank, shot_id in enumerate(ranking):
            scores[shot_id] += 1 / (RANK_FUSION_CONSTANT + rank)
    return sorted(scores, key=scores.get, reverse=True)


def limit_shots_per_video(shot_ids: list[str], max_per_video: int) -> list[str]:
    shots_taken = defaultdict(int)
    varied = []
    for shot_id in shot_ids:
        video_id = video_id_from_shot_id(shot_id)
        if shots_taken[video_id] < max_per_video:
            shots_taken[video_id] += 1
            varied.append(shot_id)
    return varied
