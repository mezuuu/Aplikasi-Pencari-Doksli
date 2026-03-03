"""
URL routing for the Image Detection API.
"""

from django.urls import path
from . import views

urlpatterns = [
    path('search/', views.search_image, name='search-image'),
    path('add-original/', views.add_original, name='add-original'),
    path('results/<uuid:search_id>/', views.get_result_detail, name='result-detail'),
    path('originals/', views.list_originals, name='list-originals'),
    # Admin endpoints
    path('admin/login/', views.admin_login, name='admin-login'),
    path('admin/originals/<uuid:document_id>/', views.delete_original, name='delete-original'),
]
