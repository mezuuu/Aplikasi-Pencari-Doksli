"""
Privacy filter service.

Analyzes images for personal/sensitive information:
- Face detection (via Vision API → fallback to OpenCV Haar Cascade)
- Name detection (capitalized word patterns)
- Age detection (regex: number + 'tahun')
- Address detection (Indonesian address keywords)
- Phone number detection (Indonesian phone patterns)

If >= 3 categories are flagged, the search is blocked.
"""

import re
import logging
import os
from django.conf import settings

logger = logging.getLogger(__name__)

# ─── Try import optional local detection libraries ───
_cv2 = None
_easyocr = None
_easyocr_reader = None

try:
    import cv2 as _cv2
    logger.info("OpenCV (cv2) available for local face detection fallback")
except ImportError:
    logger.info("OpenCV (cv2) not installed — local face detection unavailable")

try:
    import easyocr as _easyocr
    logger.info("easyocr available for local OCR fallback")
except ImportError:
    logger.info("easyocr not installed — local OCR unavailable")


# ─── Indonesian address keywords ───
ADDRESS_KEYWORDS = [
    'jl', 'jl.', 'jalan',
    'rt', 'rt.', 'rw', 'rw.',
    'rt/', 'rw/',
    'no', 'no.',
    'kecamatan', 'kec', 'kec.',
    'kelurahan', 'kel', 'kel.',
    'kabupaten', 'kab', 'kab.',
    'kota', 'provinsi', 'prov',
    'desa', 'dusun',
    'gang', 'gg', 'gg.',
    'blok', 'gedung',
    'perumahan', 'perum',
    'komplek', 'kompleks',
]

# ─── Compiled regex patterns ───
AGE_PATTERN = re.compile(
    r'\b(\d{1,3})\s*(?:tahun|thn|th)\b', re.IGNORECASE
)
PHONE_PATTERN = re.compile(
    r'(\+\d{1,4}[\s\-]?(?:\d[\s\-]?){7,14}' # International format (e.g. +1, +44, +62)
    r'|08[\s\-]?(?:\d[\s\-]?){7,12})'        # Local Indonesian starting with 08
)
NAME_PATTERN = re.compile(r'\b([A-Z][a-z]{1,15}(?:\s+[A-Z][a-z]{1,15})+)\b')

# Additional patterns for NIK (KTP number) and TTL (Tempat Tanggal Lahir)
# Resistant to OCR noise (e.g. spaces inside numbers or typos in 'Tempat/Tgl Lahir')
NIK_PATTERN = re.compile(r'\b\d[\d\sO]{14,20}\b', re.IGNORECASE)
TTL_PATTERN = re.compile(
    r'(?:tempat|tgl|tanggal|lahir).{0,30}?\d{1,2}[\s\-/. ,]+\d{1,2}[\s\-/. ,]+\d{2,4}',
    re.IGNORECASE
)


# ══════════════════════════════════════════════════════════════════
#  Local Fallback Detection Methods
# ══════════════════════════════════════════════════════════════════

def _local_detect_faces(image_path):
    """
    Detect faces locally using OpenCV Haar Cascade classifier.
    Returns list of face bounding boxes (or empty list).
    """
    if _cv2 is None:
        return []

    try:
        img = _cv2.imread(image_path)
        if img is None:
            return []

        gray = _cv2.cvtColor(img, _cv2.COLOR_BGR2GRAY)

        # Apply histogram equalization to improve contrast for low-quality images
        gray_eq = _cv2.equalizeHist(gray)

        # Use the frontal face Haar cascade bundled with OpenCV
        cascade_path = _cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        face_cascade = _cv2.CascadeClassifier(cascade_path)

        # Try with equalized image first (handles low-contrast screenshots/photos)
        faces = face_cascade.detectMultiScale(
            gray_eq,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(50, 50),
        )

        # Fallback to raw grayscale if equalized found nothing
        if len(faces) == 0:
            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=3, #sensitivity face detect (lower=more sensitive, higher=less sensitive)
                minSize=(50, 50),
            )

        result = [{'x': int(x), 'y': int(y), 'w': int(w), 'h': int(h)}
                  for (x, y, w, h) in faces]
        logger.info(f"[OpenCV] Local face detection: {len(result)} face(s)")
        return result

    except Exception as e:
        logger.error(f"[OpenCV] Local face detection error: {e}")
        return []


