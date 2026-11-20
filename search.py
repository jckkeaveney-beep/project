"""Find shots by description, by example picture, by a similar shot, or by spoken words."""
import sqlite3
from collections import defaultdict

import numpy as np
from PIL import Image

from config import (
    IMAGE_INDEX_MODEL_FILE,
    IMAGE_VECTORS_FILE,
    RESULTS_PER_SEARCH,
    SHOT_IDS_FILE,
    TEXT_INDEX_FILE,
)
from shots import video_id_from_shot_id

# Standard value for reciprocal rank fusion (Cormack et al., 2009).
RANK_FUSION_CONSTANT = 60
# How much more a match in the spoken words counts than one in the title/tags.
SPOKEN_WEIGHT = 2.0
VIDEO_INFO_WEIGHT = 1.0


class ShotSearcher:
    def __init__(self):
        self.text_index = sqlite3.connect(TEXT_INDEX_FILE, check_same_thread=False)
        # Picture search needs CLIP and the image index. Without them the app
        # still starts, so speech search, playback and DRES can be tested on any
        # machine; picture search then explains why it is unavailable.
        self.picture_search_problem = None
        try:
            from clip_encoder import ClipEncoder

            self.image_vectors = np.load(IMAGE_VECTORS_FILE)
            self.shot_ids = SHOT_IDS_FILE.read_text().splitlines()
            self.row_of_shot = {shot_id: row for row, shot_id in enumerate(self.shot_ids)}
            # Encode queries with the exact model that built the index.
            model_name, weights = IMAGE_INDEX_MODEL_FILE.read_text().split()
            self.encoder = ClipEncoder(model_name, weights)
            print(f"Picture search ready: {len(self.shot_ids)} shots, {model_name} / {weights}")
        except (ImportError, OSError) as error:
            self.picture_search_problem = f"Picture search is off on this machine: {error}"
            print(self.picture_search_problem)

    def by_description(self, description: str) -> list[str]:
        self._require_picture_search()
        return self._closest_shots(self.encoder.encode_text(description))

    def by_example_image(self, image: Image.Image) -> list[str]:
        self._require_picture_search()
        return self._closest_shots(self.encoder.encode_images([image])[0])

    def by_similar_shot(self, shot_id: str) -> list[str]:
        # "More like this": reuse the stored vector, no CLIP call needed.
        self._require_picture_search()
        return self._closest_shots(self.image_vectors[self.row_of_shot[shot_id]])

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

    def _require_picture_search(self) -> None:
        if self.picture_search_problem:
            raise RuntimeError(self.picture_search_problem)

    def _closest_shots(self, query_vector: np.ndarray) -> list[str]:
        similarities = self.image_vectors @ query_vector
        # argpartition finds the top results without sorting all 141k scores.
        top = np.argpartition(-similarities, RESULTS_PER_SEARCH)[:RESULTS_PER_SEARCH]
        best_first = top[np.argsort(-similarities[top])]
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
