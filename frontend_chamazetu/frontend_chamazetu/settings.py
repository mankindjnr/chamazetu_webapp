import os
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()
# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# EMAIL SETTINGS
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND")
EMAIL_USE_TLS = True
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
EMAIL_PORT = int(os.getenv("EMAIL_PORT"))
# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("DJANGO_SECRET")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = [
    "localhost",
    "chamazetu.com",
    "www.chamazetu.com",
    "192.168.242.254",
    "0.0.0.0",
    "frontend.192.168.100.7.nip.io",
    "34.45.2.223",
    "35.223.24.137",
    "eea0-102-213-49-8.ngrok-free.app",
]


# Application definition

INSTALLED_APPS = [
    "chama.apps.ChamaConfig",
    "member.apps.MemberConfig",
    "manager.apps.ManagerConfig",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django_celery_results",
    "django_celery_beat",
    "corsheaders",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# SECURE_SSL_REDIRECT = True
# CSRF_COOKIE_SECURE = True
# SESSION_COOKIE_SECURE = True

CORS_ALLOWED_ORIGINS = [
    "https://localhost:8000",
    "https://chamazetu.com",
    "https://www.chamazetu.com",
    "https://0.0.0.0:8000",
    "https://192.168.242.254:8000",
    "https://frontend.192.168.100.7.nip.io",
    "https://eea0-102-213-49-8.ngrok-free.app",
]

CSRF_TRUSTED_ORIGINS = [
    "https://localhost",
    "https://127.0.0.1",
    "https://chamazetu.com",
    "https://www.chamazetu.com",
    "https://frontend.192.168.100.7.nip.io",
    "https://eea0-102-213-49-8.ngrok-free.app",
]

ROOT_URLCONF = "frontend_chamazetu.urls"

imports = ("chama.tasks", "member.tasks", "manager.tasks")

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "frontend_chamazetu.wsgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("FRONTEND_DB_NAME"),
        "USER": os.getenv("FRONTEND_DB_USER"),
        "PASSWORD": os.getenv("FRONTEND_DB_PASSWORD"),
        "HOST": os.getenv("FRONTEND_DB_HOST"),
        "PORT": os.getenv("FRONTEND_DB_PORT"),
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Africa/Nairobi"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATIC_URL = "/static/"

# WHITENOISE
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Celery settings
CELERY_broker_url = os.getenv("CELERY_broker_url")
accept_content = ["json", "pickle"]
task_serializer = "json"
result_serializer = "json"
timezone = "Africa/Nairobi"
CELERY_enable_utc = False  # set to False to use local timezone(i think)
result_expires = 3600
# CELERY_TASK_TIME_LIMIT = 1000  # 1000 seconds - 16 minutes is how long a task can run
CELERY_WORKER_CONCURRENCY = 4  # number of workers

# monitor celery tasks
# result_backend = "django-db"  # YOU CAN USE REDIS AS WELL
# using redis as the result backend
result_backend = os.getenv("result_backend")

# celery beat settings
CELERY_BEAT_SCHEDULER = os.getenv("CELERY_BEAT_SCHEDULER")


# Logging configuration
if not os.path.exists(os.path.join(BASE_DIR, "logs")):
    os.mkdir(os.path.join(BASE_DIR, "logs"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "ERROR",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "chama_file": {
            "level": "DEBUG",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(BASE_DIR, "logs/chama.log"),
            "maxBytes": 1024 * 1024 * 5,  # 5MB
            "backupCount": 5,
            "formatter": "verbose",
        },
        "manager_file": {
            "level": "DEBUG",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(BASE_DIR, "logs/manager.log"),
            "maxBytes": 1024 * 1024 * 5,  # 5MB
            "backupCount": 5,
            "formatter": "verbose",
        },
        "member_file": {
            "level": "DEBUG",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(BASE_DIR, "logs/member.log"),
            "maxBytes": 1024 * 1024 * 5,  # 5MB
            "backupCount": 5,
            "formatter": "verbose",
        },
    },
    "loggers": {
        "chama": {
            "handlers": ["chama_file"],
            "level": "DEBUG",
            "propagate": True,
        },
        "manager": {
            "handlers": ["manager_file"],
            "level": "DEBUG",
            "propagate": True,
        },
        "member": {
            "handlers": ["member_file"],
            "level": "DEBUG",
            "propagate": True,
        },
    },
}