def _local_detect_text(image_path):
    """
    Extract text from image locally using easyocr.
    Returns the full detected text string or empty string.
    """
    global _easyocr_reader

    if _easyocr is None:
        return ''

    try:
        # Initialize reader once
        if _easyocr_reader is None:
            _easyocr_reader = _easyocr.Reader(['id', 'en'], gpu=False, verbose=False)

        results = _easyocr_reader.readtext(image_path, detail=0)
        text = ' '.join(results)

        text = text.strip()
        logger.info(f"[easyocr] Local OCR: {len(text)} chars extracted")
        return text

    except Exception as e:
        logger.error(f"[easyocr] Local OCR error: {e}")
        return ''


# ══════════════════════════════════════════════════════════════════
#  Text Analysis Functions
# ══════════════════════════════════════════════════════════════════

# Common non-name capitalized phrases to exclude
COMMON_NON_NAMES = {
    'Indonesia', 'Jakarta', 'Bandung', 'Surabaya', 'Semarang', 'Yogyakarta',
    'Medan', 'Makassar', 'Palembang', 'Tangerang', 'Depok', 'Bekasi', 'Bogor',
    'Google', 'Facebook', 'Microsoft', 'Instagram', 'Twitter', 'Youtube',
    'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
    'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember',
    'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu',
    'Republik', 'Provinsi', 'Kabupaten', 'Kecamatan', 'Kelurahan',
    'Negara', 'Kesatuan', 'Undang',
}


def _detect_name_in_text(text):
    """Detect person names using indicator keywords to prevent false positives."""
    if not text:
        return False

    # Check for Indonesian name indicators near words
    # Tolerates OCR typos like 'Narna', 'Noma'
    name_indicators = re.compile(
        r'\b(?:nama|name|an\.|a\.n\.?|narna|noma)\b\s*[:.\-]?\s*([A-Za-z\s\.]{3,40})',
        re.IGNORECASE
    )
    
    # Special case for 'hama' (common OCR typo for 'Nama' on KTP).
    # To prevent false positives in agriculture news (e.g., "Hama Tikus"),
    # we ONLY accept it if the following text is strictly ALL CAPS (like KTP names).
    hama_indicator = re.compile(r'\bhama\b\s*[:.\-]?\s*([A-Z\s\.]{3,40})(?![a-z])')
    
    if name_indicators.search(text) or hama_indicator.search(text):
        return True

    # Fallback for blurry KTPs:
    # If the image is so blurry that "Nama" is completely destroyed (e.g., KTP),
    # but we can clearly see the KTP header structure (Provinsi ... NIK/KIK),
    # we logically infer that the document contains a Name.
    ktp_header = re.compile(r'(?:provinsi|paovinsi).{5,50}?(?:nik|kik|n1k)\b', re.IGNORECASE)
    if ktp_header.search(text):
        return True

    return False


def _detect_age_in_text(text):
    """Detect age mentions using regex (number + 'tahun'/'th'/'thn')."""
    if not text:
        return False
    if AGE_PATTERN.search(text):
        return True
    # Also check for TTL (Tempat Tanggal Lahir) pattern
    if TTL_PATTERN.search(text):
        return True
    return False


