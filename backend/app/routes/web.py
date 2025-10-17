"""Routes serving the HTML shell for the single-page application."""
from __future__ import annotations

from flask import Blueprint, render_template

web_bp = Blueprint("web", __name__)


@web_bp.get("/")
def dashboard():
    """Render the main dashboard."""
    return render_template("dashboard.html")
