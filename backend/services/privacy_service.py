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
_cv2 = None
_easyocr = None
_easyocr_reader = None
try:
    import cv2 as _cv2
    logger.info('OpenCV (cv2) available for local face detection fallback')
except ImportError:
    logger.info('OpenCV (cv2) not installed — local face detection unavailable')
try:
    import easyocr as _easyocr
    logger.info('easyocr available for local OCR fallback')
except ImportError:
    logger.info('easyocr not installed — local OCR unavailable')
ADDRESS_KEYWORDS = ['jl', 'jl.', 'jalan', 'rt', 'rt.', 'rw', 'rw.', 'rt/', 'rw/', 'no', 'no.', 'kecamatan', 'kec', 'kec.', 'kelurahan', 'kel', 'kel.', 'kabupaten', 'kab', 'kab.', 'kota', 'provinsi', 'prov', 'desa', 'dusun', 'gang', 'gg', 'gg.', 'blok', 'gedung', 'perumahan', 'perum', 'komplek', 'kompleks']
AGE_PATTERN = re.compile('\\b(\\d{1,3})\\s*(?:tahun|thn|th)\\b', re.IGNORECASE)
PHONE_PATTERN = re.compile('(\\+\\d{1,4}[\\s\\-]?(?:\\d[\\s\\-]?){7,14}|08[\\s\\-]?(?:\\d[\\s\\-]?){7,12})')
NAME_PATTERN = re.compile('\\b([A-Z][a-z]{1,15}(?:\\s+[A-Z][a-z]{1,15})+)\\b')
NIK_PATTERN = re.compile('\\b\\d[\\d\\sO]{14,20}\\b', re.IGNORECASE)
TTL_PATTERN = re.compile('(?:tempat|tgl|tanggal|lahir).{0,30}?\\d{1,2}[\\s\\-/. ,]+\\d{1,2}[\\s\\-/. ,]+\\d{2,4}', re.IGNORECASE)
COMMON_NON_NAMES = {'Indonesia', 'Jakarta', 'Bandung', 'Surabaya', 'Semarang', 'Yogyakarta', 'Medan', 'Makassar', 'Palembang', 'Tangerang', 'Depok', 'Bekasi', 'Bogor', 'Google', 'Facebook', 'Microsoft', 'Instagram', 'Twitter', 'Youtube', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu', 'Republik', 'Provinsi', 'Kabupaten', 'Kecamatan', 'Kelurahan', 'Negara', 'Kesatuan', 'Undang'}

class PrivacyService:

    @staticmethod
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
            gray_eq = _cv2.equalizeHist(gray)
            cascade_path = _cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            face_cascade = _cv2.CascadeClassifier(cascade_path)
            faces = face_cascade.detectMultiScale(gray_eq, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))
            if len(faces) == 0:
                faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(50, 50))
            result = [{'x': int(x), 'y': int(y), 'w': int(w), 'h': int(h)} for x, y, w, h in faces]
            logger.info(f'[OpenCV] Local face detection: {len(result)} face(s)')
            return result
        except Exception as e:
            logger.error(f'[OpenCV] Local face detection error: {e}')
            return []

    @staticmethod
    def _local_detect_text(image_path):
        """
    Extract text from image locally using easyocr.
    Returns the full detected text string or empty string.
    """
        global _easyocr_reader
        if _easyocr is None:
            return ''
        try:
            if _easyocr_reader is None:
                _easyocr_reader = _easyocr.Reader(['id', 'en'], gpu=False, verbose=False)
            results = _easyocr_reader.readtext(image_path, detail=0)
            text = ' '.join(results)
            text = text.strip()
            logger.info(f'[easyocr] Local OCR: {len(text)} chars extracted')
            return text
        except Exception as e:
            logger.error(f'[easyocr] Local OCR error: {e}')
            return ''

    @staticmethod
    def _detect_name_in_text(text):
        """Detect person names using indicator keywords to prevent false positives."""
        if not text:
            return False
        name_indicators = re.compile('\\b(?:nama|name|an\\.|a\\.n\\.?|narna|noma)\\b\\s*[:.\\-]?\\s*([A-Za-z\\s\\.]{3,40})', re.IGNORECASE)
        hama_indicator = re.compile('\\bhama\\b\\s*[:.\\-]?\\s*([A-Z\\s\\.]{3,40})(?![a-z])')
        if name_indicators.search(text) or hama_indicator.search(text):
            return True
        ktp_header = re.compile('(?:provinsi|paovinsi).{5,50}?(?:nik|kik|n1k)\\b', re.IGNORECASE)
        if ktp_header.search(text):
            return True
        return False

    @staticmethod
    def _detect_age_in_text(text):
        """Detect age mentions using regex (number + 'tahun'/'th'/'thn')."""
        if not text:
            return False
        if AGE_PATTERN.search(text):
            return True
        if TTL_PATTERN.search(text):
            return True
        return False

    @staticmethod
    def _detect_address_in_text(text):
        """Detect Indonesian address patterns using keyword matching."""
        if not text:
            return False
        address_pattern_strict = re.compile('\\b(jl|rt|rw|no|kec|kel|kab|prov|gg)\\b', re.IGNORECASE)
        address_pattern_loose = re.compile('\\b(jalan|kecamatan|kelurahan|kabupaten|kota|provinsi|paovinsi|desa|dusun|gang|blok|gedung|perumahan|perum|kompleks?)', re.IGNORECASE)
        matches = address_pattern_strict.findall(text) + address_pattern_loose.findall(text)
        unique_keywords = set([m.lower() for m in matches])
        if len(unique_keywords) >= 2:
            return True
        rt_rw_pattern = re.compile('\\brt\\s*\\.?\\s*\\d+\\s*/\\s*rw\\s*\\.?\\s*\\d+', re.IGNORECASE)
        if rt_rw_pattern.search(text):
            return True
        return False

    @staticmethod
    def _detect_phone_in_text(text):
        """Detect Indonesian phone number patterns."""
        if not text:
            return False
        if PHONE_PATTERN.search(text):
            return True
        if NIK_PATTERN.search(text):
            return True
        return False

    @staticmethod
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
        result = {'face_detected': False, 'name_detected': False, 'age_detected': False, 'address_detected': False, 'phone_detected': False, 'total_flags': 0, 'is_blocked': False, 'detected_text': ''}
        try:
            from services.vision_service import VisionService
            faces = VisionService.detect_faces(image_path)
            result['face_detected'] = len(faces) > 0
            if result['face_detected']:
                logger.info(f'[Vision API] Face detected: {len(faces)} face(s)')
        except Exception as e:
            logger.warning(f'Vision API face detection failed: {e}')
        if not result['face_detected']:
            local_faces = PrivacyService._local_detect_faces(image_path)
            result['face_detected'] = len(local_faces) > 0
        detected_text = ''
        try:
            from services.vision_service import VisionService
            detected_text = VisionService.detect_text(image_path)
            if detected_text:
                logger.info(f'[Vision API] Text detected: {len(detected_text)} chars')
        except Exception as e:
            logger.warning(f'Vision API text detection failed: {e}')
        if not detected_text:
            detected_text = PrivacyService._local_detect_text(image_path)
        result['detected_text'] = detected_text
        if detected_text:
            result['name_detected'] = PrivacyService._detect_name_in_text(detected_text)
            result['age_detected'] = PrivacyService._detect_age_in_text(detected_text)
            result['address_detected'] = PrivacyService._detect_address_in_text(detected_text)
            result['phone_detected'] = PrivacyService._detect_phone_in_text(detected_text)
        flags = [result['face_detected'], result['name_detected'], result['age_detected'], result['address_detected'], result['phone_detected']]
        result['total_flags'] = sum(flags)
        result['is_blocked'] = result['total_flags'] >= threshold
        logger.info(f"Privacy analysis complete: {result['total_flags']} flags, blocked={result['is_blocked']} | face={result['face_detected']}, name={result['name_detected']}, age={result['age_detected']}, addr={result['address_detected']}, phone={result['phone_detected']}")
        return result

    @staticmethod
    def blur_pii_regions(image_path, privacy_result=None):
        """
    Disabled masking: returns the original image path without modifications.
    
    Previously, this would create a blurred copy of the image to mask PII.
    Now, it simply returns the input path as requested by the user.
    """
        logger.info('[Masking] Censoring disabled, returning original image path')
        return image_path