from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from config import Config

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()


def create_app(config_class=Config):
    """Application factory pattern."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    # Custom error responses for JWT failures — without these,
    # Flask-JWT-Extended's defaults are still JSON, but this keeps the
    # error shape ({"error": "..."}) consistent with every other
    # endpoint in this API instead of its default {"msg": "..."}.
    @jwt.unauthorized_loader
    def handle_missing_token(reason):
        return jsonify({'error': f'Missing or invalid authorization token: {reason}'}), 401

    @jwt.invalid_token_loader
    def handle_invalid_token(reason):
        return jsonify({'error': f'Invalid token: {reason}'}), 401

    @jwt.expired_token_loader
    def handle_expired_token(jwt_header, jwt_payload):
        return jsonify({'error': 'Token has expired, please log in again'}), 401

    # Import models so SQLAlchemy/Flask-Migrate is aware of every table
    # before any migration is generated or the app queries the database.
    with app.app_context():
        from app import models  # noqa: F401

    # Register blueprints
    from app.routes.category_routes import category_bp
    from app.routes.order_routes import order_bp
    from app.routes.product_routes import product_bp
    from app.routes.user_routes import auth_bp, user_bp

    app.register_blueprint(product_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(category_bp)
    app.register_blueprint(order_bp)

    return app
