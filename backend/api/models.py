"""
Database models for the Image Manipulation Detection System.

5 models with UUID primary keys:
- OriginalDocument: stored original images with embeddings
- DocumentLabel: labels detected on original documents
- SearchQuery: search requests
- PrivacyAnalysis: privacy flag analysis per search
- SearchResult: individual matching results per search
"""

import uuid
from django.db import models


class OriginalDocument(models.Model):
    """An original document stored in the local database for similarity comparison."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    image_path = models.TextField(help_text="Path to the stored image file")
    embedding_vector = models.JSONField(
        default=list,
        help_text="Float array of the CNN embedding vector"
    )
    file_hash = models.CharField(
        max_length=128,
        unique=True,
        help_text="SHA-256 hash of the file for deduplication"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"OriginalDocument({self.id}) - {self.file_hash[:12]}..."


class DocumentLabel(models.Model):
    """Labels detected on an original document (e.g., from Vision API)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        OriginalDocument,
        on_delete=models.CASCADE,
        related_name='labels'
    )
    label_type = models.CharField(max_length=50, help_text="Type: object, text, logo, etc.")
    label_value = models.CharField(max_length=255, help_text="Detected label value")
    confidence_score = models.FloatField(default=0.0)

    def __str__(self):
        return f"{self.label_type}: {self.label_value} ({self.confidence_score:.2f})"


class SearchQuery(models.Model):
    """A search request submitted by a user."""
    SOURCE_CHOICES = [
        ('local', 'Local'),
        ('google', 'Google'),
        ('both', 'Both'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    query_image_path = models.TextField(help_text="Path to the uploaded query image")
    query_hash = models.CharField(max_length=128, help_text="SHA-256 hash of the query image")
    search_source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='local')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"SearchQuery({self.id}) - {self.search_source}"


class PrivacyAnalysis(models.Model):
    """Privacy analysis result for a search query."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    search = models.OneToOneField(
        SearchQuery,
        on_delete=models.CASCADE,
        related_name='privacy_analysis'
    )
    face_detected = models.BooleanField(default=False)
    name_detected = models.BooleanField(default=False)
    age_detected = models.BooleanField(default=False)
    address_detected = models.BooleanField(default=False)
    phone_detected = models.BooleanField(default=False)
    total_flags = models.IntegerField(default=0)
    is_blocked = models.BooleanField(default=False)
    analyzed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        status = "BLOCKED" if self.is_blocked else "OK"
        return f"Privacy({self.search_id}) - {self.total_flags} flags - {status}"


class SearchResult(models.Model):
    """An individual result from a search query."""
    SOURCE_CHOICES = [
        ('local', 'Local'),
        ('google', 'Google'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    search = models.ForeignKey(
        SearchQuery,
        on_delete=models.CASCADE,
        related_name='results'
    )
    source_type = models.CharField(max_length=10, choices=SOURCE_CHOICES)
    matched_document = models.ForeignKey(
        OriginalDocument,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matched_results'
    )
    external_url = models.TextField(null=True, blank=True, help_text="URL for Google web matches")
    similarity_score = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-similarity_score']

    def __str__(self):
        return f"Result({self.source_type}) - score: {self.similarity_score:.4f}"
