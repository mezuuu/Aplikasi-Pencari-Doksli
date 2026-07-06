"""
API Views for the Image Manipulation Detection System.

Endpoints:
- POST /api/search/       → Upload image, privacy analysis, similarity search
- POST /api/add-original/ → Add original document to database
- GET  /api/results/<id>/ → Get search result detail
- GET  /api/originals/    → List stored original documents
"""
import hashlib
import base64
import logging
import mimetypes
import os
import uuid
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import OriginalDocument, SearchQuery, PrivacyAnalysis, SearchResult
from .serializers import SearchQuerySerializer, OriginalDocumentSerializer, OriginalDocumentListSerializer
logger = logging.getLogger(__name__)

def _db_web_source(search_source):
    """Map internal online providers to DB/frontend source labels."""
    if search_source in ('bing', 'gemini+bing'):
        return 'bing'
    return 'google'

class HealthCheckView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        original_count = OriginalDocument.objects.count()
        from services.privacy_service import PrivacyService
        return Response({
            'status': 'ok',
            'service': 'pencari-doksli-api',
            'original_count': original_count,
            'google_vision_api_configured': bool(settings.GOOGLE_CLOUD_API_KEY),
            'privacy_flag_threshold': settings.PRIVACY_FLAG_THRESHOLD,
            'privacy_detectors': PrivacyService.get_capabilities(),
        }, status=status.HTTP_200_OK)

