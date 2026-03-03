"""
DRF Serializers for the Image Detection API.
"""

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
        return _image_path_to_url(obj.image_path)


class OriginalDocumentListSerializer(serializers.ModelSerializer):
    """Lighter serializer for list views (without embedding vector)."""
    label_count = serializers.IntegerField(source='labels.count', read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = OriginalDocument
        fields = ['id', 'image_path', 'image_url', 'file_hash', 'created_at', 'label_count']

    def get_image_url(self, obj):
        return _image_path_to_url(obj.image_path)


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

    class Meta:
        model = SearchResult
        fields = [
            'id', 'source_type', 'matched_document',
            'external_url', 'similarity_score', 'created_at',
        ]


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
