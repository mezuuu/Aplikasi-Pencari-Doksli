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

    Flow:
    1. Save uploaded image
    2. Run privacy analysis
    3. If blocked (>=3 flags) → return blocked response
    4. Generate embedding
    5. Search local DB
    6. If no local match → fallback to Google Vision Web Detection
    7. Return results
    """
    image_file = request.FILES.get('image')
    if not image_file:
        return Response(
            {'error': 'No image file provided. Use "image" field.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        # 1. Save uploaded image
        filepath = _save_uploaded_file(image_file, subfolder='queries')
        file_hash = _compute_file_hash(filepath)

        # 2. Create search query record
        search_query = SearchQuery.objects.create(
            query_image_path=filepath,
            query_hash=file_hash,
            search_source='local',
        )

        # 3. Run privacy analysis
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

        # 4. If blocked, return early
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

        # 5. Generate embedding (GPU-accelerated if available)
        from services.embedding_service import extract_embedding
        query_embedding = extract_embedding(filepath)

        # 6. Local similarity search (cosine similarity, top-K)
        from services.similarity_service import find_most_similar
        local_matches = find_most_similar(query_embedding)

        # Save local matches
        for match in local_matches:
            SearchResult.objects.create(
                search=search_query,
                source_type='local',
                matched_document=match['document'],
                similarity_score=match['score'],
            )

        # 7. If no local matches, fallback to Google Vision
        if not local_matches:
            try:
                from services.vision_service import detect_web_matches
                web_results = detect_web_matches(filepath)

                search_query.search_source = 'google'
                search_query.save()

                # Save web results
                all_web_urls = []
                for img in web_results.get('full_matching_images', []):
                    all_web_urls.append((img['url'], img.get('score', 0.9)))
                for img in web_results.get('partial_matching_images', []):
                    all_web_urls.append((img['url'], img.get('score', 0.7)))
                for img in web_results.get('visually_similar_images', []):
                    all_web_urls.append((img['url'], img.get('score', 0.5)))

                for url, score in all_web_urls[:20]:  # Limit to 20 results
                    SearchResult.objects.create(
                        search=search_query,
                        source_type='google',
                        external_url=url,
                        similarity_score=score,
                    )

            except Exception as e:
                logger.error(f"Google Vision fallback failed: {e}")
                search_query.search_source = 'local'
                search_query.save()
        else:
            search_query.search_source = 'local'
            search_query.save()

        # Return results
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

    documents = OriginalDocument.objects.all()
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
