# 49er GPX Race Analyzer

A Flask-powered toolkit for uploading 49er GPX tracks, aligning fleets, and extracting
windowed performance insights. The project keeps a compact directory layout while still
following SOLID ideas through clear separation of routes, services, and templates.

## Project structure

```
backend/
  app/
    __init__.py          # Flask application factory
    crud.py              # Data-access helpers around SQLAlchemy
    database.py          # Engine/session management
    main.py              # WSGI entrypoint (``python -m app.main``)
    models.py            # ORM models
    schemas.py           # Pydantic request/response schemas
    routes/
      __init__.py
      api.py             # JSON API (mounted under /api)
      web.py             # Serves the SPA shell
    services/
      gpx.py             # GPXService for parsing + event detection
      statistics.py      # StatisticsService for windowed metrics
    static/
      css/
        base.css
        layout.css
      js/
        apiClient.js
        app.js
        mapView.js
        state.js
        ui.js
    templates/
      base.html
      dashboard.html
  requirements.txt
```

The Flask app serves the HTML shell and static assets directly, so running the backend is
all that is required to load the front end.

## Backend setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app app.main run --debug
```

The server exposes REST endpoints under `/api` while `/` returns the dashboard. When using
`flask run`, static assets are served automatically.

## Core workflows

1. **Create a race** – enter the basics (name, start, optional TWD/TWS) via the left panel.
2. **Upload GPX files** – select a race and drop `.gpx` logs. Each file becomes a boat entry.
3. **Select boats** – toggle boats to render their tracks and compute stats.
4. **Adjust the analysis window** – use the datetime pickers to set `[t0, t1]`, then refresh.
5. **Export** – download the current table as CSV for further analysis.

## Extending

* Add new analytics by subclassing or expanding `StatisticsService`.
* Replace SQLite with Postgres by editing `DATABASE_URL` in `database.py`.
* Introduce additional pages by adding templates and registering more routes without
  increasing directory sprawl.

## License

MIT License (add your preferred license here).