class FileHelper:
    @staticmethod
    def _save_uploaded_file(uploaded_file, subfolder='uploads'):
        """Save an uploaded file to the media directory and return the path."""
        media_dir = os.path.join(settings.MEDIA_ROOT, subfolder)
        os.makedirs(media_dir, exist_ok=True)
        ext = os.path.splitext(uploaded_file.name)[1] or '.jpg'
        filename = f'{uuid.uuid4().hex}{ext}'
        filepath = os.path.join(media_dir, filename)
        with open(filepath, 'wb') as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)
        return filepath

    @staticmethod
    def _compute_file_hash(filepath):
        """Compute SHA-256 hash of a file."""
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def _encode_image_data(filepath):
        """Return base64 image data and MIME type for durable DB fallback."""
        mime_type, _ = mimetypes.guess_type(filepath)
        if not mime_type or not mime_type.startswith('image/'):
            mime_type = 'image/jpeg'
        with open(filepath, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('ascii')
        return image_data, mime_type

class SearchImageView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    def post(self, request):
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
            return Response({'error': 'No image file provided. Use "image" field.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            filepath = FileHelper._save_uploaded_file(image_file, subfolder='queries')
            file_hash = FileHelper._compute_file_hash(filepath)
            search_query = SearchQuery.objects.create(query_image_path=filepath, query_hash=file_hash, search_source='local')
            from services.privacy_service import PrivacyService
            privacy_result = PrivacyService.analyze_privacy(filepath)
            privacy = PrivacyAnalysis.objects.create(search=search_query, face_detected=privacy_result['face_detected'], name_detected=privacy_result['name_detected'], age_detected=privacy_result['age_detected'], address_detected=privacy_result['address_detected'], phone_detected=privacy_result['phone_detected'], total_flags=privacy_result['total_flags'], is_blocked=privacy_result['is_blocked'])
            if privacy.is_blocked:
                serializer = SearchQuerySerializer(search_query)
                return Response({'status': 'blocked', 'message': f'Pencarian diblokir: terdeteksi {privacy.total_flags} kategori informasi pribadi. Minimum {settings.PRIVACY_FLAG_THRESHOLD} flag untuk pemblokiran.', 'data': serializer.data}, status=status.HTTP_403_FORBIDDEN)
            from services.privacy_service import PrivacyService
            masked_path = PrivacyService.blur_pii_regions(filepath, privacy_result)
            if masked_path != filepath:
                search_query.query_image_path = masked_path
                search_query.save(update_fields=['query_image_path'])
                logger.info(f'Query image replaced with masked version: {masked_path}')
            from services.embedding_service import EmbeddingService
            query_embedding = EmbeddingService.extract_embedding(filepath)
            from services.similarity_service import SimilarityService
            local_limit = getattr(settings, 'LOCAL_RESULTS_LIMIT', 3)
            web_default_limit = getattr(settings, 'WEB_RESULTS_LIMIT', 7)
            web_incomplete_limit = getattr(settings, 'WEB_RESULTS_LIMIT_WHEN_LOCAL_INCOMPLETE', 10)
            local_original_count = OriginalDocument.objects.count()
            local_matches = []
            if local_original_count:
                local_candidates = SimilarityService.find_candidate_pool(query_embedding)
                local_candidates = SimilarityService.re_rank_local_candidates(filepath, local_candidates)
                local_matches = SimilarityService.filter_reliable_local_matches(local_candidates, top_k=local_limit)
                if local_matches:
                    logger.info(
                        f"Local search accepted {len(local_matches)} match(es). "
                        f"Best score: {local_matches[0]['score']}"
                    )
                else:
                    logger.info(
                        f'Local search checked {local_original_count} document(s) '
                        'but found no reliable Doksli match. Continuing fallback search.'
                    )
            else:
                logger.warning('Local search skipped because original document database is empty.')
            crop_paths = []
            if len(local_matches) < local_limit:
                try:
                    from services.cropping_service import CroppingService
                    crop_paths = CroppingService.generate_crop_regions(filepath)
                    if crop_paths:
                        logger.info(f'Local search has {len(local_matches)}/{local_limit} reliable match(es). Trying {len(crop_paths)} sub-region crops...')
                        best_crop_matches = []
                        for crop_path in crop_paths:
                            try:
                                crop_embedding = EmbeddingService.extract_embedding(crop_path)
                                crop_matches = SimilarityService.find_candidate_pool(crop_embedding)
                                for match in crop_matches:
                                    best_crop_matches.append(match)
                            except Exception as e:
                                logger.warning(f'Crop embedding/search failed for {crop_path}: {e}')
                                continue
                        if best_crop_matches:
                            seen = {}
                            for match in local_matches:
                                doc_id = str(match['document'].id)
                                seen[doc_id] = match
                            for match in best_crop_matches:
                                doc_id = str(match['document'].id)
                                if doc_id not in seen or match['score'] > seen[doc_id]['score']:
                                    seen[doc_id] = match
                            best_crop_matches = sorted(seen.values(), key=lambda x: x['score'], reverse=True)
                            best_crop_matches = SimilarityService.re_rank_local_candidates(filepath, best_crop_matches)
                            best_crop_matches = SimilarityService.filter_reliable_local_matches(best_crop_matches, top_k=local_limit)
                            local_matches = best_crop_matches
                            if local_matches:
                                logger.info(f"Sub-region search found {len(local_matches)} match(es). Best score: {local_matches[0]['score']}")
                            else:
                                logger.info('Sub-region search found no reliable local Doksli match.')
                except Exception as e:
                    logger.error(f'Sub-region search error: {e}', exc_info=True)
                finally:
                    if crop_paths:
                        try:
                            from services.cropping_service import CroppingService
                            CroppingService.cleanup_crops(crop_paths)
                        except Exception:
                            pass
            for match in local_matches[:local_limit]:
                SearchResult.objects.create(search=search_query, source_type='local', matched_document=match['document'], similarity_score=match['score'])
            web_candidates = []
            web_results_created = 0
            web_limit = web_default_limit if len(local_matches) >= local_limit else web_incomplete_limit
            search_source = 'none'
            try:
                from services.online_search_service import OnlineSearchService
                from services.similarity_service import SimilarityService
                logger.info(
                    f'Starting online search with limit={web_limit} '
                    f'(local reliable={len(local_matches)}/{local_limit}).'
                )
                online_result = OnlineSearchService.search_online(filepath, max_candidates=web_limit)
                web_candidates = online_result.get('candidates', [])
                search_source = online_result.get('search_source', 'none')
                if web_candidates:
                    ranked_all = SimilarityService.re_rank_web_candidates(filepath, query_embedding, web_candidates)
                    online_threshold = getattr(settings, 'ONLINE_MATCH_THRESHOLD', 0.65)
                    fallback_min = getattr(settings, 'ONLINE_FALLBACK_MIN_SCORE', 0.35)
                    ranked_web = [
                        ranked for ranked in ranked_all
                        if ranked.get('score', 0) >= online_threshold
                    ]
                    if len(ranked_web) < web_limit:
                        seen_paths = {ranked.get('path') for ranked in ranked_web}
                        seen_urls = {ranked.get('url') for ranked in ranked_web}
                        for ranked in ranked_all:
                            if len(ranked_web) >= web_limit:
                                break
                            if ranked.get('path') in seen_paths or ranked.get('url') in seen_urls:
                                continue
                            if ranked.get('score', 0) >= fallback_min:
                                ranked_web.append(ranked)
                                seen_paths.add(ranked.get('path'))
                                seen_urls.add(ranked.get('url'))
                    ranked_web = ranked_web[:web_limit]
                    db_source_type = _db_web_source(search_source)
                    kept_paths = set()
                    for ranked in ranked_web:
                        url = ranked.get('url', '')
                        path = ranked.get('path', '')
                        external_url = url if str(url).startswith(('http://', 'https://')) else ''
                        SearchResult.objects.create(
                            search=search_query,
                            source_type=db_source_type,
                            matched_image_path=path,
                            external_url=external_url,
                            similarity_score=ranked['score']
                        )
                        web_results_created += 1
                        if path:
                            kept_paths.add(path)
                    cleanup_candidates = [
                        candidate for candidate in web_candidates
                        if candidate.get('path') not in kept_paths
                    ]
                    OnlineSearchService.cleanup_candidates(cleanup_candidates)
                    logger.info(
                        f'Online search accepted {web_results_created}/{web_limit} candidate(s) '
                        f'(source={search_source}, threshold={online_threshold}, fallback_min={fallback_min})'
                    )
                elif online_result.get('google_web_results'):
                    web_results = online_result['google_web_results']
                    all_web_urls = []
                    online_threshold = getattr(settings, 'ONLINE_MATCH_THRESHOLD', 0.65)
                    for img in web_results.get('full_matching_images', []):
                        all_web_urls.append((img['url'], img.get('score', 0.9)))
                    for img in web_results.get('partial_matching_images', []):
                        all_web_urls.append((img['url'], img.get('score', 0.7)))
                    for img in web_results.get('visually_similar_images', []):
                        all_web_urls.append((img['url'], img.get('score', 0.5)))
                    for url, score in all_web_urls[:web_limit]:
                        if score < online_threshold:
                            continue
                        SearchResult.objects.create(search=search_query, source_type='google', external_url=url, similarity_score=score)
                        web_results_created += 1
            except Exception as e:
                logger.error(f'Online search failed: {e}', exc_info=True)
            finally:
                for candidate in web_candidates:
                    src = candidate.get('path', '')
                    if src and os.path.exists(src):
                        linked = SearchResult.objects.filter(search=search_query, matched_image_path=src).exists()
                        if linked:
                            continue
                        try:
                            os.remove(src)
                        except Exception:
                            pass
            if local_matches and web_results_created:
                search_query.search_source = 'both'
                search_query.save(update_fields=['search_source'])
            elif local_matches:
                search_query.search_source = 'local'
                search_query.save(update_fields=['search_source'])
            elif web_results_created or search_source != 'none':
                search_query.search_source = _db_web_source(search_source)
                search_query.save(update_fields=['search_source'])
            try:
                from services.forensic_service import ForensicService
                ela_result = ForensicService.perform_ela(filepath)
                if ela_result.get('ela_image_path'):
                    ForensicService.cleanup_ela_files(ela_result['ela_image_path'])
                logger.info(f"ELA analysis: score={ela_result['ela_score']:.2f}, suspicious={ela_result['is_suspicious']}")
            except Exception as e:
                logger.warning(f'ELA analysis skipped: {e}')
            search_query.refresh_from_db()
            serializer = SearchQuerySerializer(search_query)
            return Response({'status': 'success', 'message': 'Analisis selesai', 'data': serializer.data}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f'Search error: {e}', exc_info=True)
            return Response({'error': f'Terjadi kesalahan saat memproses gambar: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AddOriginalView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    def post(self, request):
        """
        POST /api/add-original/

        Upload an original document to the local database.
        Generates embedding and stores image with hash for deduplication.
        """
        image_file = request.FILES.get('image')
        if not image_file:
            return Response({'error': 'No image file provided. Use "image" field.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            filepath = FileHelper._save_uploaded_file(image_file, subfolder='originals')
            file_hash = FileHelper._compute_file_hash(filepath)
            image_data, image_mime_type = FileHelper._encode_image_data(filepath)
            existing = OriginalDocument.objects.filter(file_hash=file_hash).first()
            if existing:
                update_fields = []
                if existing.image_path != filepath:
                    existing.image_path = filepath
                    update_fields.append('image_path')
                if not existing.image_data:
                    existing.image_data = image_data
                    update_fields.append('image_data')
                if existing.image_mime_type != image_mime_type:
                    existing.image_mime_type = image_mime_type
                    update_fields.append('image_mime_type')
                if update_fields:
                    existing.save(update_fields=update_fields)
                serializer = OriginalDocumentSerializer(existing)
                return Response({'status': 'duplicate', 'message': 'Dokumen dengan hash yang sama sudah ada di database.', 'data': serializer.data}, status=status.HTTP_409_CONFLICT)
            from services.embedding_service import EmbeddingService
            embedding = EmbeddingService.extract_embedding(filepath)
            document = OriginalDocument.objects.create(
                image_path=filepath,
                image_data=image_data,
                image_mime_type=image_mime_type,
                embedding_vector=embedding,
                file_hash=file_hash,
            )
            serializer = OriginalDocumentSerializer(document)
            return Response({'status': 'success', 'message': 'Dokumen asli berhasil ditambahkan.', 'data': serializer.data}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f'Add original error: {e}', exc_info=True)
            return Response({'error': f'Terjadi kesalahan: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ResultDetailView(APIView):
    def get(self, request, search_id):
        """
        GET /api/results/<search_id>/

        Get detailed search results including privacy analysis.
        """
        try:
            search_query = SearchQuery.objects.get(pk=search_id)
        except SearchQuery.DoesNotExist:
            return Response({'error': 'Hasil pencarian tidak ditemukan.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = SearchQuerySerializer(search_query)
        return Response({'status': 'success', 'data': serializer.data}, status=status.HTTP_200_OK)

class ListOriginalsView(APIView):
    def get(self, request):
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
        return Response({'status': 'success', 'data': serializer.data}, status=status.HTTP_200_OK)
ADMIN_USERNAME = settings.ADMIN_USERNAME
ADMIN_PASSWORD = settings.ADMIN_PASSWORD

class AdminLoginView(APIView):
    def post(self, request):
        """
        POST /api/admin/login/

        Simple admin authentication with hardcoded credentials.
        Returns a token-like response for frontend session management.
        """
        username = str(request.data.get('username', '')).strip()
        password = str(request.data.get('password', '')).strip()
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            return Response({'status': 'success', 'message': 'Login berhasil.', 'admin': True}, status=status.HTTP_200_OK)
        return Response({'error': 'Username atau password salah.'}, status=status.HTTP_401_UNAUTHORIZED)

class DeleteOriginalView(APIView):
    def delete(self, request, document_id):
        """
        DELETE /api/admin/originals/<document_id>/

        Delete an original document from the database.
        Requires admin auth header.
        """
        auth = request.headers.get('X-Admin-Auth', '')
        if auth != f'{ADMIN_USERNAME}:{ADMIN_PASSWORD}':
            return Response({'error': 'Akses ditolak. Login sebagai admin terlebih dahulu.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            document = OriginalDocument.objects.get(pk=document_id)
        except OriginalDocument.DoesNotExist:
            return Response({'error': 'Dokumen tidak ditemukan.'}, status=status.HTTP_404_NOT_FOUND)
        if document.image_path:
            try:
                file_path = str(document.image_path)
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.warning(f'Could not delete file: {e}')
        doc_id = str(document.id)
        document.delete()
        return Response({'status': 'success', 'message': f'Dokumen {doc_id[:8]}... berhasil dihapus.'}, status=status.HTTP_200_OK)
