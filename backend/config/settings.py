"""
Django settings for Image Manipulation Detection System.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-dev-key-change-in-production')
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 'yes')

# Di production, isi dengan domain asli (contoh: 'api-kamu.hf.space')
# Di development, biarkan '*' atau 'localhost'
ALLOWED_HOSTS_RAW = os.getenv('ALLOWED_HOSTS', '*')
ALLOWED_HOSTS = [h.strip() for h in ALLOWED_HOSTS_RAW.split(',')]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    'corsheaders',
    # Local
    'api',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database — PostgreSQL (auto-fallback ke SQLite untuk development)
_USE_POSTGRES = os.getenv('USE_POSTGRES', 'true').lower() in ('true', '1', 'yes')

if _USE_POSTGRES:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'image_detection'),
            'USER': os.getenv('DB_USER', 'postgres'),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
        }
    }
else:
    # SQLite fallback untuk development tanpa PostgreSQL
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'id'
TIME_ZONE = 'Asia/Jakarta'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'  # Untuk perintah 'collectstatic'

# Media files (uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS
# Tambahkan domain production frontend di sini atau lewat env variable CORS_ORIGINS
_CORS_ORIGINS_RAW = os.getenv('CORS_ORIGINS', '')
_EXTRA_ORIGINS = [o.strip() for o in _CORS_ORIGINS_RAW.split(',') if o.strip()]
CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
] + _EXTRA_ORIGINS

# Hanya izinkan semua origin jika sedang dalam mode DEBUG (development)
CORS_ALLOW_ALL_ORIGINS = DEBUG

# Security headers (aktif di production)
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    # Di production: sembunyikan Browsable API, hanya tampilkan JSON
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ] + (['rest_framework.renderers.BrowsableAPIRenderer'] if DEBUG else []),
    # Rate Limiting: mencegah spam & DDoS Level 7
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': os.getenv('THROTTLE_ANON', '30/minute'),    # 30 req/menit per IP anonim
        'user': os.getenv('THROTTLE_USER', '100/minute'),   # 100 req/menit per user terautentikasi
    },
}

def _clean_env_value(name, default=''):
    value = os.getenv(name, default)
    return value.strip().strip('"').strip("'")


# Admin credentials — ambil dari environment variable, bukan hardcode!
ADMIN_USERNAME = _clean_env_value('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = _clean_env_value('ADMIN_PASSWORD', 'admin123')

# Google Cloud Vision API
GOOGLE_CLOUD_API_KEY = os.getenv('GOOGLE_CLOUD_API_KEY', '')

# Gemini API — supports key pool for automatic rotation
# Use GEMINI_API_KEYS (comma-separated) for multiple keys:
#   GEMINI_API_KEYS=key1,key2,key3
# Or GEMINI_API_KEY for a single key (fallback):
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GEMINI_API_KEYS = os.getenv('GEMINI_API_KEYS', '')

# Google Cloud Service Account credentials (JSON key file)
GOOGLE_APPLICATION_CREDENTIALS = os.getenv(
    'GOOGLE_APPLICATION_CREDENTIALS',
    os.path.join(BASE_DIR, 'doksli-489605-3a86fa275159.json')
)
# Set env var so google-cloud-vision library auto-detects it
os.environ.setdefault('GOOGLE_APPLICATION_CREDENTIALS', GOOGLE_APPLICATION_CREDENTIALS)

# ML Settings
SIMILARITY_THRESHOLD = 0.80   # Minimum local embedding score to count as a direct match
SIMILARITY_MIN = 0.6          # Absolute floor for direct local embedding matches
LOCAL_CANDIDATE_MIN = 0.35    # Wider local pool before visual re-ranking
LOCAL_MATCH_THRESHOLD = 0.50  # Minimum visual re-ranked local score to accept
ONLINE_MATCH_THRESHOLD = 0.65 # Minimum web score to show as a candidate
SIMILARITY_TOP_K = 5          # Maximum results to return
PRIVACY_FLAG_THRESHOLD = 3    # Block if >= 3 privacy flags detected

# Sub-region cropping settings (for screenshot analysis)
CROP_SCALES = [0.5, 0.7]      # Window sizes relative to image dimensions
CROP_OVERLAP = 0.5             # 50% overlap between sliding windows
CROP_MIN_SIZE = 100            # Minimum crop dimension in pixels
