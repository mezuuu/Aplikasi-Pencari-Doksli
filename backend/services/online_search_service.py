"""
Modular online image search service.

Provides a fallback pipeline when Google Cloud Vision API is unavailable:
1. Google Cloud Vision Web Detection (if API key/credentials active)
2. Yandex Reverse Image Search (free, visual similarity - like Google Lens)
2.5. Google Lens direct upload (bonus, may return nothing due to JS)
2.7. Gemini AI keyword extraction (if GEMINI_API_KEY is set)
3. Bing Image Search via icrawler (free, keyword-based fallback)

Strategy:
- Yandex is the PRIMARY free fallback because it performs actual reverse
  image search (uploading the image and finding visual matches), similar
  to how Google Lens works.
- Gemini AI generates high-quality search keywords by understanding image
  content (document type, logos, context) — far superior to basic OCR.
- Bing/icrawler is a SECONDARY fallback using keywords (from Gemini or OCR),
  only used if reverse image search methods fail entirely.
"""
import logging
import os
import re
import uuid
import shutil
import html as html_module
import requests
from django.conf import settings as django_settings
logger = logging.getLogger(__name__)
MAX_CANDIDATES = 20
DOWNLOAD_TIMEOUT = 10
SEARCH_TIMEOUT = 30
MIN_IMAGE_SIZE = 5000
MAX_IMAGE_SIZE = 10000000
_google_vision_failed = False