def _detect_address_in_text(text):
    """Detect Indonesian address patterns using keyword matching."""
    if not text:
        return False

    # Use word boundary \b to prevent false positives like 'kel' inside 'sekelompok'
    # or 'rt' inside 'kertas'.
    # Use strict word boundaries \b for short abbreviations to prevent false positives
    # like 'kel' inside 'sekelompok' or 'rt' inside 'kertas'.
    address_pattern_strict = re.compile(
        r'\b(jl|rt|rw|no|kec|kel|kab|prov|gg)\b',
        re.IGNORECASE
    )
    
    # Use looser boundaries for long words to handle OCR mushing (e.g., 'KOTABOGOR')
    # and tolerate common OCR typos (e.g., 'paovinsi').
    address_pattern_loose = re.compile(
        r'\b(jalan|kecamatan|kelurahan|kabupaten|kota|provinsi|paovinsi|desa|dusun|gang|blok|gedung|perumahan|perum|kompleks?)',
        re.IGNORECASE
    )
    
    matches = address_pattern_strict.findall(text) + address_pattern_loose.findall(text)
    unique_keywords = set([m.lower() for m in matches])
    
    # Require at least 2 unique address keywords to flag as address
    if len(unique_keywords) >= 2:
        return True

    # Also check for RT/RW pattern like "RT 01/RW 02" or "RT.001/RW.002"
    rt_rw_pattern = re.compile(r'\brt\s*\.?\s*\d+\s*/\s*rw\s*\.?\s*\d+', re.IGNORECASE)
    if rt_rw_pattern.search(text):
        return True

    return False


def _detect_phone_in_text(text):
    """Detect Indonesian phone number patterns."""
    if not text:
        return False

    if PHONE_PATTERN.search(text):
        return True

    # Also detect NIK (16-digit Indonesian ID number)
    if NIK_PATTERN.search(text):
        return True

    return False


# ══════════════════════════════════════════════════════════════════
#  Main Privacy Analysis Entry Point
# ══════════════════════════════════════════════════════════════════

def analyze_privacy(image_path):
    """
    Perform complete privacy analysis on an image.

    Detection chain:
    1. Face: Google Vision API → OpenCV Haar Cascade fallback
    2. Text: Google Vision OCR → pytesseract fallback
    3. Analyze extracted text for name, age, address, phone

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

    # ─── 1. Face detection (Vision API → OpenCV fallback) ───
    try:
        from services.vision_service import detect_faces
        faces = detect_faces(image_path)
        result['face_detected'] = len(faces) > 0
        if result['face_detected']:
            logger.info(f"[Vision API] Face detected: {len(faces)} face(s)")
    except Exception as e:
        logger.warning(f"Vision API face detection failed: {e}")

    # Fallback to local OpenCV if Vision API found nothing or errored
    if not result['face_detected']:
        local_faces = _local_detect_faces(image_path)
        result['face_detected'] = len(local_faces) > 0

    # ─── 2. Text detection / OCR (Vision API → easyocr fallback) ───
    detected_text = ''
    try:
        from services.vision_service import detect_text
        detected_text = detect_text(image_path)
        if detected_text:
            logger.info(f"[Vision API] Text detected: {len(detected_text)} chars")
    except Exception as e:
        logger.warning(f"Vision API text detection failed: {e}")

    # Fallback to local easyocr if Vision API returned nothing
    if not detected_text:
        detected_text = _local_detect_text(image_path)

    result['detected_text'] = detected_text

    # ─── 3. Analyze text content for privacy flags ───
    if detected_text:
        result['name_detected'] = _detect_name_in_text(detected_text)
        result['age_detected'] = _detect_age_in_text(detected_text)
        result['address_detected'] = _detect_address_in_text(detected_text)
        result['phone_detected'] = _detect_phone_in_text(detected_text)

    # ─── Count total flags ───
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
        f"blocked={result['is_blocked']} | "
        f"face={result['face_detected']}, name={result['name_detected']}, "
        f"age={result['age_detected']}, addr={result['address_detected']}, "
        f"phone={result['phone_detected']}"
    )

    return result


# ══════════════════════════════════════════════════════════════════
#  Privacy Masking (Blur PII Regions)
# ══════════════════════════════════════════════════════════════════

def blur_pii_regions(image_path, privacy_result=None):
    """
    Disabled masking: returns the original image path without modifications.
    
    Previously, this would create a blurred copy of the image to mask PII.
    Now, it simply returns the input path as requested by the user.
    """
    logger.info("[Masking] Censoring disabled, returning original image path")
    return image_path

