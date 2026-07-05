"""
URL routing for the Image Detection API.
"""

from django.urls import path
from . import views

urlpatterns = [
    path('search/', views.SearchImageView.as_view(), name='search-image'),
    path('add-original/', views.AddOriginalView.as_view(), name='add-original'),
    path('results/<uuid:search_id>/', views.ResultDetailView.as_view(), name='result-detail'),
    path('originals/', views.ListOriginalsView.as_view(), name='list-originals'),
    # Admin endpoints
    path('admin/login/', views.AdminLoginView.as_view(), name='admin-login'),
    path('admin/originals/<uuid:document_id>/', views.DeleteOriginalView.as_view(), name='delete-original'),
]
