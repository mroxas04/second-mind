"""Small, replaceable local embedding implementations."""

from collections.abc import Sequence
from hashlib import blake2b
from math import sqrt
from typing import Protocol
import re


_TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)


class Embedder(Protocol):
    """Interface implemented by local text embedding backends."""

    @property
    def identifier(self) -> str:
        """Return a stable name for the backend and its configuration."""

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one fixed-length vector for each input text."""


class HashingEmbedder:
    """Create local lexical embeddings with signed feature hashing.

    Feature hashing needs no fitted vocabulary or downloaded model. The output
    vectors are L2-normalized, so their dot product is cosine similarity.
    """

    def __init__(self, dimensions: int = 512) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be greater than zero")
        self._dimensions = dimensions

    @property
    def identifier(self) -> str:
        """Return the versioned embedding configuration name."""

        return f"feature-hashing-v1:{self._dimensions}"

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed text locally into deterministic normalized vectors."""

        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self._dimensions
        for token in _TOKEN_PATTERN.findall(text.casefold()):
            digest = blake2b(token.encode("utf-8"), digest_size=16).digest()
            feature = int.from_bytes(digest[:8], "big") % self._dimensions
            sign = 1.0 if digest[8] & 1 else -1.0
            vector[feature] += sign

        magnitude = sqrt(sum(value * value for value in vector))
        if magnitude:
            return [value / magnitude for value in vector]
        return vector
