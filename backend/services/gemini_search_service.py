"""
Gemini AI-powered image search service.

Uses Google Gemini API as an intelligent fallback for reverse image search.
Instead of relying on basic OCR for keyword extraction, Gemini can:

1. Describe the image content in detail → much better search keywords
2. Identify document types, logos, watermarks, and contextual clues
3. Suggest potential sources where the image might have originated

This service is used as a fallback in the search pipeline when:
- Google Cloud Vision is unavailable (billing/quota)
- Yandex reverse image search returns no results
- Before falling back to basic Bing keyword search

Requirements:
    pip install google-genai

Configuration:
    Set GEMINI_API_KEY in your .env file.
"""

import base64
import logging
import mimetypes
import os
import re
import uuid

import requests
from django.conf import settings as django_settings

logger = logging.getLogger(__name__)

# --- Configuration ---
DOWNLOAD_TIMEOUT = 10
MIN_IMAGE_SIZE = 5_000
MAX_IMAGE_SIZE = 10_000_000

# How long (seconds) to wait before retrying a rate-limited key (1 hour)
QUOTA_COOLDOWN_SECONDS = 3600


# ======================================================================
#  API Key Rotation Manager
# ======================================================================

import time
import threading

class _GeminiKeyManager:
    """
    Manages a pool of Gemini API keys with automatic rotation.

    When a key hits a rate limit (429) or quota error, it is marked as
    exhausted with a cooldown timestamp. The manager automatically switches
    to the next available key. After QUOTA_COOLDOWN_SECONDS, exhausted keys
    are eligible for retry.

    Configuration (in .env):
        # Multiple keys (recommended):
        GEMINI_API_KEYS=key1,key2,key3

        # Single key fallback:
        GEMINI_API_KEY=key1
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._keys = []          # list of API key strings
        self._exhausted = {}     # {key: exhausted_at_timestamp}
        self._current_idx = 0
        self._initialized = False
        self._all_failed = False  # permanently disabled (auth error)

    def _load_keys(self):
        """Load keys from Django settings. Call once on first use."""
        if self._initialized:
            return

        # Try GEMINI_API_KEYS first (comma-separated pool)
        keys_str = getattr(django_settings, 'GEMINI_API_KEYS', '').strip()
        if keys_str:
            candidates = [
                k.strip() for k in keys_str.split(',')
                if k.strip() and k.strip() not in ('your-gemini-api-key-here', '')
            ]
            self._keys = candidates

        # Fallback: single GEMINI_API_KEY
        if not self._keys:
            single = getattr(django_settings, 'GEMINI_API_KEY', '').strip()
            if single and single not in ('your-gemini-api-key-here', ''):
                self._keys = [single]

        self._initialized = True

        if self._keys:
            logger.info(
                f"[Gemini KeyManager] Loaded {len(self._keys)} API key(s)"
            )
        else:
            logger.debug("[Gemini KeyManager] No API keys configured")

    def has_keys(self):
        """Return True if at least one key is configured."""
        self._load_keys()
        return bool(self._keys)

    def get_client(self):
        """
        Return a Gemini client using the next available key.
        Returns (client, api_key) or (None, None) if all keys exhausted.
        """
        self._load_keys()

        if self._all_failed or not self._keys:
            return None, None

        try:
            from google import genai
        except ImportError:
            logger.warning(
                "[Gemini] google-genai not installed: pip install google-genai"
            )
            return None, None

        with self._lock:
            now = time.time()
            total = len(self._keys)

            # Try each key starting from current index
            for attempt in range(total):
                idx = (self._current_idx + attempt) % total
                key = self._keys[idx]

                # Check if key is in cooldown
                exhausted_at = self._exhausted.get(key)
                if exhausted_at is not None:
                    elapsed = now - exhausted_at
                    if elapsed < QUOTA_COOLDOWN_SECONDS:
                        remaining = int(QUOTA_COOLDOWN_SECONDS - elapsed)
                        logger.debug(
                            f"[Gemini KeyManager] Key [{idx+1}/{total}] "
                            f"still cooling down ({remaining}s left)"
                        )
                        continue
                    else:
                        # Cooldown expired — allow retry
                        logger.info(
                            f"[Gemini KeyManager] Key [{idx+1}/{total}] "
                            f"cooldown expired, retrying"
                        )
                        del self._exhausted[key]

                # Key is available — create client
                client = genai.Client(api_key=key)
                self._current_idx = idx  # remember for next call
                logger.debug(
                    f"[Gemini KeyManager] Using key [{idx+1}/{total}]"
                )
                return client, key

            # All keys exhausted
            logger.warning(
                f"[Gemini KeyManager] All {total} key(s) are rate-limited. "
                f"Will retry after cooldown expires."
            )
            return None, None

    def mark_exhausted(self, api_key):
        """
        Mark a key as rate-limited (429). It will be skipped until
        QUOTA_COOLDOWN_SECONDS have passed.
        """
        with self._lock:
            self._exhausted[api_key] = time.time()
            total = len(self._keys)
            exhausted_count = len(self._exhausted)

            logger.warning(
                f"[Gemini KeyManager] Key marked as rate-limited "
                f"({exhausted_count}/{total} keys exhausted). "
                f"Auto-retry in {QUOTA_COOLDOWN_SECONDS // 60} min."
            )

            # Advance to next key for the next request
            self._current_idx = (self._current_idx + 1) % total

    def mark_auth_failed(self, api_key):
        """
        Mark a key as permanently invalid (401/403 auth error).
        Unlike rate limits, auth failures disable the key permanently.
        """
        with self._lock:
            if api_key in self._keys:
                self._keys.remove(api_key)
                logger.warning(
                    f"[Gemini KeyManager] Permanently removed invalid key. "
                    f"{len(self._keys)} key(s) remaining."
                )
            if not self._keys:
                self._all_failed = True
                logger.warning(
                    "[Gemini KeyManager] All keys permanently disabled."
                )

    def status(self):
        """Return a human-readable status summary."""
        self._load_keys()
        total = len(self._keys)
        exhausted = len(self._exhausted)
        available = total - exhausted
        return {
            'total_keys': total,
            'available': available,
            'exhausted': exhausted,
            'all_failed': self._all_failed,
        }


# Singleton key manager — shared across all requests in the process
_key_manager = _GeminiKeyManager()


def is_gemini_available():
    """Check if at least one Gemini API key is configured and not permanently failed."""
    return _key_manager.has_keys() and not _key_manager._all_failed


def _detect_mime_type(image_path):
    """Detect MIME type from file extension."""
    mime_type, _ = mimetypes.guess_type(image_path)
    if mime_type and mime_type.startswith('image/'):
        return mime_type
    # Default to JPEG if we can't detect
    return 'image/jpeg'


def gemini_describe_image(image_path):
    """
    Use Gemini to describe an image and extract intelligent search keywords.

    Automatically retries with the next available API key if rate-limited.

    Returns:
        dict with:
            - keywords: str -- optimized search query
            - description: str -- full image description
            - document_type: str -- identified document type (if applicable)
            - potential_sources: list[str] -- suggested source URLs/domains
    """
    result = {
        'keywords': '',
        'description': '',
        'document_type': '',
        'potential_sources': [],
    }

    if not is_gemini_available():
        return result

    try:
        from google.genai import types
    except ImportError:
        logger.warning("[Gemini] google-genai not installed")
        return result

    # Read image once, reuse across key retries
    try:
        with open(image_path, 'rb') as f:
            image_data = f.read()
    except OSError as e:
        logger.warning(f"[Gemini] Cannot read image: {e}")
        return result

    mime_type = _detect_mime_type(image_path)
    image_part = types.Part.from_bytes(data=image_data, mime_type=mime_type)

    prompt = """Analyze this image carefully and provide the following information in a structured format.
