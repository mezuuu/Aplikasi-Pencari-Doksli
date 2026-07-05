"""
URL configuration for the Image Detection project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from api.views import HealthCheckView

urlpatterns = [
    path('', HealthCheckView.as_view(), name='root-health-check'),
    path('', include('api.urls')),
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
