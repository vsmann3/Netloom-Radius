import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-key-not-for-deployment")
os.environ.setdefault("DB_PASSWORD", "test-only")
from .settings import *  # noqa: F403,E402

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
