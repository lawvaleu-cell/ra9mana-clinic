import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production-9f8a7d6c5b4e3f2a1")
    DATABASE_PATH = os.path.join(BASE_DIR, "instance", "clinic.db")
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB uploads max
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "instance", "uploads")
    APP_NAME = "RA9MANA Clinic"
    APP_VERSION = "1.0.0"
    LOW_STOCK_THRESHOLD_DEFAULT = 10
    EXPIRY_WARNING_DAYS = 60
