"""Flask application factory for the GPX race analyzer."""
from __future__ import annotations

from flask import Flask
from flask_cors import CORS

from .database import Base, engine
from .routes.api import api_bp
from .routes.web import web_bp


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )
    CORS(app)

    # Ensure tables exist before handling requests.
    Base.metadata.create_all(bind=engine)

    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    return app


def get_app() -> Flask:
    """Convenience accessor used by the WSGI entrypoint."""
    return create_app()
