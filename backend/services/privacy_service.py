"""
Privacy filter service.

Analyzes images for personal/sensitive information:
- Face detection (via Vision API)
- Name detection (capitalized word patterns)
- Age detection (regex: number + 'tahun')
- Address detection (Indonesian address keywords)
- Phone number detection (Indonesian phone patterns)

If >= 3 categories are flagged, the search is blocked.
"""

import re
import logging
from django.conf import settings
from services.vision_service import detect_faces, detect_text

logger = logging.getLogger(__name__)

# Indonesian address keywords
ADDRESS_KEYWORDS = [
    'jl', 'jl.', 'jalan',
    'rt', 'rt.', 'rw', 'rw.',
    'no', 'no.',
    'kecamatan', 'kec', 'kec.',
    'kelurahan', 'kel', 'kel.',
    'kabupaten', 'kab', 'kab.',
    'kota', 'provinsi', 'prov',
    'desa', 'dusun',
    'gang', 'gg', 'gg.',
    'blok', 'gedung',
]

# Compile regex patterns
AGE_PATTERN = re.compile(r'\b(\d{1,3})\s*tahun\b', re.IGNORECASE)
PHONE_PATTERN = re.compile(r'(\+62\d{8,13}|08\d{8,12})')
NAME_PATTERN = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b')


def _detect_name_in_text(text):
    """Detect person names using capitalized word pattern matching."""
    if not text:
        return False
    matches = NAME_PATTERN.findall(text)
    # Filter out common non-name capitalized phrases
    common_non_names = {
        'Indonesia', 'Jakarta', 'Bandung', 'Surabaya',
        'Google', 'Facebook', 'Microsoft', 'Januari', 'Februari',
        'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus',
        'September', 'Oktober', 'November', 'Desember',
        'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu',
    }
    for match in matches:
        words = match.split()
        if not all(w in common_non_names for w in words):
            return True
    return False


def _detect_age_in_text(text):
    """Detect age mentions using regex (number + 'tahun')."""
    if not text:
        return False
    return bool(AGE_PATTERN.search(text))


def _detect_address_in_text(text):
    """Detect Indonesian address patterns using keyword matching."""
    if not text:
        return False
    text_lower = text.lower()
    found_keywords = sum(1 for kw in ADDRESS_KEYWORDS if kw in text_lower)
    # Require at least 2 address keywords to flag as address
    return found_keywords >= 2


def _detect_phone_in_text(text):
    """Detect Indonesian phone number patterns."""
    if not text:
        return False
    return bool(PHONE_PATTERN.search(text))


def analyze_privacy(image_path):
    """
    Perform complete privacy analysis on an image.

    Returns a dict with:
        - face_detected: bool
        - name_detected: bool
        - age_detected: bool
        - address_detected: bool
        - phone_detected: bool
        - total_flags: int
        - is_blocked: bool (True if total_flags >= PRIVACY_FLAG_THRESHOLD)
        - detected_text: str (raw OCR text for reference)
    """
    threshold = getattr(settings, 'PRIVACY_FLAG_THRESHOLD', 3)

    result = {
        'face_detected': False,
        'name_detected': False,
        'age_detected': False,
        'address_detected': False,
        'phone_detected': False,
        'total_flags': 0,
        'is_blocked': False,
        'detected_text': '',
    }

    # 1. Face detection
    try:
        faces = detect_faces(image_path)
        result['face_detected'] = len(faces) > 0
        if result['face_detected']:
            logger.info(f"Face detected in {image_path}: {len(faces)} face(s)")
    except Exception as e:
        logger.error(f"Face detection error: {e}")

    # 2. Text detection (OCR)
    detected_text = ''
    try:
        detected_text = detect_text(image_path)
        result['detected_text'] = detected_text
    except Exception as e:
        logger.error(f"Text detection error: {e}")

    # 3. Analyze text content for privacy flags
    if detected_text:
        result['name_detected'] = _detect_name_in_text(detected_text)
        result['age_detected'] = _detect_age_in_text(detected_text)
        result['address_detected'] = _detect_address_in_text(detected_text)
        result['phone_detected'] = _detect_phone_in_text(detected_text)

    # Count total flags
    flags = [
        result['face_detected'],
        result['name_detected'],
        result['age_detected'],
        result['address_detected'],
        result['phone_detected'],
    ]
    result['total_flags'] = sum(flags)
    result['is_blocked'] = result['total_flags'] >= threshold

    logger.info(
        f"Privacy analysis complete: {result['total_flags']} flags, "
        f"blocked={result['is_blocked']}"
    )

    return result
