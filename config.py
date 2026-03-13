import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'pokedex-secret-key-change-in-production'

    # Database - Use PostgreSQL in production, SQLite for local dev
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
        # Fix for SQLAlchemy 1.4+ (Heroku/Render uses postgres://, SQLAlchemy needs postgresql://)
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

    SQLALCHEMY_DATABASE_URI = DATABASE_URL or 'sqlite:///pokedex.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # PokémonTCG API
    POKEMON_TCG_API_URL = 'https://api.pokemontcg.io/v2'
    POKEMON_TCG_API_KEY = os.environ.get('POKEMON_TCG_API_KEY', '')

    # OCR is disabled in web deployment (Tesseract not available on most hosts)
    OCR_ENABLED = os.environ.get('OCR_ENABLED', 'false').lower() == 'true'

    # Upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
