import os
from datetime import timedelta

from dotenv import load_dotenv

# Load variables from a local .env file (if present) into the environment.
# .env is gitignored — never commit real credentials.
load_dotenv()


def _normalize_database_url(url: str) -> str:
    """Render/Heroku-style Postgres URLs use the 'postgres://' scheme, but
    SQLAlchemy 1.4+ only recognizes 'postgresql://'. Rewrite it so the same
    DATABASE_URL value works both locally and on those platforms."""
    if url.startswith('postgres://'):
        return url.replace('postgres://', 'postgresql://', 1)
    return url


class Config:
    """Base configuration for the Flask app."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

    # PostgreSQL connection string
    _raw_db_url = os.environ.get('DATABASE_URL')
    if not _raw_db_url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set! "
            "Check that the Postgres service is linked in Railway → Variables."
        )
    SQLALCHEMY_DATABASE_URI = _normalize_database_url(_raw_db_url)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Secret used to sign/verify JWT access tokens (Flask-JWT-Extended).
    # Falls back to a dev-only default so local runs work without extra
    # setup — set a real JWT_SECRET_KEY env var before deploying.
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'dev-jwt-secret-key-change-in-production')
    # How long an access token stays valid before the client must log in
    # again. 1 hour is a reasonable default for this checkpoint's scope
    # (no refresh-token flow is implemented).
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)


class TestConfig(Config):
    """Configuration used by the pytest suite — isolated in-memory SQLite
    database so tests never touch the real development/production data."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
