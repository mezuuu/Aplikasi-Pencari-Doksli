"""
Cosine similarity search service.

Compares a query embedding against all stored original document embeddings
using cosine similarity. Returns top-K matches above the configured threshold.

Since embeddings are L2-normalized to unit length, the dot product is
equivalent to cosine similarity (optimization).
"""

import logging
import numpy as np
from django.conf import settings

logger = logging.getLogger(__name__)


def cosine_similarity(vec_a, vec_b):
    """
    Compute cosine similarity between two vectors.

    Formula: dot(A, B) / (||A|| * ||B||)
    If vectors are L2-normalized, dot product alone is sufficient.

    Returns a float between -1 and 1 (1 = identical, 0 = orthogonal).
    """
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)

    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    # If both are unit vectors (L2-normalized), dot product = cosine similarity
    if abs(norm_a - 1.0) < 0.01 and abs(norm_b - 1.0) < 0.01:
        return float(np.dot(a, b))

    # Fallback to full cosine formula
    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(np.dot(a, b) / (norm_a * norm_b))


def find_most_similar(query_embedding, threshold=None, top_k=None, min_similarity=None):
    """
    Search local database for similar documents using cosine similarity.

    Args:
        query_embedding: list[float] — the query image embedding vector (1280-dim).
        threshold: float — minimum similarity score to include (default: SIMILARITY_THRESHOLD).
        top_k: int — maximum number of results to return (default: SIMILARITY_TOP_K).
        min_similarity: float — absolute floor, ignore anything below this (default: SIMILARITY_MIN).

    Returns:
        list[dict]: Sorted list of top-K matches with 'document' and 'score' keys,
                    sorted by score descending.
    """
    from api.models import OriginalDocument

    if threshold is None:
        threshold = getattr(settings, 'SIMILARITY_THRESHOLD', 0.85)
    if top_k is None:
        top_k = getattr(settings, 'SIMILARITY_TOP_K', 5)
    if min_similarity is None:
        min_similarity = getattr(settings, 'SIMILARITY_MIN', 0.6)

    documents = OriginalDocument.objects.all()

    if not documents.exists():
        logger.info("No original documents in database for similarity search")
        return []

    query_vec = np.array(query_embedding, dtype=np.float32)
    matches = []

    for doc in documents:
        if not doc.embedding_vector:
            continue

        try:
            doc_vec = np.array(doc.embedding_vector, dtype=np.float32)
            score = cosine_similarity(query_vec, doc_vec)

            # Skip if below absolute minimum
            if score < min_similarity:
                continue

            if score >= threshold:
                matches.append({
                    'document': doc,
                    'score': round(score, 6),
                })
        except Exception as e:
            logger.error(f"Similarity computation error for doc {doc.id}: {e}")
            continue

    # Sort by score descending
    matches.sort(key=lambda x: x['score'], reverse=True)

    # Limit to top-K results
    matches = matches[:top_k]

    logger.info(
        f"Local search: {len(matches)} matches found "
        f"(threshold={threshold}, min={min_similarity}, "
        f"top_k={top_k}, total_docs={documents.count()})"
    )

    return matches


# Backward-compatible alias
search_local = find_most_similar
