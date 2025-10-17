"""WSGI entry point for running the Flask app via ``flask run`` or ``python``.

The module can be invoked either as ``python -m app.main`` (preferred) or as a
script, e.g. ``python app/main.py`` as IDEs often configure.  Direct execution
does not provide a package context, so we temporarily augment ``sys.path`` to
import :func:`create_app` from the local package.
"""
from __future__ import annotations

from pathlib import Path
import sys


if __package__ in {None, ""}:  # Executed directly, e.g. ``python app/main.py``
    package_root = Path(__file__).resolve().parent
    sys.path.insert(0, str(package_root.parent))
    from app import create_app  # type: ignore
else:  # Imported as part of the ``app`` package (``python -m app.main``)
    from . import create_app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)