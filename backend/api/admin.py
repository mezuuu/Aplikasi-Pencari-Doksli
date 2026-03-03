from django.contrib import admin
from .models import (
    OriginalDocument,
    DocumentLabel,
    SearchQuery,
    PrivacyAnalysis,
    SearchResult,
)


@admin.register(OriginalDocument)
class OriginalDocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'file_hash', 'created_at')
    search_fields = ('file_hash',)
    readonly_fields = ('id', 'created_at')


@admin.register(DocumentLabel)
class DocumentLabelAdmin(admin.ModelAdmin):
    list_display = ('id', 'document', 'label_type', 'label_value', 'confidence_score')
    list_filter = ('label_type',)


@admin.register(SearchQuery)
class SearchQueryAdmin(admin.ModelAdmin):
    list_display = ('id', 'search_source', 'created_at')
    list_filter = ('search_source',)


@admin.register(PrivacyAnalysis)
class PrivacyAnalysisAdmin(admin.ModelAdmin):
    list_display = ('id', 'search', 'total_flags', 'is_blocked', 'analyzed_at')
    list_filter = ('is_blocked',)


@admin.register(SearchResult)
class SearchResultAdmin(admin.ModelAdmin):
    list_display = ('id', 'search', 'source_type', 'similarity_score')
    list_filter = ('source_type',)
