"""
Google Cloud Vision API integration service.

Provides face detection, text detection (OCR), and web detection
using the Google Cloud Vision REST API.
"""

import base64
import json
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

VISION_API_BASE = "https://vision.googleapis.com/v1/images:annotate"


def _get_api_key():
    """Get the Google Cloud API key from settings."""
    key = settings.GOOGLE_CLOUD_API_KEY
    if not key or key == 'your-api-key-here':
        return None
    return key


def _encode_image(image_path):
    """Encode an image file as base64."""
    with open(image_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


def _call_vision_api(image_path, features):
    """
    Call the Google Cloud Vision API with the specified features.
    Returns the API response or None if the API key is not configured.
    """
    api_key = _get_api_key()
    if not api_key:
        logger.warning("Google Cloud Vision API key not configured")
        return None

    try:
        image_content = _encode_image(image_path)
    except FileNotFoundError:
        logger.error(f"Image file not found: {image_path}")
        return None

    payload = {
        "requests": [
            {
                "image": {"content": image_content},
                "features": features,
            }
        ]
    }

    try:
        response = requests.post(
            f"{VISION_API_BASE}?key={api_key}",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        if 'responses' in data and len(data['responses']) > 0:
            return data['responses'][0]
        return None
    except requests.RequestException as e:
        logger.error(f"Vision API request failed: {e}")
        return None


def detect_faces(image_path):
    """
    Detect faces in an image using Google Cloud Vision API.
    Returns list of face annotations or empty list.
    """
    response = _call_vision_api(image_path, [
        {"type": "FACE_DETECTION", "maxResults": 10}
    ])
    if response and 'faceAnnotations' in response:
        return response['faceAnnotations']
    return []


def detect_text(image_path):
    """
    Detect text in an image using Google Cloud Vision OCR.
    Returns the full detected text string or empty string.
    """
    response = _call_vision_api(image_path, [
        {"type": "TEXT_DETECTION", "maxResults": 10}
    ])
    if response and 'textAnnotations' in response:
        annotations = response['textAnnotations']
        if annotations:
            return annotations[0].get('description', '')
    return ''


def detect_web_matches(image_path):
    """
    Detect web matches for an image using Google Cloud Vision Web Detection.
    Returns structured web detection data.
    """
    response = _call_vision_api(image_path, [
        {"type": "WEB_DETECTION", "maxResults": 10}
    ])

    results = {
        'full_matching_images': [],
        'partial_matching_images': [],
        'pages_with_matching_images': [],
        'visually_similar_images': [],
        'web_entities': [],
    }

    if not response or 'webDetection' not in response:
        return results

    web = response['webDetection']

    for img in web.get('fullMatchingImages', []):
        results['full_matching_images'].append({
            'url': img.get('url', ''),
            'score': img.get('score', 0),
        })

    for img in web.get('partialMatchingImages', []):
        results['partial_matching_images'].append({
            'url': img.get('url', ''),
            'score': img.get('score', 0),
        })

    for page in web.get('pagesWithMatchingImages', []):
        results['pages_with_matching_images'].append({
            'url': page.get('url', ''),
            'page_title': page.get('pageTitle', ''),
            'score': page.get('score', 0),
        })

    for img in web.get('visuallySimilarImages', []):
        results['visually_similar_images'].append({
            'url': img.get('url', ''),
            'score': img.get('score', 0),
        })

    for entity in web.get('webEntities', []):
        results['web_entities'].append({
            'entity_id': entity.get('entityId', ''),
            'description': entity.get('description', ''),
            'score': entity.get('score', 0),
        })

    return results
