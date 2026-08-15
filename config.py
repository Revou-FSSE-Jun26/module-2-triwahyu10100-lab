import os
from dotenv import load_dotenv

# Load variables from a local .env file (if present) into the environment.
# .env is gitignored — never commit real credentials.
load_dotenv()


class Config:
    """Base configuration for the Flask app."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

    # PostgreSQL connection string — adjust user/password to match your local setup
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'postgresql://postgres:postgres@localhost:5432/revoshop_db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
