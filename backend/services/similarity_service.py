"""
Cosine similarity search service with ORB re-ranking.

Compares a query embedding against all stored original document embeddings
using cosine similarity. Returns top-K matches above the configured threshold.

Since embeddings are L2-normalized to unit length, the dot product is
equivalent to cosine similarity (optimization).

Enhanced with ORB (Oriented FAST and Rotated BRIEF) feature matching
for pixel-level verification of top candidates.
"""
import logging
import os
import base64
import mimetypes
import numpy as np
from django.conf import settings
logger = logging.getLogger(__name__)
_cv2 = None
try:
    import cv2 as _cv2
    logger.info('OpenCV available for ORB feature matching')
except ImportError:
    logger.info('OpenCV not installed — ORB re-ranking unavailable')


class SimilarityService:

    @staticmethod
    def _document_image_path(doc):
        """Return a readable local image path for an OriginalDocument."""
        doc_image_path = None
        if hasattr(doc, 'image_path'):
            doc_image_path = str(doc.image_path)
        elif isinstance(doc, dict):
            doc_image_path = doc.get('image_path') or doc.get('path')
        if doc_image_path and os.path.exists(doc_image_path):
            return doc_image_path

        image_data = getattr(doc, 'image_data', None)
        if not image_data:
            return doc_image_path if doc_image_path and os.path.exists(doc_image_path) else None

        try:
            mime_type = getattr(doc, 'image_mime_type', 'image/jpeg') or 'image/jpeg'
            ext = mimetypes.guess_extension(mime_type) or '.jpg'
            if ext == '.jpe':
                ext = '.jpg'
            cache_dir = os.path.join(str(settings.MEDIA_ROOT), 'cached_originals')
            os.makedirs(cache_dir, exist_ok=True)
            doc_id = getattr(doc, 'id', 'document')
            cached_path = os.path.join(cache_dir, f'{doc_id}{ext}')
            if not os.path.exists(cached_path):
                with open(cached_path, 'wb') as f:
                    f.write(base64.b64decode(image_data))
            return cached_path
        except Exception as e:
            logger.warning(f'Could not materialize original image from DB fallback: {e}')
            return None

    @staticmethod
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
        if abs(norm_a - 1.0) < 0.01 and abs(norm_b - 1.0) < 0.01:
            return float(np.dot(a, b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    @staticmethod
    def phash_similarity(image_path_a, image_path_b, hash_size=16):
        """
    Compute perceptual hash similarity between two images.

    Perceptual hashing captures the visual 'fingerprint' of an image.
    Unlike CNN embeddings (which recognize concepts like 'same person'),
    pHash detects whether two images share the same BASE IMAGE,
    even if one has text overlays, crops, or color adjustments.

    This is the key technique behind Google Lens's exact-match detection.

    Args:
        image_path_a: Path to the first image.
        image_path_b: Path to the second image.
        hash_size: Size of the hash grid (default: 16 for 256-bit hash).

    Returns:
        float: Similarity between 0.0 (completely different images)
               and 1.0 (identical or near-identical base image).
    """
        try:
            from PIL import Image

            def _compute_phash(img_path):
                """Compute a DCT-based perceptual hash."""
                img = Image.open(img_path).convert('L')
                img = img.resize((hash_size * 2, hash_size * 2), Image.LANCZOS)
                pixels = np.array(img, dtype=np.float64)
                dct = np.fft.fft2(pixels)
                dct_low = np.abs(dct[:hash_size, :hash_size])
                median = np.median(dct_low)
                return (dct_low > median).flatten()
            hash_a = _compute_phash(image_path_a)
            hash_b = _compute_phash(image_path_b)
            matching_bits = np.sum(hash_a == hash_b)
            similarity = matching_bits / len(hash_a)
            logger.debug(f'[pHash] {matching_bits}/{len(hash_a)} bits match (similarity: {similarity:.4f})')
            return float(similarity)
        except Exception as e:
            logger.debug(f'[pHash] Failed: {e}')
            return 0.0

    @staticmethod
    def histogram_similarity(image_path_a, image_path_b):
        """
    Compute color histogram similarity between two images.

    Compares the overall color distribution. Two versions of the same
    image (original vs text-overlay edit) will have very similar color
    histograms, while a completely different photo of the same person
    will have a different color distribution.

    Returns:
        float: Correlation coefficient between -1.0 and 1.0.
               Values above 0.7 suggest visually similar images.
    """
        if _cv2 is None:
            return 0.0
        try:
            img_a = _cv2.imread(image_path_a)
            img_b = _cv2.imread(image_path_b)
            if img_a is None or img_b is None:
                return 0.0
            hsv_a = _cv2.cvtColor(img_a, _cv2.COLOR_BGR2HSV)
            hsv_b = _cv2.cvtColor(img_b, _cv2.COLOR_BGR2HSV)
            hist_a = _cv2.calcHist([hsv_a], [0, 1], None, [50, 60], [0, 180, 0, 256])
            hist_b = _cv2.calcHist([hsv_b], [0, 1], None, [50, 60], [0, 180, 0, 256])
            _cv2.normalize(hist_a, hist_a, 0, 1, _cv2.NORM_MINMAX)
            _cv2.normalize(hist_b, hist_b, 0, 1, _cv2.NORM_MINMAX)
            score = _cv2.compareHist(hist_a, hist_b, _cv2.HISTCMP_CORREL)
            score = max(0.0, min(1.0, score))
            logger.debug(f'[Histogram] Correlation: {score:.4f}')
            return float(score)
        except Exception as e:
            logger.debug(f'[Histogram] Failed: {e}')
            return 0.0

    @staticmethod
    def orb_similarity(image_path_a, image_path_b, max_features=1000):
        """
    Compute ORB feature matching similarity between two images.

    ORB (Oriented FAST and Rotated BRIEF) detects keypoints and computes
    descriptors that are robust to rotation, scale, and minor perspective
    changes. This provides pixel-level verification that complements
    the global CNN embedding similarity.

    Args:
        image_path_a: Path to the first image.
        image_path_b: Path to the second image.
        max_features: Maximum ORB features to detect (default: 1000).

    Returns:
        float: Similarity score between 0.0 and 1.0.
               Returns 0.0 if ORB is unavailable or matching fails.
    """
        if _cv2 is None:
            return 0.0
        try:
            img_a = _cv2.imread(image_path_a, _cv2.IMREAD_GRAYSCALE)
            img_b = _cv2.imread(image_path_b, _cv2.IMREAD_GRAYSCALE)
            if img_a is None or img_b is None:
                return 0.0
            orb = _cv2.ORB_create(nfeatures=max_features)
            kp_a, desc_a = orb.detectAndCompute(img_a, None)
            kp_b, desc_b = orb.detectAndCompute(img_b, None)
            if desc_a is None or desc_b is None:
                return 0.0
            if len(desc_a) < 2 or len(desc_b) < 2:
                return 0.0
            bf = _cv2.BFMatcher(_cv2.NORM_HAMMING, crossCheck=False)
            try:
                matches = bf.knnMatch(desc_a, desc_b, k=2)
            except _cv2.error:
                return 0.0
            good_matches = []
            for match_pair in matches:
                if len(match_pair) == 2:
                    m, n = match_pair
                    if m.distance < 0.75 * n.distance:
                        good_matches.append(m)
            max_possible = min(len(desc_a), len(desc_b))
            if max_possible == 0:
                return 0.0
            score = len(good_matches) / max_possible
            score = min(max(score, 0.0), 1.0)
            logger.debug(f'[ORB] {len(good_matches)} good matches out of {max_possible} possible (score: {score:.4f})')
            return score
        except Exception as e:
            logger.warning(f'[ORB] Feature matching failed: {e}')
            return 0.0

    @staticmethod
    def re_rank_with_orb(query_image_path, candidates, embedding_weight=0.6, orb_weight=0.4):
        """
    Re-rank candidate matches using a combination of embedding similarity
    and ORB feature matching.

    The combined score provides both global (CNN embedding) and local
    (ORB keypoints) similarity assessment, which is more robust for
    detecting document manipulations like cropping, rotation, or editing.

    Args:
        query_image_path: Path to the query image.
        candidates: list[dict] — each dict must have 'document' (with image_path)
                    and 'score' (embedding cosine similarity).
        embedding_weight: Weight for embedding score (default: 0.6).
        orb_weight: Weight for ORB score (default: 0.4).

    Returns:
        list[dict]: Re-ranked candidates with updated 'score' and added
                    'embedding_score' and 'orb_score' fields.
    """
        if _cv2 is None or not candidates:
            logger.info('[Re-rank] ORB unavailable or no candidates, skipping re-ranking')
            return candidates
        re_ranked = []
        for candidate in candidates:
            doc = candidate.get('document')
            embedding_score = candidate.get('score', 0.0)
            doc_image_path = None
            if hasattr(doc, 'image_path'):
                doc_image_path = str(doc.image_path)
            elif isinstance(doc, dict):
                doc_image_path = doc.get('image_path') or doc.get('path')
            orb_score = 0.0
            if doc_image_path:
                orb_score = SimilarityService.orb_similarity(query_image_path, doc_image_path)
            combined_score = embedding_weight * embedding_score + orb_weight * orb_score
            re_ranked.append({**candidate, 'score': round(combined_score, 6), 'embedding_score': round(embedding_score, 6), 'orb_score': round(orb_score, 6)})
        re_ranked.sort(key=lambda x: x['score'], reverse=True)
        logger.info(f"[Re-rank] Re-ranked {len(re_ranked)} candidates with ORB. Best combined score: {(re_ranked[0]['score'] if re_ranked else 'N/A')}")
        return re_ranked

    @staticmethod
    def re_rank_local_candidates(query_image_path, candidates):
        """
    Re-rank local database candidates using exact-image signals.

    CNN embeddings are useful for broad semantic similarity, but edited news
    cards can be dominated by a background photo. This ranking favors local
    visual evidence so a stored Doksli document wins over a generic web
    background candidate.
    """
        if not candidates:
            return []
        W_PHASH = 0.25
        W_ORB = 0.35
        W_HIST = 0.15
        W_EMB = 0.25
        ranked = []
        for candidate in candidates:
            doc = candidate.get('document')
            doc_image_path = SimilarityService._document_image_path(doc)
            if not doc_image_path:
                continue
            embedding_score = candidate.get('score', 0.0)
            ph_score = SimilarityService.phash_similarity(query_image_path, doc_image_path)
            orb_score_val = SimilarityService.orb_similarity(query_image_path, doc_image_path)
            hist_score = SimilarityService.histogram_similarity(query_image_path, doc_image_path)
            combined_score = (
                W_PHASH * ph_score
                + W_ORB * orb_score_val
                + W_HIST * hist_score
                + W_EMB * embedding_score
            )
            ranked.append({
                **candidate,
                'score': round(combined_score, 6),
                'embedding_score': round(embedding_score, 6),
                'phash_score': round(ph_score, 6),
                'orb_score': round(orb_score_val, 6),
                'hist_score': round(hist_score, 6),
            })
        ranked.sort(key=lambda x: x['score'], reverse=True)
        if ranked:
            best = ranked[0]
            logger.info(
                f"[Re-rank Local] Ranked {len(ranked)} local candidates. "
                f"Best score: {best['score']:.4f} "
                f"(pHash={best['phash_score']:.4f}, ORB={best['orb_score']:.4f}, "
                f"hist={best['hist_score']:.4f}, emb={best['embedding_score']:.4f})"
            )
        return ranked

    @staticmethod
    def is_reliable_local_match(match):
        """
        Decide whether a local candidate is strong enough to stop online fallback.

        Embeddings alone often match the same person, topic, or template. Local
        Doksli matches must also show same-base-image evidence from pHash/ORB.
        """
        score = float(match.get('score', 0.0) or 0.0)
        phash = float(match.get('phash_score', 0.0) or 0.0)
        orb = float(match.get('orb_score', 0.0) or 0.0)
        local_threshold = getattr(settings, 'LOCAL_MATCH_THRESHOLD', 0.62)
        phash_threshold = getattr(settings, 'LOCAL_PHASH_THRESHOLD', 0.82)
        orb_threshold = getattr(settings, 'LOCAL_ORB_THRESHOLD', 0.08)
        strong_phash = getattr(settings, 'LOCAL_STRONG_PHASH_THRESHOLD', 0.90)
        strong_orb = getattr(settings, 'LOCAL_STRONG_ORB_THRESHOLD', 0.18)

        if score < local_threshold:
            return False
        if phash >= strong_phash or orb >= strong_orb:
            return True
        if phash >= phash_threshold and orb >= orb_threshold:
            return True
        return False

    @staticmethod
    def filter_reliable_local_matches(candidates, top_k=None):
        """Keep only local candidates with enough exact-image evidence."""
        if top_k is None:
            top_k = getattr(settings, 'SIMILARITY_TOP_K', 5)
        accepted = []
        rejected = []
        for match in candidates:
            if SimilarityService.is_reliable_local_match(match):
                accepted.append(match)
            else:
                rejected.append(match)
        if rejected:
            best_rejected = rejected[0]
            logger.info(
                f"Rejected {len(rejected)} weak local candidate(s). Best rejected: "
                f"score={best_rejected.get('score', 0):.4f}, "
                f"pHash={best_rejected.get('phash_score', 0):.4f}, "
                f"ORB={best_rejected.get('orb_score', 0):.4f}, "
                f"emb={best_rejected.get('embedding_score', 0):.4f}"
            )
        return accepted[:top_k]

    @staticmethod
    def re_rank_web_candidates(query_image_path, query_embedding, candidates):
        """
    Rank downloaded web candidate images using multi-metric similarity.

    Uses four complementary signals to find the EXACT original image
    (not just a semantically similar one):

    - pHash (30%): Perceptual hash detects same base image even with
      text overlays, crops, or color edits. This is the critical metric
      that differentiates "same image, edited" from "same person,
      different photo".
    - ORB (30%): Feature keypoint matching for structural verification.
    - Histogram (20%): Color distribution similarity.
    - Embedding (20%): CNN semantic similarity (same concept/person).

    The old formula (65% embedding + 35% ORB) favored "same person"
    over "same image". The new formula favors "same image" — matching
    Google Lens behavior for document forgery detection.

    Args:
        query_image_path: Path to the query image.
        query_embedding: list[float] -- the query embedding vector.
        candidates: list[dict] -- downloaded candidates from online search,
                    each has 'path', 'url', 'source'.

    Returns:
        list[dict]: Ranked candidates with score breakdowns.
    """
        if not candidates:
            return []
        use_embedding = getattr(settings, 'WEB_RERANK_WITH_EMBEDDING', False)
        if use_embedding:
            from services.embedding_service import EmbeddingService
            W_PHASH = 0.3
            W_ORB = 0.3
            W_HIST = 0.2
            W_EMB = 0.2
        else:
            EmbeddingService = None
            W_PHASH = 0.4
            W_ORB = 0.4
            W_HIST = 0.2
            W_EMB = 0.0
        ranked = []
        for candidate in candidates:
            candidate_path = candidate.get('path')
            if not candidate_path:
                continue
            try:
                ph_score = SimilarityService.phash_similarity(query_image_path, candidate_path)
                orb_score_val = SimilarityService.orb_similarity(query_image_path, candidate_path)
                hist_score = SimilarityService.histogram_similarity(query_image_path, candidate_path)
                if use_embedding:
                    candidate_embedding = EmbeddingService.extract_embedding(candidate_path)
                    emb_score = SimilarityService.cosine_similarity(query_embedding, candidate_embedding)
                else:
                    emb_score = 0.0
                combined_score = W_PHASH * ph_score + W_ORB * orb_score_val + W_HIST * hist_score + W_EMB * emb_score
                if orb_score_val < 0.05 and ph_score < 0.75:
                    combined_score *= 0.5
                ranked.append({'path': candidate_path, 'url': candidate.get('url', ''), 'source': candidate.get('source', 'web'), 'score': round(combined_score, 6), 'phash_score': round(ph_score, 6), 'orb_score': round(orb_score_val, 6), 'hist_score': round(hist_score, 6), 'embedding_score': round(emb_score, 6)})
            except Exception as e:
                logger.warning(f'[Re-rank Web] Failed to rank candidate {candidate_path}: {e}')
                continue
        ranked.sort(key=lambda x: x['score'], reverse=True)
        if ranked:
            best = ranked[0]
            logger.info(f"[Re-rank Web] Ranked {len(ranked)} web candidates. Best score: {best['score']:.4f} (pHash={best['phash_score']:.4f}, ORB={best['orb_score']:.4f}, hist={best['hist_score']:.4f}, emb={best['embedding_score']:.4f})")
        return ranked

    @staticmethod
    def find_candidate_pool(query_embedding, min_similarity=None, top_k=None):
        """
    Return a broader local candidate pool before visual re-ranking.

    This intentionally does not require SIMILARITY_THRESHOLD. It is used as a
    first-pass retrieval step so manipulated screenshots/posters still get
    compared against Supabase/local originals before online fallback.
    """
        from api.models import OriginalDocument
        if min_similarity is None:
            min_similarity = getattr(settings, 'LOCAL_CANDIDATE_MIN', 0.35)
        if top_k is None:
            top_k = max(getattr(settings, 'SIMILARITY_TOP_K', 5) * 4, 20)
        documents = OriginalDocument.objects.all()
        if not documents.exists():
            logger.info('No original documents in database for local candidate search')
            return []
        query_vec = np.array(query_embedding, dtype=np.float32)
        candidates = []
        for doc in documents:
            if not doc.embedding_vector:
                continue
            try:
                doc_vec = np.array(doc.embedding_vector, dtype=np.float32)
                score = SimilarityService.cosine_similarity(query_vec, doc_vec)
                if score >= min_similarity:
                    candidates.append({'document': doc, 'score': round(score, 6)})
            except Exception as e:
                logger.error(f'Candidate similarity computation error for doc {doc.id}: {e}')
                continue
        candidates.sort(key=lambda x: x['score'], reverse=True)
        candidates = candidates[:top_k]
        logger.info(
            f'Local candidate pool: {len(candidates)} candidates '
            f'(min={min_similarity}, top_k={top_k}, total_docs={documents.count()})'
        )
        return candidates

    @staticmethod
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
            logger.info('No original documents in database for similarity search')
            return []
        query_vec = np.array(query_embedding, dtype=np.float32)
        matches = []
        for doc in documents:
            if not doc.embedding_vector:
                continue
            try:
                doc_vec = np.array(doc.embedding_vector, dtype=np.float32)
                score = SimilarityService.cosine_similarity(query_vec, doc_vec)
                if score < min_similarity:
                    continue
                if score >= threshold:
                    matches.append({'document': doc, 'score': round(score, 6)})
            except Exception as e:
                logger.error(f'Similarity computation error for doc {doc.id}: {e}')
                continue
        matches.sort(key=lambda x: x['score'], reverse=True)
        matches = matches[:top_k]
        logger.info(f'Local search: {len(matches)} matches found (threshold={threshold}, min={min_similarity}, top_k={top_k}, total_docs={documents.count()})')
        return matches