class OnlineSearchService:

    @staticmethod
    def _google_vision_search(image_path):
        """
    Search using Google Cloud Vision Web Detection.
    Returns list of image URLs found online.
    Caches failure so we don't retry a broken API on every request.
    """
        global _google_vision_failed
        if _google_vision_failed:
            logger.debug('[Google Vision] Skipping (previously failed)')
            return ([], {})
        try:
            from services.vision_service import VisionService
            web_results = VisionService.detect_web_matches(image_path)
            urls = []
            for img in web_results.get('full_matching_images', []):
                if img.get('url'):
                    urls.append(img['url'])
            for img in web_results.get('partial_matching_images', []):
                if img.get('url'):
                    urls.append(img['url'])
            for img in web_results.get('visually_similar_images', []):
                if img.get('url'):
                    urls.append(img['url'])
            logger.info(f'[Google Vision] Found {len(urls)} candidate URLs')
            return (urls, web_results)
        except Exception as e:
            error_msg = str(e).lower()
            if any((keyword in error_msg for keyword in ['billing', 'permission', 'forbidden', '403', 'disabled', 'quota', 'not enabled', 'access denied'])):
                _google_vision_failed = True
                logger.warning(f'[Google Vision] Permanently disabled for this session (billing/permission error): {e}')
            else:
                logger.warning(f'[Google Vision] Web detection failed: {e}')
            return ([], {})

    @staticmethod
    def _is_google_available():
        """Check if Google Cloud Vision API is configured and likely available."""
        if _google_vision_failed:
            return False
        api_key = getattr(django_settings, 'GOOGLE_CLOUD_API_KEY', '')
        if api_key and api_key != 'your-api-key-here' and (api_key != 'API-KEY'):
            return True
        creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '')
        if creds_path and os.path.isfile(creds_path):
            return True
        return False

    @staticmethod
    def _yandex_reverse_image_search(image_path, max_results=MAX_CANDIDATES):
        """
    Perform reverse image search using Yandex (works like Google Lens).

    Queries two modes for maximum accuracy:
    1. 'sites' mode — finds pages where THIS EXACT image appears online.
       This is the closest equivalent to Google Lens's "exact match".
    2. 'similar' mode — finds visually similar images across the web.

    Sites-mode results are prioritized because they represent the
    actual original document found on real web pages.

    Args:
        image_path: Path to the query image file.
        max_results: Maximum number of image URLs to return.

    Returns:
        list[str]: URLs of matching/similar images found online,
                   ordered by relevance (exact matches first).
    """
        urls = []
        try:
            session = requests.Session()
            session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'Accept-Language': 'en-US,en;q=0.9'})
            with open(image_path, 'rb') as f:
                upload_resp = session.post('https://yandex.com/images/search', params={'rpt': 'imageview'}, files={'upfile': ('image.jpg', f, 'image/jpeg')}, data={'prg': '1'}, timeout=SEARCH_TIMEOUT, allow_redirects=False)
            if upload_resp.status_code not in (301, 302, 303):
                logger.warning(f'[Yandex] Unexpected upload status: {upload_resp.status_code}')
                return urls
            redirect_url = upload_resp.headers.get('Location', '')
            cbir_match = re.search('cbir_id=([^&]+)', redirect_url)
            if not cbir_match:
                logger.warning('[Yandex] No CBIR ID in redirect URL')
                return urls
            cbir_id = cbir_match.group(1)
            logger.info(f'[Yandex] Image uploaded, CBIR ID: {cbir_id}')
            seen = set()
            skip_patterns = ['yastatic.net', 'avatars.mds.yandex.net', 'yandex.net', 'favicon', '.css', '.js', '.svg', '.ico', 'yandex.ru/images']
            for mode in ['sites', 'similar']:
                if len(urls) >= max_results:
                    break
                try:
                    search_resp = session.get('https://yandex.com/images/search', params={'rpt': 'imageview', 'cbir_id': cbir_id, 'cbir_page': mode}, timeout=SEARCH_TIMEOUT)
                    if search_resp.status_code != 200:
                        logger.debug(f'[Yandex] {mode} page status: {search_resp.status_code}')
                        continue
                    decoded = html_module.unescape(search_resp.text)
                    raw_urls = re.findall('https?://[^\\s"\\\'<>]+\\.(?:jpg|jpeg|png|webp)', decoded)
                    originals = []
                    thumbnails = []
                    for url in raw_urls:
                        url_lower = url.lower()
                        if any((skip in url_lower for skip in skip_patterns)):
                            continue
                        if len(url) < 30 or 'data:image' in url:
                            continue
                        if url in seen:
                            continue
                        if any((indicator in url_lower for indicator in ['/originals/', '/original/', 'full_size', 'maxresdefault', '/photo/', '/upload/'])):
                            originals.append(url)
                        elif any((indicator in url_lower for indicator in ['/236x/', '/150x/', '/100x/', 'thumb', 'small', 'mini', '_s.', '_t.', '_m.'])):
                            thumbnails.append(url)
                        else:
                            originals.append(url)
                    for url in originals + thumbnails:
                        if url in seen:
                            continue
                        seen.add(url)
                        urls.append(url)
                        if len(urls) >= max_results:
                            break
                    logger.info(f"[Yandex] Mode '{mode}': {len(originals)} originals, {len(thumbnails)} thumbnails extracted")
                except Exception as e:
                    logger.debug(f"[Yandex] Mode '{mode}' failed: {e}")
                    continue
            logger.info(f'[Yandex] Reverse image search found {len(urls)} candidate URLs')
        except requests.RequestException as e:
            logger.warning(f'[Yandex] Search request failed: {e}')
        except Exception as e:
            logger.error(f'[Yandex] Unexpected error: {e}', exc_info=True)
        return urls

    @staticmethod
    def _google_lens_search(image_path, max_results=MAX_CANDIDATES):
        """
    Attempt reverse image search via Google Lens direct upload.

    Google Lens renders results via JavaScript (SPA), so this method
    has limited success with plain HTTP. It's included as a bonus
    layer; if it extracts any URLs, they're typically very high quality.

    Returns:
        list[str]: Image URLs found (may be empty if JS-rendered).
    """
        urls = []
        try:
            with open(image_path, 'rb') as f:
                img_data = f.read()
            resp = requests.post('https://lens.google.com/v3/upload', files={'encoded_image': ('image.jpg', img_data, 'image/jpeg')}, data={'sbisrc': '1'}, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}, timeout=SEARCH_TIMEOUT, allow_redirects=True)
            if resp.status_code != 200:
                return urls
            decoded = html_module.unescape(resp.text)
            google_skip = ['gstatic', 'google.com', 'googleusercontent.com/s2', 'ssl.gstatic', 'googleapis.com']
            raw_urls = re.findall('https?://[^\\s"\\\'<>]+\\.(?:jpg|jpeg|png|webp)', decoded)
            seen = set()
            for url in raw_urls:
                if any((skip in url.lower() for skip in google_skip)):
                    continue
                if url in seen or len(url) < 30:
                    continue
                seen.add(url)
                urls.append(url)
                if len(urls) >= max_results:
                    break
            if urls:
                logger.info(f'[Google Lens] Found {len(urls)} image URLs')
            else:
                logger.debug('[Google Lens] No parseable image URLs (JS-rendered)')
        except Exception as e:
            logger.debug(f'[Google Lens] Failed: {e}')
        return urls

    @staticmethod
    def _extract_search_keywords(image_path):
        """
    Extract search keywords from image using OCR.
    Supports both Indonesian and English text.
    Returns a search query string.
    """
        keywords = []
        try:
            from services.privacy_service import PrivacyService
            text = PrivacyService._local_detect_text(image_path)
            if text and len(text.strip()) > 5:
                words = re.findall('[A-Za-z\\u00C0-\\u024F]{3,}', text)
                if not words:
                    words = re.findall('\\b\\w{3,}\\b', text)
                noise = {'the', 'and', 'for', 'that', 'this', 'with', 'dari', 'yang', 'dan', 'untuk', 'dengan', 'ini', 'itu', 'adalah', 'pada', 'tidak', 'akan', 'juga', 'telah', 'jpg', 'png', 'img', 'image', 'foto', 'photo', 'http', 'https', 'www', 'com'}
                seen = set()
                for w in words:
                    w_lower = w.lower()
                    if w_lower not in seen and w_lower not in noise and (len(w_lower) >= 3):
                        seen.add(w_lower)
                        keywords.append(w)
                        if len(keywords) >= 8:
                            break
                logger.info(f'[Keywords] OCR extracted {len(keywords)} keywords')
        except Exception as e:
            logger.debug(f'OCR keyword extraction failed: {e}')
        if not keywords:
            basename = os.path.splitext(os.path.basename(image_path))[0]
            file_words = [w for w in re.split('[^a-zA-Z]+', basename) if len(w) >= 3]
            keywords = file_words[:5]
        if not keywords:
            keywords = ['dokumen', 'sertifikat', 'resmi']
        query = ' '.join(keywords[:8])
        logger.info(f"[Keywords] Final search query: '{query}'")
        return query

    @staticmethod
    def _bing_image_search(query, max_results=MAX_CANDIDATES, download_dir=None):
        """
    Search and download images from Bing using icrawler.
    This is a keyword-based search, less accurate than reverse image search.

    Returns:
        list[dict]: Downloaded candidates with 'path', 'url', 'source' keys.
    """
        if download_dir is None:
            download_dir = os.path.join(str(django_settings.MEDIA_ROOT), 'temp_candidates')
        os.makedirs(download_dir, exist_ok=True)
        candidates = []
        try:
            from icrawler.builtin import BingImageCrawler
            search_id = uuid.uuid4().hex[:8]
            search_dir = os.path.join(download_dir, f'search_{search_id}')
            os.makedirs(search_dir, exist_ok=True)
            crawler = BingImageCrawler(storage={'root_dir': search_dir}, log_level=logging.WARNING)
            crawler.crawl(keyword=query, max_num=max_results, file_idx_offset=0)
            if os.path.isdir(search_dir):
                for filename in sorted(os.listdir(search_dir)):
                    filepath = os.path.join(search_dir, filename)
                    if not os.path.isfile(filepath):
                        continue
                    file_size = os.path.getsize(filepath)
                    if file_size < MIN_IMAGE_SIZE or file_size > MAX_IMAGE_SIZE:
                        os.remove(filepath)
                        continue
                    try:
                        from PIL import Image
                        with Image.open(filepath) as img:
                            img.verify()
                    except Exception:
                        os.remove(filepath)
                        continue
                    candidates.append({'path': filepath, 'url': f'bing://{query}/{filename}', 'source': 'bing'})
                    if len(candidates) >= max_results:
                        break
            logger.info(f"[Bing/icrawler] Downloaded {len(candidates)} images for: '{query}'")
        except ImportError:
            logger.warning('[Bing/icrawler] icrawler not installed')
        except Exception as e:
            logger.error(f'[Bing/icrawler] Search failed: {e}', exc_info=True)
        return candidates

    @staticmethod
    def _download_candidate_images(urls, max_count=MAX_CANDIDATES):
        """
    Download candidate images from URLs to temporary local files.

    Returns:
        list[dict]: List of dicts with 'path', 'url', and 'source' keys.
    """
        candidates = []
        download_dir = os.path.join(str(django_settings.MEDIA_ROOT), 'temp_candidates')
        os.makedirs(download_dir, exist_ok=True)
        for url in urls[:max_count * 2]:
            if len(candidates) >= max_count:
                break
            try:
                resp = requests.get(url, timeout=DOWNLOAD_TIMEOUT, stream=True, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})
                resp.raise_for_status()
                content_type = resp.headers.get('Content-Type', '')
                if not content_type.startswith('image/'):
                    continue
                if 'png' in content_type:
                    ext = '.png'
                elif 'webp' in content_type:
                    ext = '.webp'
                else:
                    ext = '.jpg'
                filename = f'candidate_{uuid.uuid4().hex[:12]}{ext}'
                filepath = os.path.join(download_dir, filename)
                content = resp.content
                content_size = len(content)
                if content_size < MIN_IMAGE_SIZE or content_size > MAX_IMAGE_SIZE:
                    continue
                with open(filepath, 'wb') as f:
                    f.write(content)
                candidates.append({'path': filepath, 'url': url, 'source': 'web'})
            except Exception as e:
                logger.debug(f'Failed to download {url[:80]}: {e}')
                continue
        logger.info(f'Downloaded {len(candidates)}/{len(urls)} candidate images')
        return candidates

    @staticmethod
    def cleanup_candidates(candidates):
        """Delete temporary candidate image files from disk."""
        removed = 0
        dirs_to_check = set()
        for item in candidates:
            path = item.get('path', item) if isinstance(item, dict) else item
            try:
                if os.path.exists(path):
                    os.remove(path)
                    removed += 1
                    parent = os.path.dirname(path)
                    if 'search_' in os.path.basename(parent):
                        dirs_to_check.add(parent)
            except Exception as e:
                logger.warning(f'Failed to remove candidate file {path}: {e}')
        for d in dirs_to_check:
            try:
                if os.path.isdir(d) and (not os.listdir(d)):
                    os.rmdir(d)
            except Exception:
                pass
        logger.info(f'Cleaned up {removed}/{len(candidates)} candidate files')

    @staticmethod
    def search_online(image_path, max_candidates=MAX_CANDIDATES):
        """
    Perform modular online image search.

    Priority:
    1. Google Cloud Vision (if API key/credentials available)
    2. Yandex Reverse Image Search (free, visual - like Google Lens)
    2.5. Google Lens (bonus layer)
    2.7. Gemini AI keyword generation (if GEMINI_API_KEY is set)
    3. Bing Image Search via icrawler (free, keyword-based)

    Args:
        image_path: Path to the query image.
        max_candidates: Maximum number of candidate images to download.

    Returns:
        dict with:
            - candidates: list[dict] -- downloaded candidate images
            - search_source: str -- 'google', 'yandex', 'gemini+google',
                                     'gemini+bing', 'bing', or 'none'
            - google_web_results: dict -- raw Google Vision results (if used)
            - gemini_analysis: dict -- Gemini image analysis (if used)
            - total_urls_found: int -- total URLs discovered
            - search_query: str -- keyword query used (if applicable)
    """
        result = {'candidates': [], 'search_source': 'none', 'google_web_results': {}, 'gemini_analysis': {}, 'total_urls_found': 0, 'search_query': ''}
        all_url_candidates = []
        direct_candidates = []
        if OnlineSearchService._is_google_available():
            logger.info('[Online Search] Trying Google Cloud Vision...')
            google_urls, web_results = OnlineSearchService._google_vision_search(image_path)
            result['google_web_results'] = web_results
            if google_urls:
                all_url_candidates.extend(google_urls)
                result['search_source'] = 'google'
                logger.info(f'[Online Search] Google Vision returned {len(google_urls)} URLs')
        remaining_needed = max_candidates - len(all_url_candidates) - len(direct_candidates)
        if remaining_needed > 0:
            logger.info('[Online Search] Using Yandex reverse image search...')
            yandex_urls = OnlineSearchService._yandex_reverse_image_search(image_path, remaining_needed)
            if yandex_urls:
                existing = set(all_url_candidates)
                for url in yandex_urls:
                    if url not in existing:
                        all_url_candidates.append(url)
                        existing.add(url)
                if result['search_source'] == 'none':
                    result['search_source'] = 'yandex'
                logger.info(f'[Online Search] Yandex returned {len(yandex_urls)} visual matches')
        remaining_needed = max_candidates - len(all_url_candidates) - len(direct_candidates)
        if remaining_needed > 0:
            lens_urls = OnlineSearchService._google_lens_search(image_path, remaining_needed)
            if lens_urls:
                existing = set(all_url_candidates)
                for url in lens_urls:
                    if url not in existing:
                        all_url_candidates.insert(0, url)
                        existing.add(url)
                if result['search_source'] == 'none':
                    result['search_source'] = 'google'
                logger.info(f'[Online Search] Google Lens returned {len(lens_urls)} URLs')
        gemini_keywords = ''
        remaining_needed = max_candidates - len(all_url_candidates) - len(direct_candidates)
        if remaining_needed > 0:
            try:
                from services.gemini_search_service import GeminiSearchService
                if GeminiSearchService.is_gemini_available():
                    logger.info('[Online Search] Using Gemini AI + Google Search...')
                    gemini_query, gemini_urls, gemini_analysis = GeminiSearchService.gemini_enhanced_keyword_search(image_path)
                    result['gemini_analysis'] = gemini_analysis
                    if gemini_urls:
                        existing = set(all_url_candidates)
                        added = 0
                        for url in gemini_urls:
                            if url not in existing:
                                all_url_candidates.insert(0, url)
                                existing.add(url)
                                added += 1
                        if result['search_source'] == 'none':
                            result['search_source'] = 'gemini+google'
                        logger.info(f'[Online Search] Gemini+Google Search found {added} new URLs')
                    if gemini_query:
                        gemini_keywords = gemini_query
                        result['search_query'] = gemini_query
                        logger.info(f"[Online Search] Gemini keywords: '{gemini_query[:80]}'")
            except ImportError:
                logger.debug('[Online Search] Gemini search service not available')
            except Exception as e:
                logger.warning(f'[Online Search] Gemini analysis failed: {e}')
        remaining_needed = max_candidates - len(all_url_candidates) - len(direct_candidates)
        if remaining_needed > 0 and (not all_url_candidates):
            if gemini_keywords:
                keywords = gemini_keywords
                search_source_label = 'gemini+bing'
                logger.info(f"[Online Search] Using Gemini-enhanced keywords for Bing: '{keywords[:80]}'")
            else:
                logger.info('[Online Search] Using OCR keyword fallback for Bing...')
                keywords = OnlineSearchService._extract_search_keywords(image_path)
                search_source_label = 'bing'
            result['search_query'] = keywords
            if keywords:
                bing_candidates = OnlineSearchService._bing_image_search(keywords, remaining_needed)
                if bing_candidates:
                    direct_candidates.extend(bing_candidates)
                    if result['search_source'] == 'none':
                        result['search_source'] = search_source_label
                    logger.info(f'[Online Search] Bing downloaded {len(bing_candidates)} candidates')
        if all_url_candidates:
            remaining_needed = max_candidates - len(direct_candidates)
            if remaining_needed > 0:
                downloaded = OnlineSearchService._download_candidate_images(all_url_candidates, remaining_needed)
                direct_candidates.extend(downloaded)
        result['candidates'] = direct_candidates[:max_candidates]
        result['total_urls_found'] = len(all_url_candidates) + len(direct_candidates)
        logger.info(f"[Online Search] Complete: {len(result['candidates'])} candidates from {result['search_source']}")
        return result