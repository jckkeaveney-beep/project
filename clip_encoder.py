"""Turn images and text into CLIP vectors that can be compared with each other."""
import numpy as np
import open_clip
import torch
from PIL import Image

from config import CLIP_MODEL_NAME, CLIP_WEIGHTS


class ClipEncoder:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            CLIP_MODEL_NAME, pretrained=CLIP_WEIGHTS, device=self.device
        )
        self.tokenizer = open_clip.get_tokenizer(CLIP_MODEL_NAME)
        self.model.eval()

    @torch.no_grad()
    def encode_images(self, images: list[Image.Image]) -> np.ndarray:
        pixels = torch.stack([self.preprocess(image) for image in images])
        return self._to_unit_vectors(self.model.encode_image(pixels.to(self.device)))

    @torch.no_grad()
    def encode_text(self, text: str) -> np.ndarray:
        tokens = self.tokenizer([text]).to(self.device)
        return self._to_unit_vectors(self.model.encode_text(tokens))[0]

    @staticmethod
    def _to_unit_vectors(vectors: torch.Tensor) -> np.ndarray:
        # Unit length means a plain dot product gives cosine similarity.
        vectors = vectors / vectors.norm(dim=-1, keepdim=True)
        return vectors.cpu().numpy().astype(np.float32)
