# 49er GPX Race Analyzer

A lightweight but extensible toolkit for uploading 49er GPX tracks, aligning fleets, and extracting windowed performance insights. The project follows SOLID principles without overwhelming directory sprawl: the Python backend groups routes and services by feature, and the vanilla JavaScript frontend stays in a single folder for quick tweaks.

## Project structure

```
backend/
  app/
    __init__.py
    api.py            # FastAPI routes
    crud.py           # Small data-access helpers
    database.py       # SQLAlchemy setup
    main.py           # ASGI entrypoint
    models.py         # ORM models
    schemas.py        # Pydantic DTOs
    services/
      gpx.py          # GPX parsing + event detection
      statistics.py   # Window statistics helpers
  requirements.txt
frontend/
  index.html
  main.js
  styles.css
```

SQLite is used in development for zero-config persistence. Data tables match the spec (races, marks, boats, points, events), making it easy to swap in Postgres/PostGIS later.

## Backend setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

This starts the API on `http://localhost:8000`.

## Frontend setup

The frontend is static and framework-free. Any static server works:

```bash
cd frontend
python -m http.server 5173
```

Visit `http://localhost:5173` (adjust the port if needed). The script expects the backend at `http://localhost:8000`. To point to a different API host, define `window.API_BASE` before loading `main.js` or set up a proxy with your web server.

## Key flows

1. **Create a race** – fill name, start time, optional TWD/TWS.
2. **Upload GPX files** – select a race and upload one or more `.gpx` logs. The backend parses, resamples to 1 Hz, stores points, and tags simple tack/gybe events.
3. **Select boats** – choose the boats to display; the Leaflet map renders their tracks.
4. **Set a window** – pick start/end times and refresh stats. The API computes SOG/VMG/heading, distance sailed, height gain, and tack/gybe counts for each boat.
5. **Export** – download the current window metrics as CSV.

## Testing with sample GPX

You can point the upload form at any GPX logs sampled at ~1 Hz. The services handle speed/heading smoothing and basic event detection automatically.

## Extending

* Add richer analytics by expanding `services/statistics.py`.
* Swap SQLite for Postgres by editing `DATABASE_URL` in `database.py` and running migrations.
* Enhance the frontend timeline by building atop the existing fetch helpers in `main.js`.

## Non-implemented snapshot export

`GET /export/snapshot.png` currently returns a `501 Not Implemented` message. The backend leaves room for plugging in a renderer (e.g., MapLibre GL server-side or static map generation) while the frontend can handle client-side screenshotting.

## License

MIT License (add your preferred license here).
