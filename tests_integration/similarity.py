"""
Integration test utilities.

Provides semantic similarity checking using sentence transformers.
"""

import numpy as np
from typing import Optional
from sentence_transformers import SentenceTransformer

from app.agent.config import settings


# Cache the model
_model: Optional[SentenceTransformer] = None


def get_model() -> SentenceTransformer:
    """Get or create the sentence transformer model."""
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.SENTENCE_TRANSFORMER_MODEL)
    return _model


def compute_similarity(text1: str, text2: str) -> float:
    """
    Compute cosine similarity between two texts.

    Args:
        text1: First text
        text2: Second text

    Returns:
        Similarity score between 0.0 and 1.0
    """
    model = get_model()
    embeddings = model.encode([text1, text2])
    # Cosine similarity
    similarity = np.dot(embeddings[0], embeddings[1]) / (
        np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])
    )
    return float(similarity)


def is_similar(text1: str, text2: str, threshold: float = None) -> bool:
    """
    Check if two texts are semantically similar.

    Args:
        text1: First text
        text2: Second text
        threshold: Similarity threshold (default from config)

    Returns:
        True if similarity >= threshold
    """
    threshold = threshold or settings.SIMILARITY_THRESHOLD
    similarity = compute_similarity(text1, text2)
    return similarity >= threshold
