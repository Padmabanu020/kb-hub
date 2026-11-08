import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env(key, default=None):
    return os.environ.get(key, default)


SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-insecure-key-change-me")
DEBUG = env("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "hub",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

# ---------------------------------------------------------------- Database
if env("DB_ENGINE", "mssql") == "sqlite":
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
else:
    trusted = env("MSSQL_TRUSTED", "0") == "1"
    extra = "TrustServerCertificate=yes" + (";Trusted_Connection=yes" if trusted else "")
    DATABASES = {"default": {
        "ENGINE": "mssql",
        "NAME": env("MSSQL_DB", "kb_hub"),
        "USER": "" if trusted else env("MSSQL_USER", "sa"),
        "PASSWORD": "" if trusted else env("MSSQL_PASSWORD", ""),
        "HOST": env("MSSQL_HOST", "localhost"),
        "PORT": env("MSSQL_PORT", "1433"),
        "OPTIONS": {"driver": env("MSSQL_DRIVER", "ODBC Driver 18 for SQL Server"), "extra_params": extra},
    }}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_TZ = True
STATIC_URL = "static/"

# ---------------------------------------------------------------- DRF / CORS
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer",
                                 "rest_framework.renderers.BrowsableAPIRenderer"],
}
CORS_ALLOW_ALL_ORIGINS = True
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024

# ---------------------------------------------------------------- KB settings
FAISS_DIR = Path(env("FAISS_DIR", BASE_DIR / "vector_store"))
EMBEDDING_MODEL = env("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
CHUNK_SIZE = int(env("CHUNK_SIZE", "900"))
SCRAPE_WORKERS = int(env("SCRAPE_WORKERS", "8"))
SCRAPE_TIMEOUT = int(env("SCRAPE_TIMEOUT", "20"))
SCRAPE_MAX_CHARS = int(env("SCRAPE_MAX_CHARS", "3000000"))

LLM_ENABLED = env("LLM_ENABLED", "1") == "1"
LLM_BASE_URL = env("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_MODEL = env("LLM_MODEL", "llama3.2")
LLM_API_KEY = env("LLM_API_KEY", "ollama")
LLM_TIMEOUT = int(env("LLM_TIMEOUT", "90"))
