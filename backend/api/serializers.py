"""
DRF Serializers for the Image Detection API.
"""

import base64
import mimetypes
import os
from django.conf import settings
from rest_framework import serializers
from .models import (
    OriginalDocument,
    DocumentLabel,
    SearchQuery,
    PrivacyAnalysis,
    SearchResult,
)


def _image_path_to_url(image_path):
    """Convert an absolute or relative image path to a media URL."""
    if not image_path:
        return None
    # If it's already a relative path (e.g., 'originals/abc.jpg')
    media_root = str(settings.MEDIA_ROOT)
    path_str = str(image_path)
    if path_str.startswith(media_root):
        # Absolute path — strip media root to get relative
        relative = os.path.relpath(path_str, media_root)
    else:
        relative = path_str
    # Convert backslashes to forward slashes for URL
    relative = relative.replace('\\', '/')
    return f"{settings.MEDIA_URL}{relative}"


def _image_file_to_data_url(image_path):
    if not image_path:
        return None
    path_str = str(image_path)
    if not os.path.exists(path_str):
        return None
    mime_type, _ = mimetypes.guess_type(path_str)
    if not mime_type or not mime_type.startswith('image/'):
        mime_type = 'image/jpeg'
    with open(path_str, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode('ascii')
    return f"data:{mime_type};base64,{image_data}"


def _document_image_url(obj):
    if not obj:
        return None

    image_data = getattr(obj, 'image_data', None)
    if image_data:
        mime_type = getattr(obj, 'image_mime_type', 'image/jpeg') or 'image/jpeg'
        return f"data:{mime_type};base64,{image_data}"

    image_path = getattr(obj, 'image_path', None)
    if image_path:
        path_str = str(image_path)
        if os.path.exists(path_str):
            data_url = _image_file_to_data_url(path_str)
            if data_url:
                return data_url

    return _image_path_to_url(image_path)


class DocumentLabelSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentLabel
        fields = ['id', 'label_type', 'label_value', 'confidence_score']


class OriginalDocumentSerializer(serializers.ModelSerializer):
    labels = DocumentLabelSerializer(many=True, read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = OriginalDocument
        fields = ['id', 'image_path', 'image_url', 'file_hash', 'created_at', 'labels']

    def get_image_url(self, obj):
        return _document_image_url(obj)


class OriginalDocumentListSerializer(serializers.ModelSerializer):
    """Lighter serializer for list views (without embedding vector)."""
    label_count = serializers.IntegerField(source='labels.count', read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = OriginalDocument
        fields = ['id', 'image_path', 'image_url', 'file_hash', 'created_at', 'label_count']

    def get_image_url(self, obj):
        return _document_image_url(obj)


class PrivacyAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrivacyAnalysis
        fields = [
            'id', 'face_detected', 'name_detected', 'age_detected',
            'address_detected', 'phone_detected', 'total_flags',
            'is_blocked', 'analyzed_at',
        ]


class SearchResultSerializer(serializers.ModelSerializer):
    matched_document = OriginalDocumentListSerializer(read_only=True)
    matched_image_url = serializers.SerializerMethodField()

    class Meta:
        model = SearchResult
        fields = [
            'id', 'source_type', 'matched_document',
            'matched_image_url', 'external_url',
            'similarity_score', 'created_at',
        ]

    def get_matched_image_url(self, obj):
        """
        Return a displayable image URL for any result type:
        - Local results: use matched_document.image_path
        - Web results: use local matched_image_path OR external_url (direct link)
        """
        # Priority 1: local matched document
        if obj.matched_document:
            return _document_image_url(obj.matched_document)
        
        # Priority 2: web candidate stored locally
        if obj.matched_image_path:
            data_url = _image_file_to_data_url(obj.matched_image_path)
            if data_url:
                return data_url
            return _image_path_to_url(obj.matched_image_path)
        
        # Priority 3: external direct URL (for non-permanent storage)
        if obj.external_url:
            return obj.external_url
            
        return None


class SearchQuerySerializer(serializers.ModelSerializer):
    privacy_analysis = PrivacyAnalysisSerializer(read_only=True)
    results = SearchResultSerializer(many=True, read_only=True)
    query_image_url = serializers.SerializerMethodField()

    class Meta:
        model = SearchQuery
        fields = [
            'id', 'query_image_path', 'query_image_url', 'query_hash',
            'search_source', 'created_at', 'privacy_analysis', 'results',
        ]

    def get_query_image_url(self, obj):
        return _image_path_to_url(obj.query_image_path)


class SearchQueryListSerializer(serializers.ModelSerializer):
    """Lighter serializer for list views."""
    is_blocked = serializers.BooleanField(
        source='privacy_analysis.is_blocked',
        read_only=True,
        default=False,
    )
    result_count = serializers.IntegerField(
        source='results.count',
        read_only=True,
    )

    class Meta:
        model = SearchQuery
        fields = [
            'id', 'query_hash', 'search_source',
            'created_at', 'is_blocked', 'result_count',
        ]


class ImageUploadSerializer(serializers.Serializer):
    """Serializer for image upload endpoints."""
    image = serializers.ImageField(required=True)
