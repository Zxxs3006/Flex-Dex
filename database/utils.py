from .models import db
import os


def init_db(app):
    """Initialize the database with the Flask app."""
    db.init_app(app)

    # Log which database is being used
    db_url = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if 'postgresql' in db_url or 'postgres' in db_url:
        print("Using PostgreSQL database")
    else:
        print(f"WARNING: Using SQLite database - data will not persist!")
        print(f"Set DATABASE_URL environment variable to use PostgreSQL")

    with app.app_context():
        db.create_all()
        print("Database tables created successfully.")
