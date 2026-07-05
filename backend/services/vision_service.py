"""
Google Cloud Vision API integration service.

Provides face detection, text detection (OCR), and web detection.

Authentication priority:
1. Service Account JSON (via GOOGLE_APPLICATION_CREDENTIALS env var)
2. Fallback to REST API with API Key (GOOGLE_CLOUD_API_KEY)
"""
import base64
import json
import logging
import os
import requests
from django.conf import settings
logger = logging.getLogger(__name__)
_vision_client = None
try:
    from google.cloud import vision
    creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '')
    if creds_path and os.path.isfile(creds_path):
        _vision_client = vision.ImageAnnotatorClient()
        logger.info(f'Google Cloud Vision client initialized with Service Account: {creds_path}')
    else:
        logger.warning('GOOGLE_APPLICATION_CREDENTIALS not set or file not found. Will fall back to REST API with API key.')
except ImportError:
    logger.warning('google-cloud-vision package not installed. Will fall back to REST API with API key.')
except Exception as e:
    logger.warning(f'Failed to init Vision client: {e}. Falling back to REST API.')
VISION_API_BASE = 'https://vision.googleapis.com/v1/images:annotate'

class VisionService:

    @staticmethod
    def _client_detect_faces(image_path):
        """Detect faces using the official google-cloud-vision client."""
        with open(image_path, 'rb') as f:
            content = f.read()
        image = vision.Image(content=content)
        response = _vision_client.face_detection(image=image)
        if response.error.message:
            raise Exception(response.error.message)
        return response.face_annotations

    @staticmethod
    def _client_detect_text(image_path):
        """Detect text (OCR) using the official google-cloud-vision client."""
        with open(image_path, 'rb') as f:
            content = f.read()
        image = vision.Image(content=content)
        response = _vision_client.text_detection(image=image)
        if response.error.message:
            raise Exception(response.error.message)
        texts = response.text_annotations
        if texts:
            return texts[0].description
        return ''

    @staticmethod
    def _client_detect_web(image_path):
        """Detect web matches using the official google-cloud-vision client."""
        with open(image_path, 'rb') as f:
            content = f.read()
        image = vision.Image(content=content)
        response = _vision_client.web_detection(image=image)
        if response.error.message:
            raise Exception(response.error.message)
        return response.web_detection

    @staticmethod
    def _get_api_key():
        """Get the Google Cloud API key from settings."""
        key = settings.GOOGLE_CLOUD_API_KEY
        if not key or key == 'your-api-key-here':
            return None
        return key

    @staticmethod
    def _encode_image(image_path):
        """Encode an image file as base64."""
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')

    @staticmethod
    def _call_vision_api(image_path, features):
        """
    Call the Google Cloud Vision REST API with the specified features.
    Returns the API response or None if the API key is not configured.
    """
        api_key = VisionService._get_api_key()
        if not api_key:
            logger.warning('Google Cloud Vision API key not configured')
            return None
        try:
            image_content = VisionService._encode_image(image_path)
        except FileNotFoundError:
            logger.error(f'Image file not found: {image_path}')
            return None
        payload = {'requests': [{'image': {'content': image_content}, 'features': features}]}
        try:
            response = requests.post(f'{VISION_API_BASE}?key={api_key}', json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            if 'responses' in data and len(data['responses']) > 0:
                return data['responses'][0]
            return None
        except requests.RequestException as e:
            logger.error(f'Vision API request failed: {e}')
            return None

    @staticmethod
    def detect_faces(image_path):
        """
    Detect faces in an image using Google Cloud Vision API.
    Returns list of face annotations or empty list.
    """
        if _vision_client:
            try:
                annotations = VisionService._client_detect_faces(image_path)
                logger.info(f'[ServiceAccount] Face detection: {len(annotations)} face(s)')
                return annotations
            except Exception as e:
                logger.error(f'[ServiceAccount] Face detection failed: {e}')
        response = VisionService._call_vision_api(image_path, [{'type': 'FACE_DETECTION', 'maxResults': 10}])
        if response and 'faceAnnotations' in response:
            return response['faceAnnotations']
        return []

    @staticmethod
    def detect_text(image_path):
        """
    Detect text in an image using Google Cloud Vision OCR.
    Returns the full detected text string or empty string.
    """
        if _vision_client:
            try:
                text = VisionService._client_detect_text(image_path)
                logger.info(f'[ServiceAccount] Text detection: {len(text)} chars')
                return text
            except Exception as e:
                logger.error(f'[ServiceAccount] Text detection failed: {e}')
        response = VisionService._call_vision_api(image_path, [{'type': 'TEXT_DETECTION', 'maxResults': 10}])
        if response and 'textAnnotations' in response:
            annotations = response['textAnnotations']
            if annotations:
                return annotations[0].get('description', '')
        return ''

    @staticmethod
    def detect_web_matches(image_path):
        """
    Detect web matches for an image using Google Cloud Vision Web Detection.
    Returns structured web detection data.
    """
        results = {'full_matching_images': [], 'partial_matching_images': [], 'pages_with_matching_images': [], 'visually_similar_images': [], 'web_entities': []}
        if _vision_client:
            try:
                web = VisionService._client_detect_web(image_path)
                if web:
                    for img in web.full_matching_images:
                        results['full_matching_images'].append({'url': img.url, 'score': img.score})
                    for img in web.partial_matching_images:
                        results['partial_matching_images'].append({'url': img.url, 'score': img.score})
                    for page in web.pages_with_matching_images:
                        results['pages_with_matching_images'].append({'url': page.url, 'page_title': page.page_title, 'score': page.score})
                    for img in web.visually_similar_images:
                        results['visually_similar_images'].append({'url': img.url, 'score': img.score})
                    for entity in web.web_entities:
                        results['web_entities'].append({'entity_id': entity.entity_id, 'description': entity.description, 'score': entity.score})
                    total = sum((len(v) for v in results.values()))
                    logger.info(f'[ServiceAccount] Web detection: {total} results')
                    return results
            except Exception as e:
                logger.error(f'[ServiceAccount] Web detection failed: {e}')
        response = VisionService._call_vision_api(image_path, [{'type': 'WEB_DETECTION', 'maxResults': 10}])
        if not response or 'webDetection' not in response:
            return results
        web = response['webDetection']
        for img in web.get('fullMatchingImages', []):
            results['full_matching_images'].append({'url': img.get('url', ''), 'score': img.get('score', 0)})
        for img in web.get('partialMatchingImages', []):
            results['partial_matching_images'].append({'url': img.get('url', ''), 'score': img.get('score', 0)})
        for page in web.get('pagesWithMatchingImages', []):
            results['pages_with_matching_images'].append({'url': page.get('url', ''), 'page_title': page.get('pageTitle', ''), 'score': page.get('score', 0)})
        for img in web.get('visuallySimilarImages', []):
            results['visually_similar_images'].append({'url': img.get('url', ''), 'score': img.get('score', 0)})
        for entity in web.get('webEntities', []):
            results['web_entities'].append({'entity_id': entity.get('entityId', ''), 'description': entity.get('description', ''), 'score': entity.get('score', 0)})
        return results