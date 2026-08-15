from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config

db = SQLAlchemy()
migrate = Migrate()


def create_app(config_class=Config):
    """Application factory pattern."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Import models so SQLAlchemy/Flask-Migrate is aware of every table
    # before any migration is generated or the app queries the database.
    with app.app_context():
        from app import models  # noqa: F401

    # Register blueprints
    from app.routes.product_routes import product_bp
    from app.routes.user_routes import user_bp

    app.register_blueprint(product_bp)
    app.register_blueprint(user_bp)

    return app
