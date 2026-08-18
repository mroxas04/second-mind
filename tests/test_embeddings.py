"""Tests for the dependency-free local embedding backend."""

from second_mind import HashingEmbedder


def test_hashing_embeddings_are_deterministic_and_local() -> None:
    embedder = HashingEmbedder(dimensions=32)

    first = embedder.embed(["Library books", "Garden seeds"])
    second = embedder.embed(["Library books", "Garden seeds"])

    assert first == second
    assert len(first) == 2
    assert all(len(vector) == 32 for vector in first)
    assert first[0] != first[1]