This image may be a document, certificate, ID card, screenshot, or any other type of image.

1. DESCRIPTION: A concise but detailed description of what this image contains (max 2 sentences).
2. DOCUMENT_TYPE: If this is a document/certificate/ID/card, identify the type. Otherwise write "photo" or "graphic".
3. KEYWORDS: Extract 5-8 of the most important and specific search keywords that would help find this exact image or similar images online. Focus on:
   - Any visible text (names, titles, organizations, ID numbers)
   - Document type and issuing organization
   - Distinctive visual elements (logos, seals, watermarks)
   - Context clues (country, language, institution)
   Do NOT include generic words like "image", "photo", "document".
4. SOURCES: If you can identify or guess the likely origin/source of this image (e.g., a specific website, institution, or organization), list up to 3 possible source domains.

Format your response EXACTLY like this (keep the labels):
DESCRIPTION: [your description]
DOCUMENT_TYPE: [type]
KEYWORDS: [keyword1, keyword2, keyword3, ...]
SOURCES: [source1, source2, ...]"""

    # --- Key rotation retry loop ---
    total_keys = len(_key_manager._keys)
    for attempt in range(max(1, total_keys)):
        client, active_key = _key_manager.get_client()
        if not client:
            logger.warning("[Gemini] No available API keys")
            break

        try:
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=[image_part, prompt],
            )

            if not response or not response.text:
                logger.warning("[Gemini] Empty response")
                return result

            text = response.text.strip()

            # Parse structured response
            desc_match = re.search(
                r'DESCRIPTION:\s*(.+?)(?=\nDOCUMENT_TYPE:|\Z)', text, re.DOTALL
            )
            type_match = re.search(
                r'DOCUMENT_TYPE:\s*(.+?)(?=\nKEYWORDS:|\Z)', text, re.DOTALL
            )
            keywords_match = re.search(
                r'KEYWORDS:\s*(.+?)(?=\nSOURCES:|\Z)', text, re.DOTALL
            )
            sources_match = re.search(
                r'SOURCES:\s*(.+?)$', text, re.DOTALL
            )

            if desc_match:
                result['description'] = desc_match.group(1).strip()
            if type_match:
                result['document_type'] = type_match.group(1).strip()
            if keywords_match:
                raw = keywords_match.group(1).strip().strip('[]')
                kws = [
                    k.strip().strip("\'\"")
                    for k in raw.split(',')
                    if k.strip() and k.strip() not in ('...', 'N/A', 'none', '-')
                ]
                result['keywords'] = ' '.join(kws[:8])
            if sources_match:
                raw = sources_match.group(1).strip().strip('[]')
                srcs = [
                    s.strip().strip("\'\"")
                    for s in raw.split(',')
                    if s.strip() and s.strip() not in ('...', 'N/A', 'none', '-', 'None', 'Unknown')
                ]
                result['potential_sources'] = srcs[:3]

            logger.info(
                f"[Gemini] Analysis OK — "
                f"type='{result['document_type']}', "
                f"kw='{result['keywords'][:50]}'"
            )
            return result  # success

        except Exception as e:
            error_msg = str(e).lower()
            if any(kw in error_msg for kw in ['401', '403', 'unauthorized', 'invalid', 'api_key']):
                # Auth failure — remove key permanently, try next
                logger.warning(f"[Gemini] Auth error on key, removing: {e}")
                _key_manager.mark_auth_failed(active_key)
                continue
            elif any(kw in error_msg for kw in ['429', 'quota', 'rate_limit', 'resource_exhausted']):
                # Rate limit — mark key, auto-switch to next
                logger.warning(f"[Gemini] Rate limit hit, switching key: {e}")
                _key_manager.mark_exhausted(active_key)
                continue
            else:
                logger.warning(f"[Gemini] Unexpected error: {e}")
                return result

    return result


def gemini_google_search_image(image_path, max_results=20):
    """
    Use Gemini with Google Search Grounding to find this image online.
    Automatically retries with the next available API key if rate-limited.

    Returns:
        dict with:
            - urls: list[str] -- actual image/page URLs found via Google Search
            - search_queries: list[str] -- queries Gemini used internally
            - description: str -- image description
            - grounding_sources: list[dict] -- raw grounding metadata
    """
    result = {
        'urls': [],
        'search_queries': [],
        'description': '',
        'grounding_sources': [],
    }

    if not is_gemini_available():
        return result

    try:
        from google.genai import types
    except ImportError:
        return result

    try:
        with open(image_path, 'rb') as f:
            image_data = f.read()
    except OSError as e:
        logger.warning(f"[Gemini+Search] Cannot read image: {e}")
        return result

    mime_type = _detect_mime_type(image_path)
    image_part = types.Part.from_bytes(data=image_data, mime_type=mime_type)
    google_search_tool = types.Tool(google_search=types.GoogleSearch())

    prompt = """Look at this image carefully. I need to find where this exact image or very similar versions of it appear online.

