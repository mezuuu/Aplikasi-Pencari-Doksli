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
import tempfile
from django.conf import settings
logger = logging.getLogger(__name__)
_cv2 = None
_easyocr = None
_easyocr_reader = None
_pytesseract = None
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
try:
    import pytesseract as _pytesseract
    logger.info('pytesseract available for local OCR fallback')
except ImportError:
    logger.info('pytesseract not installed - local OCR unavailable')
ADDRESS_KEYWORDS = ['jl', 'jl.', 'jalan', 'rt', 'rt.', 'rw', 'rw.', 'rt/', 'rw/', 'no', 'no.', 'kecamatan', 'kec', 'kec.', 'kelurahan', 'kel', 'kel.', 'kabupaten', 'kab', 'kab.', 'kota', 'provinsi', 'prov', 'desa', 'dusun', 'gang', 'gg', 'gg.', 'blok', 'gedung', 'perumahan', 'perum', 'komplek', 'kompleks']
AGE_PATTERN = re.compile('\\b(\\d{1,3})\\s*(?:tahun|thn|th)\\b', re.IGNORECASE)
PHONE_PATTERN = re.compile('(\\+\\d{1,4}[\\s\\-]?(?:\\d[\\s\\-]?){7,14}|08[\\s\\-]?(?:\\d[\\s\\-]?){7,12})')
NAME_PATTERN = re.compile('\\b([A-Z][a-z]{1,15}(?:\\s+[A-Z][a-z]{1,15})+)\\b')
NIK_PATTERN = re.compile('\\b\\d[\\d\\sO]{14,20}\\b', re.IGNORECASE)
TTL_PATTERN = re.compile('(?:tempat|tgl|tanggal|lahir).{0,30}?\\d{1,2}[\\s\\-/. ,]+\\d{1,2}[\\s\\-/. ,]+\\d{2,4}', re.IGNORECASE)
COMMON_NON_NAMES = {'Indonesia', 'Jakarta', 'Bandung', 'Surabaya', 'Semarang', 'Yogyakarta', 'Medan', 'Makassar', 'Palembang', 'Tangerang', 'Depok', 'Bekasi', 'Bogor', 'Google', 'Facebook', 'Microsoft', 'Instagram', 'Twitter', 'Youtube', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu', 'Republik', 'Provinsi', 'Kabupaten', 'Kecamatan', 'Kelurahan', 'Negara', 'Kesatuan', 'Undang'}

class PrivacyService:

    @staticmethod
    def get_capabilities():
        """Return detector availability for deployment diagnostics."""
        return {
            'opencv': _cv2 is not None,
            'opencv_haar_face': PrivacyService._has_haar_face_cascade(),
            'opencv_dnn_face': PrivacyService._has_dnn_face_model(),
            'easyocr': _easyocr is not None,
            'pytesseract': _pytesseract is not None,
        }

    @staticmethod
    def _has_dnn_face_model():
        model_dir = os.path.join(settings.BASE_DIR, 'models')
        proto_path = os.path.join(model_dir, 'deploy.prototxt')
        model_path = os.path.join(model_dir, 'res10_300x300_ssd_iter_140000.caffemodel')
        return os.path.exists(proto_path) and os.path.exists(model_path)

    @staticmethod
    def _has_haar_face_cascade():
        if _cv2 is None:
            return False
        cascade_path = os.path.join(_cv2.data.haarcascades, 'haarcascade_frontalface_default.xml')
        if not os.path.exists(cascade_path):
            return False
        cascade = _cv2.CascadeClassifier(cascade_path)
        return not cascade.empty()

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
            dnn_faces = PrivacyService._dnn_detect_faces(img)
            if dnn_faces:
                logger.info(f'[OpenCV DNN] Local face detection: {len(dnn_faces)} face(s)')
                return dnn_faces
            result = PrivacyService._haar_detect_faces(img)
            logger.info(f'[OpenCV] Local face detection: {len(result)} face(s)')
            return result
        except Exception as e:
            logger.error(f'[OpenCV] Local face detection error: {e}')
            return []

    @staticmethod
    def _haar_detect_faces(img):
        """Detect faces with Haar cascades across conservative image regions."""
        height, width = img.shape[:2]
        min_side = min(width, height)
        min_face = max(24, int(min_side * 0.035))
        max_face = int(min_side * 0.45)
        cascade_names = [
            'haarcascade_frontalface_default.xml',
            'haarcascade_frontalface_alt2.xml',
            'haarcascade_profileface.xml',
        ]
        cascades = []
        for cascade_name in cascade_names:
            cascade_path = os.path.join(_cv2.data.haarcascades, cascade_name)
            if not os.path.exists(cascade_path):
                logger.warning(f'[OpenCV] Haar cascade missing: {cascade_name}')
                continue
            cascade = _cv2.CascadeClassifier(cascade_path)
            if cascade.empty():
                logger.warning(f'[OpenCV] Haar cascade could not be loaded: {cascade_name}')
                continue
            cascades.append((cascade_name, cascade))

        if not cascades:
            return []

        regions = [
            ('full', img, 0, 0, 1.0),
            ('left', img[:int(height * 0.78), :int(width * 0.65)], 0, 0, 1.0),
            ('left_mid', img[int(height * 0.20):int(height * 0.82), :int(width * 0.65)], 0, int(height * 0.20), 1.0),
            ('center', img[int(height * 0.15):int(height * 0.80), int(width * 0.12):int(width * 0.88)], int(width * 0.12), int(height * 0.15), 1.0),
        ]
        attempts = [
            (1.0, 1.08, 4),
            (1.0, 1.05, 3),
            (1.0, 1.03, 3),
            (1.5, 1.08, 3),
            (1.5, 1.05, 3),
        ]
        faces = []
        for region_name, region, offset_x, offset_y, _ in regions:
            if region.size == 0:
                continue
            for resize_scale, scale_factor, min_neighbors in attempts:
                if resize_scale != 1.0:
                    work = _cv2.resize(region, None, fx=resize_scale, fy=resize_scale, interpolation=_cv2.INTER_CUBIC)
                else:
                    work = region
                gray = _cv2.cvtColor(work, _cv2.COLOR_BGR2GRAY)
                gray_variants = (gray, _cv2.equalizeHist(gray))
                scaled_min_face = max(20, int(min_face * resize_scale))
                scaled_max_face = max(scaled_min_face + 1, int(max_face * resize_scale))
                for gray_img in gray_variants:
                    for cascade_name, cascade in cascades:
                        detected = cascade.detectMultiScale(
                            gray_img,
                            scaleFactor=scale_factor,
                            minNeighbors=min_neighbors,
                            minSize=(scaled_min_face, scaled_min_face),
                            maxSize=(scaled_max_face, scaled_max_face),
                        )
                        for x, y, w, h in detected:
                            aspect = w / float(h or 1)
                            if aspect < 0.65 or aspect > 1.45:
                                continue
                            face = {
                                'x': int(offset_x + x / resize_scale),
                                'y': int(offset_y + y / resize_scale),
                                'w': int(w / resize_scale),
                                'h': int(h / resize_scale),
                                'detector': cascade_name.replace('haarcascade_', '').replace('.xml', ''),
                                'region': region_name,
                            }
                            faces.append(face)
                    if faces:
                        return PrivacyService._dedupe_faces(faces)
        return PrivacyService._dedupe_faces(faces)

    @staticmethod
    def _dedupe_faces(faces):
        """Remove strongly overlapping face boxes."""
        deduped = []
        for face in sorted(faces, key=lambda item: item['w'] * item['h'], reverse=True):
            if not any(PrivacyService._face_iou(face, existing) > 0.35 for existing in deduped):
                deduped.append(face)
        return deduped

    @staticmethod
    def _face_iou(a, b):
        ax1, ay1, ax2, ay2 = a['x'], a['y'], a['x'] + a['w'], a['y'] + a['h']
        bx1, by1, bx2, by2 = b['x'], b['y'], b['x'] + b['w'], b['y'] + b['h']
        inter_x1, inter_y1 = max(ax1, bx1), max(ay1, by1)
        inter_x2, inter_y2 = min(ax2, bx2), min(ay2, by2)
        inter_w, inter_h = max(0, inter_x2 - inter_x1), max(0, inter_y2 - inter_y1)
        intersection = inter_w * inter_h
        if intersection == 0:
            return 0.0
        area_a = max(1, a['w'] * a['h'])
        area_b = max(1, b['w'] * b['h'])
        return intersection / float(area_a + area_b - intersection)

    @staticmethod
    def _dnn_detect_faces(img):
        """Detect faces using OpenCV's SSD face detector if model files exist."""
        if _cv2 is None or not PrivacyService._has_dnn_face_model():
            return []
        try:
            model_dir = os.path.join(settings.BASE_DIR, 'models')
            proto_path = os.path.join(model_dir, 'deploy.prototxt')
            model_path = os.path.join(model_dir, 'res10_300x300_ssd_iter_140000.caffemodel')
            net = _cv2.dnn.readNetFromCaffe(proto_path, model_path)
            height, width = img.shape[:2]
            blob = _cv2.dnn.blobFromImage(_cv2.resize(img, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0))
            net.setInput(blob)
            detections = net.forward()
            faces = []
            for i in range(detections.shape[2]):
                confidence = float(detections[0, 0, i, 2])
                if confidence < 0.35:
                    continue
                box = detections[0, 0, i, 3:7] * [width, height, width, height]
                x1, y1, x2, y2 = box.astype('int')
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(width, x2), min(height, y2)
                if x2 <= x1 or y2 <= y1:
                    continue
                face_w = x2 - x1
                face_h = y2 - y1
                if face_w < 18 or face_h < 18:
                    continue
                faces.append({'x': int(x1), 'y': int(y1), 'w': int(face_w), 'h': int(face_h), 'confidence': confidence})
            return faces
        except Exception as e:
            logger.warning(f'[OpenCV DNN] Face detection failed: {e}')
            return []

    @staticmethod
    def _local_detect_text(image_path):
        """
    Extract text from image locally using easyocr.
    Returns the full detected text string or empty string.
    """
        global _easyocr_reader
        if _easyocr is not None:
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
        if _pytesseract is None:
            return ''
        try:
            texts = PrivacyService._tesseract_detect_text_variants(image_path)
            text = PrivacyService._merge_ocr_texts(texts)
            logger.info(f'[pytesseract] Local OCR: {len(text)} chars extracted from {len(texts)} variant(s)')
            return text
        except Exception as e:
            logger.error(f'[pytesseract] Local OCR error: {e}')
            return ''

    @staticmethod
    def _merge_ocr_texts(texts):
        """Merge OCR outputs while preserving useful repeated context."""
        seen = set()
        lines = []
        for text in texts:
            for line in str(text or '').splitlines():
                cleaned = re.sub(r'\s+', ' ', line).strip()
                key = cleaned.lower()
                if cleaned and key not in seen:
                    seen.add(key)
                    lines.append(cleaned)
        return '\n'.join(lines)

    @staticmethod
    def _tesseract_detect_text_variants(image_path):
        """
    Run Tesseract over multiple preprocessed variants.

    Poster/news-card images often use bright text over a dark overlay. A single
    OCR pass misses those, so we crop likely text bands, upscale, threshold,
    and invert before OCR.
    """
        from PIL import Image, ImageOps, ImageFilter

        image = Image.open(image_path).convert('RGB')
        width, height = image.size
        crops = [
            image,
            image.crop((0, int(height * 0.45), width, height)),
            image.crop((0, int(height * 0.30), width, height)),
        ]
        variants = []
        for crop in crops:
            variants.append(crop)
            scale = 2 if max(crop.size) >= 900 else 3
            upscaled = crop.resize((crop.width * scale, crop.height * scale), Image.LANCZOS)
            gray = ImageOps.grayscale(upscaled)
            gray = ImageOps.autocontrast(gray).filter(ImageFilter.SHARPEN)
            variants.append(gray)
            variants.append(gray.point(lambda p: 255 if p > 150 else 0))
            variants.append(ImageOps.invert(gray).point(lambda p: 255 if p > 150 else 0))

        texts = []
        configs = (
            '--psm 6',
            '--psm 11',
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            for idx, variant in enumerate(variants):
                variant_path = os.path.join(tmpdir, f'ocr_{idx}.png')
                variant.save(variant_path)
                for config in configs:
                    try:
                        text = _pytesseract.image_to_string(variant_path, lang='ind+eng', config=config)
                        if text and text.strip():
                            texts.append(text.strip())
                    except Exception as e:
                        logger.debug(f'[pytesseract] Variant OCR failed: {e}')
        return texts

    @staticmethod
    def _detect_name_in_text(text):
        """Detect person names using indicator keywords to prevent false positives."""
        if not text:
            return False
        normalized = PrivacyService._normalize_ocr_text(text)
        name_indicators = re.compile('\\b(?:nama|name|an\\.|a\\.n\\.?|narna|noma)\\b\\s*[:.\\-]?\\s*([A-Za-z\\s\\.]{3,40})', re.IGNORECASE)
        hama_indicator = re.compile('\\bhama\\b\\s*[:.\\-]?\\s*([A-Z\\s\\.]{3,40})(?![a-z])')
        if name_indicators.search(normalized) or hama_indicator.search(normalized):
            return True
        ktp_header = re.compile('(?:provinsi|paovinsi).{5,50}?(?:nik|kik|n1k)\\b', re.IGNORECASE)
        if ktp_header.search(normalized):
            return True
        return False

    @staticmethod
    def _normalize_ocr_text(text):
        """Normalize common OCR confusions before applying privacy regexes."""
        text = str(text or '')
        replacements = {
            '|': 'I',
            '0': 'O',
            '1': 'I',
            '3': 'E',
            '4': 'A',
            '5': 'S',
            '7': 'T',
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

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
        """Detect detailed Indonesian address patterns using component categories."""
        if not text:
            return False
        normalized = PrivacyService._normalize_ocr_text(text).lower()
        components = set()
        component_patterns = {
            'street': r'\b(?:jl\.?|jalan|gang|gg\.?|blok|kompleks?|komplek|perumahan|perum)\b',
            'neighborhood': r'\b(?:rt\.?\s*\d+|rw\.?\s*\d+|rt\s*/\s*rw|rt\s*\d+\s*/\s*rw\s*\d+)\b',
            'village': r'\b(?:desa|kelurahan|kel\.?)\b',
            'district': r'\b(?:kecamatan|kec\.?)\b',
            'regency_city': r'\b(?:kabupaten|kab\.?|kota)\b',
            'province': r'\b(?:provinsi|paovinsi|prov\.?)\b',
        }
        for component, pattern in component_patterns.items():
            if re.search(pattern, normalized, re.IGNORECASE):
                components.add(component)
        if len(components) >= 2:
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
