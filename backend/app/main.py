"""WSGI entrypoint for running the Flask app with `flask run` or `python -m`."""
from __future__ import annotations

from . import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
