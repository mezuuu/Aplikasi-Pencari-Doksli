"""
API Views for the Image Manipulation Detection System.

Endpoints:
- POST /api/search/       → Upload image, privacy analysis, similarity search
- POST /api/add-original/ → Add original document to database
- GET  /api/results/<id>/ → Get search result detail
- GET  /api/originals/    → List stored original documents
"""

import hashlib
import logging
import os
import uuid

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response

from .models import (
    OriginalDocument,
    SearchQuery,
    PrivacyAnalysis,
    SearchResult,
)
from .serializers import (
    SearchQuerySerializer,
    OriginalDocumentSerializer,
    OriginalDocumentListSerializer,
)

logger = logging.getLogger(__name__)


def _save_uploaded_file(uploaded_file, subfolder='uploads'):
    """Save an uploaded file to the media directory and return the path."""
    media_dir = os.path.join(settings.MEDIA_ROOT, subfolder)
    os.makedirs(media_dir, exist_ok=True)

    # Generate unique filename
    ext = os.path.splitext(uploaded_file.name)[1] or '.jpg'
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(media_dir, filename)

    with open(filepath, 'wb') as f:
        for chunk in uploaded_file.chunks():
            f.write(chunk)

    return filepath


def _compute_file_hash(filepath):
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def search_image(request):
    """
    POST /api/search/

    Upload an image for privacy analysis and similarity search.

    Enhanced Flow:
    1. Save uploaded image
    2. Run privacy analysis (face, name, age, address, phone)
    3. If blocked (>=3 flags) → return blocked response
    4. Apply PII masking (blur faces/sensitive areas)
    5. Generate embedding (MobileNetV2 1280-dim)
    6. Search local DB (cosine similarity)
    7. Re-rank local matches with ORB feature matching
    8. If no local match → sub-region cropping search
    9. If still no match → modular online search:
       a. Google Cloud Vision (if active)
       b. DuckDuckGo (free fallback)
       c. Download up to 20 candidate images
       d. Re-rank candidates with embedding + ORB
    10. ELA forensic analysis (optional, adds manipulation score)
    11. Return results (same API contract as before)
    """
    image_file = request.FILES.get('image')
    if not image_file:
        return Response(
            {'error': 'No image file provided. Use "image" field.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        # ─── 1. Save uploaded image ───
        filepath = _save_uploaded_file(image_file, subfolder='queries')
        file_hash = _compute_file_hash(filepath)

        # ─── 2. Create search query record ───
        search_query = SearchQuery.objects.create(
            query_image_path=filepath,
            query_hash=file_hash,
            search_source='local',
        )

        # ─── 3. Run privacy analysis ───
        from services.privacy_service import analyze_privacy
        privacy_result = analyze_privacy(filepath)

        # Save privacy analysis
        privacy = PrivacyAnalysis.objects.create(
            search=search_query,
            face_detected=privacy_result['face_detected'],
            name_detected=privacy_result['name_detected'],
            age_detected=privacy_result['age_detected'],
            address_detected=privacy_result['address_detected'],
            phone_detected=privacy_result['phone_detected'],
            total_flags=privacy_result['total_flags'],
            is_blocked=privacy_result['is_blocked'],
        )

        # ─── 4. If blocked, return early ───
        if privacy.is_blocked:
            serializer = SearchQuerySerializer(search_query)
            return Response(
                {
                    'status': 'blocked',
                    'message': (
                        f'Pencarian diblokir: terdeteksi {privacy.total_flags} '
                        f'kategori informasi pribadi. '
                        f'Minimum {settings.PRIVACY_FLAG_THRESHOLD} flag untuk pemblokiran.'
                    ),
                    'data': serializer.data,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # ─── 5. Apply PII masking (blur sensitive areas) ───
        from services.privacy_service import blur_pii_regions
        masked_path = blur_pii_regions(filepath, privacy_result)

        # Update query image path to masked version for display
        if masked_path != filepath:
            search_query.query_image_path = masked_path
            search_query.save(update_fields=['query_image_path'])
            logger.info(f"Query image replaced with masked version: {masked_path}")

        # ─── 6. Generate embedding (GPU-accelerated if available) ───
        # Always use the ORIGINAL image for embedding (not masked)
        from services.embedding_service import extract_embedding
        query_embedding = extract_embedding(filepath)

        # ─── 7. Local similarity search (cosine similarity, top-K) ───
        from services.similarity_service import (
            find_most_similar, re_rank_with_orb
        )
        local_matches = find_most_similar(query_embedding)

        # ─── 8. Re-rank local matches with ORB ───
        if local_matches:
            local_matches = re_rank_with_orb(filepath, local_matches)
            logger.info(
                f"Local matches re-ranked with ORB. "
                f"Best score: {local_matches[0]['score']}"
            )

        # Save local matches
        for match in local_matches:
            SearchResult.objects.create(
                search=search_query,
                source_type='local',
                matched_document=match['document'],
                similarity_score=match['score'],
            )

        # ─── 9. If no local matches → try sub-region search ───
        crop_paths = []
        if not local_matches:
            try:
                from services.cropping_service import generate_crop_regions, cleanup_crops
                crop_paths = generate_crop_regions(filepath)

                if crop_paths:
                    logger.info(
                        f"Full-image search found no matches. "
                        f"Trying {len(crop_paths)} sub-region crops..."
                    )

                    best_crop_matches = []

                    for crop_path in crop_paths:
                        try:
                            crop_embedding = extract_embedding(crop_path)
                            crop_matches = find_most_similar(crop_embedding)

                            for match in crop_matches:
                                best_crop_matches.append(match)
                        except Exception as e:
                            logger.warning(f"Crop embedding/search failed for {crop_path}: {e}")
                            continue

                    if best_crop_matches:
                        # Deduplicate by document id, keeping the highest score
                        seen = {}
                        for match in best_crop_matches:
                            doc_id = str(match['document'].id)
                            if doc_id not in seen or match['score'] > seen[doc_id]['score']:
                                seen[doc_id] = match
                        best_crop_matches = sorted(
                            seen.values(), key=lambda x: x['score'], reverse=True
                        )

                        # Re-rank crop matches with ORB
                        best_crop_matches = re_rank_with_orb(filepath, best_crop_matches)

                        # Save sub-region matches (limit to top-K)
                        top_k = getattr(settings, 'SIMILARITY_TOP_K', 5)
                        for match in best_crop_matches[:top_k]:
                            SearchResult.objects.create(
                                search=search_query,
                                source_type='local',
                                matched_document=match['document'],
                                similarity_score=match['score'],
                            )
                        local_matches = best_crop_matches[:top_k]
                        logger.info(
                            f"Sub-region search found {len(local_matches)} match(es). "
                            f"Best score: {local_matches[0]['score']}"
                        )

            except Exception as e:
                logger.error(f"Sub-region search error: {e}", exc_info=True)
            finally:
                # Always clean up temporary crop files
                if crop_paths:
                    try:
                        from services.cropping_service import cleanup_crops
                        cleanup_crops(crop_paths)
                    except Exception:
                        pass

        # ─── 10. If still no matches, modular online search ───
        web_candidates = []
        if not local_matches:
            try:
                from services.online_search_service import search_online
                from services.similarity_service import re_rank_web_candidates

                logger.info("No local matches found. Starting modular online search...")
                online_result = search_online(filepath, max_candidates=10)

                web_candidates = online_result.get('candidates', [])
                search_source = online_result.get('search_source', 'none')

                if web_candidates:
                    # Re-rank downloaded candidates with embedding + ORB
                    ranked_web = re_rank_web_candidates(
                        filepath, query_embedding, web_candidates
                    )

                    # Determine the proper source_type for DB
                    source_map = {'google': 'google', 'yandex': 'google', 'bing': 'bing'}
                    db_source_type = source_map.get(search_source, 'google')

                    # Save web results (using only the external URL)
                    for ranked in ranked_web:
                        SearchResult.objects.create(
                            search=search_query,
                            source_type=db_source_type,
                            matched_image_path='', # Do not save locally
                            external_url=ranked.get('url', ''),
                            similarity_score=ranked['score']
                        )
                    
                    # Cleanup all temporary downloads immediately
                    from services.online_search_service import cleanup_candidates
                    cleanup_candidates(web_candidates)

                    # Update search source
                    if search_source != 'none':
                        search_query.search_source = search_source
                    else:
                        search_query.search_source = 'google'
                    search_query.save(update_fields=['search_source'])

                    logger.info(
                        f"Online search completed: {len(ranked_web)} candidates ranked "
                        f"(source: {search_source})"
                    )

                elif online_result.get('google_web_results'):
                    # Fallback: Google Vision returned URLs but download failed
                    web_results = online_result['google_web_results']
                    all_web_urls = []
                    for img in web_results.get('full_matching_images', []):
                        all_web_urls.append((img['url'], img.get('score', 0.9)))
                    for img in web_results.get('partial_matching_images', []):
                        all_web_urls.append((img['url'], img.get('score', 0.7)))
                    for img in web_results.get('visually_similar_images', []):
                        all_web_urls.append((img['url'], img.get('score', 0.5)))

                    for url, score in all_web_urls[:20]:
                        SearchResult.objects.create(
                            search=search_query,
                            source_type='google',
                            external_url=url,
                            similarity_score=score,
                        )

                    search_query.search_source = 'google'
                    search_query.save(update_fields=['search_source'])

            except Exception as e:
                logger.error(f"Online search failed: {e}", exc_info=True)
            finally:
                # Clean up any remaining temp files that were NOT moved
                for candidate in web_candidates:
                    src = candidate.get('path', '')
                    if src and os.path.exists(src):
                        try:
                            os.remove(src)
                        except Exception:
                            pass
        else:
            search_query.search_source = 'local'
            search_query.save(update_fields=['search_source'])

        # ─── 11. ELA forensic analysis (optional enhancement) ───
        try:
            from services.forensic_service import perform_ela, cleanup_ela_files
            ela_result = perform_ela(filepath)

            if ela_result.get('ela_image_path'):
                # Clean up ELA temp file (we only need the score)
                cleanup_ela_files(ela_result['ela_image_path'])

            logger.info(
                f"ELA analysis: score={ela_result['ela_score']:.2f}, "
                f"suspicious={ela_result['is_suspicious']}"
            )
        except Exception as e:
            logger.warning(f"ELA analysis skipped: {e}")

        # ─── Return results ───
        search_query.refresh_from_db()
        serializer = SearchQuerySerializer(search_query)
        return Response(
            {
                'status': 'success',
                'message': 'Analisis selesai',
                'data': serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        return Response(
            {'error': f'Terjadi kesalahan saat memproses gambar: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )



@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def add_original(request):
    """
    POST /api/add-original/

    Upload an original document to the local database.
    Generates embedding and stores image with hash for deduplication.
    """
    image_file = request.FILES.get('image')
    if not image_file:
        return Response(
            {'error': 'No image file provided. Use "image" field.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        # Save file
        filepath = _save_uploaded_file(image_file, subfolder='originals')
        file_hash = _compute_file_hash(filepath)

        # Check for duplicate
        existing = OriginalDocument.objects.filter(file_hash=file_hash).first()
        if existing:
            serializer = OriginalDocumentSerializer(existing)
            return Response(
                {
                    'status': 'duplicate',
                    'message': 'Dokumen dengan hash yang sama sudah ada di database.',
                    'data': serializer.data,
                },
                status=status.HTTP_409_CONFLICT,
            )

        # Generate embedding (GPU-accelerated if available)
        from services.embedding_service import extract_embedding
        embedding = extract_embedding(filepath)

        # Create record
        document = OriginalDocument.objects.create(
            image_path=filepath,
            embedding_vector=embedding,
            file_hash=file_hash,
        )

        serializer = OriginalDocumentSerializer(document)
        return Response(
            {
                'status': 'success',
                'message': 'Dokumen asli berhasil ditambahkan.',
                'data': serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        logger.error(f"Add original error: {e}", exc_info=True)
        return Response(
            {'error': f'Terjadi kesalahan: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(['GET'])
def get_result_detail(request, search_id):
    """
    GET /api/results/<search_id>/

    Get detailed search results including privacy analysis.
    """
    try:
        search_query = SearchQuery.objects.get(pk=search_id)
    except SearchQuery.DoesNotExist:
        return Response(
            {'error': 'Hasil pencarian tidak ditemukan.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = SearchQuerySerializer(search_query)
    return Response(
        {
            'status': 'success',
            'data': serializer.data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
def list_originals(request):
    """
    GET /api/originals/

    List all stored original documents (paginated).
    """
    from rest_framework.pagination import PageNumberPagination

    paginator = PageNumberPagination()
    paginator.page_size = 20

    documents = OriginalDocument.objects.defer('embedding_vector')
    page = paginator.paginate_queryset(documents, request)

    if page is not None:
        serializer = OriginalDocumentListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    serializer = OriginalDocumentListSerializer(documents, many=True)
    return Response(
        {
            'status': 'success',
            'data': serializer.data,
        },
        status=status.HTTP_200_OK,
    )


# --- Admin Endpoints ---

ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'penimpa'


@api_view(['POST'])
def admin_login(request):
    """
    POST /api/admin/login/

    Simple admin authentication with hardcoded credentials.
    Returns a token-like response for frontend session management.
    """
    username = request.data.get('username', '')
    password = request.data.get('password', '')

    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        return Response(
            {
                'status': 'success',
                'message': 'Login berhasil.',
                'admin': True,
            },
            status=status.HTTP_200_OK,
        )

    return Response(
        {'error': 'Username atau password salah.'},
        status=status.HTTP_401_UNAUTHORIZED,
    )


@api_view(['DELETE'])
def delete_original(request, document_id):
    """
    DELETE /api/admin/originals/<document_id>/

    Delete an original document from the database.
    Requires admin auth header.
    """
    # Simple auth check via header
    auth = request.headers.get('X-Admin-Auth', '')
    if auth != f'{ADMIN_USERNAME}:{ADMIN_PASSWORD}':
        return Response(
            {'error': 'Akses ditolak. Login sebagai admin terlebih dahulu.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        document = OriginalDocument.objects.get(pk=document_id)
    except OriginalDocument.DoesNotExist:
        return Response(
            {'error': 'Dokumen tidak ditemukan.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Delete the physical file
    if document.image_path:
        try:
            file_path = str(document.image_path)
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.warning(f"Could not delete file: {e}")

    doc_id = str(document.id)
    document.delete()

    return Response(
        {
            'status': 'success',
            'message': f'Dokumen {doc_id[:8]}... berhasil dihapus.',
        },
        status=status.HTTP_200_OK,
    )