Please do the following:
1. Describe what this image contains (document type, visible text, logos, people, etc.)
2. Search Google to find web pages where this image or similar images appear.
3. List all the URLs you find where this image or visually similar versions exist online.

Focus on finding:
- The original source of this image
- Web pages that host this exact image
- Sites where similar documents/images are published

Format your response as:
DESCRIPTION: [what the image contains]
FOUND_URLS:
- [url1]
- [url2]
..."""

    # --- Key rotation retry loop ---
    total_keys = len(_key_manager._keys)
    for attempt in range(max(1, total_keys)):
        client, active_key = _key_manager.get_client()
        if not client:
            logger.warning("[Gemini+Search] No available API keys")
            break

        try:
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=[image_part, prompt],
                config=types.GenerateContentConfig(tools=[google_search_tool]),
            )

            if not response or not response.text:
                logger.warning("[Gemini+Search] Empty response")
                return result

            text = response.text.strip()

            desc_match = re.search(
                r'DESCRIPTION:\s*(.+?)(?=\nFOUND_URLS:|$)', text, re.DOTALL
            )
            if desc_match:
                result['description'] = desc_match.group(1).strip()

            url_pattern = re.compile(r'https?://[^\s<>"\'\)\]]+', re.IGNORECASE)
            found_urls = url_pattern.findall(text)

            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                grounding = getattr(candidate, 'grounding_metadata', None)
                if grounding:
                    web_queries = getattr(grounding, 'web_search_queries', None)
                    if web_queries:
                        result['search_queries'] = list(web_queries)
                    chunks = getattr(grounding, 'grounding_chunks', None)
                    if chunks:
                        for chunk in chunks:
                            web = getattr(chunk, 'web', None)
                            if web:
                                uri = getattr(web, 'uri', '')
                                title = getattr(web, 'title', '')
                                if uri:
                                    found_urls.append(uri)
                                    result['grounding_sources'].append({'url': uri, 'title': title})
                    supports = getattr(grounding, 'grounding_supports', None)
                    if supports:
                        for support in supports:
                            for idx in getattr(support, 'grounding_chunk_indices', []):
                                if chunks and idx < len(chunks):
                                    web = getattr(chunks[idx], 'web', None)
                                    if web:
                                        uri = getattr(web, 'uri', '')
                                        if uri:
                                            found_urls.append(uri)

            seen = set()
            skip_patterns = [
                'google.com/search', 'googleapis.com', 'gstatic.com',
                'googleusercontent.com/s2', 'schema.org',
            ]
            clean_urls = []
            for url in found_urls:
                url = url.rstrip('.,;:!?)]}')
                if url in seen or len(url) < 20:
                    continue
                if any(skip in url.lower() for skip in skip_patterns):
                    continue
                seen.add(url)
                clean_urls.append(url)
                if len(clean_urls) >= max_results:
                    break

            result['urls'] = clean_urls
            logger.info(
                f"[Gemini+Search] Found {len(clean_urls)} URLs, "
                f"{len(result['grounding_sources'])} grounded, "
                f"queries={result['search_queries']}"
            )
            return result  # success

        except Exception as e:
            error_msg = str(e).lower()
            if any(kw in error_msg for kw in ['401', '403', 'unauthorized', 'invalid', 'api_key']):
                logger.warning(f"[Gemini+Search] Auth error, removing key: {e}")
                _key_manager.mark_auth_failed(active_key)
                continue
            elif any(kw in error_msg for kw in ['429', 'quota', 'rate_limit', 'resource_exhausted']):
                logger.warning(f"[Gemini+Search] Rate limit, switching key: {e}")
                _key_manager.mark_exhausted(active_key)
                continue
            else:
                logger.warning(f"[Gemini+Search] Failed: {e}")
                return result

    return result



def gemini_enhanced_keyword_search(image_path, max_results=20):
    """
    Full Gemini-enhanced search pipeline.

    Two-stage approach:
    1. First try Gemini + Google Search Grounding (finds actual URLs)
    2. If that yields no URLs, fall back to keyword extraction mode

    Returns:
        tuple: (search_query: str, urls: list[str], analysis: dict)
            - search_query: The Gemini-generated search query
            - urls: Image/page URLs found via Google Search (may be empty)
            - analysis: The full analysis result (merged from both stages)
    """
    # Stage 1: Try Google Search Grounding first (finds real URLs)
    search_result = gemini_google_search_image(image_path, max_results)

    analysis = {
        'keywords': '',
        'description': search_result.get('description', ''),
        'document_type': '',
        'potential_sources': [],
        'google_search_urls': search_result.get('urls', []),
        'grounding_sources': search_result.get('grounding_sources', []),
        'search_queries': search_result.get('search_queries', []),
    }

    urls = search_result.get('urls', [])

    if urls:
        # Build a search query from grounding queries or description
        search_query = ''
        if search_result.get('search_queries'):
            search_query = search_result['search_queries'][0]
        elif search_result.get('description'):
            words = search_result['description'].split()[:8]
            search_query = ' '.join(words)

        analysis['keywords'] = search_query
        logger.info(
            f"[Gemini] Google Search found {len(urls)} URLs directly"
        )
        return search_query, urls, analysis

    # Stage 2: Fall back to keyword extraction (no live search)
    logger.info("[Gemini] Google Search returned no URLs, falling back to keyword extraction")
    desc_result = gemini_describe_image(image_path)

    # Merge analysis
    analysis['keywords'] = desc_result.get('keywords', '')
    analysis['description'] = (
        analysis['description'] or desc_result.get('description', '')
    )
    analysis['document_type'] = desc_result.get('document_type', '')
    analysis['potential_sources'] = desc_result.get('potential_sources', [])

    if not analysis['keywords']:
        logger.info("[Gemini] No keywords extracted, falling back")
        return '', [], analysis

    # Build an enhanced search query
    query_parts = []

    if analysis['document_type'] and analysis['document_type'].lower() not in (
        'photo', 'graphic', 'image'
    ):
        query_parts.append(analysis['document_type'])

    query_parts.append(analysis['keywords'])

    search_query = ' '.join(query_parts)

    # Trim to reasonable length
    if len(search_query) > 120:
        words = search_query.split()[:10]
        search_query = ' '.join(words)

    logger.info(f"[Gemini] Enhanced search query: '{search_query}'")

    return search_query, [], analysis

