"""FastAPI app - the thin layer between the React frontend and the
unchanged engine/data packages. See the migration plan
(Streamlit -> React) for the full architecture.

Run for local dev (with the venv active, from poke_calc/):
    uvicorn poke_calc.api.main:app --reload --port 8000

In production this also serves the built React bundle (web/dist) as a
single process, so there's nothing extra to deploy - the API and the
static frontend are the same server. Local dev instead runs Vite's own
dev server on a different port, hence the CORS allowance below.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from poke_calc.api.routes_calc import router as calc_router
from poke_calc.api.routes_dex import router as dex_router
from poke_calc.api.routes_teams import router as teams_router

app = FastAPI(title="Pokemon Champions Damage Calculator API")

# Vite's default dev server origin - only relevant to local development;
# in production the frontend is served from this same origin (below), so
# there's no cross-origin request to allow at all.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dex_router, prefix="/api")
app.include_router(calc_router, prefix="/api")
app.include_router(teams_router, prefix="/api/teams")

# The built frontend doesn't exist until web/ is scaffolded (Phase 2) and
# built (`npm run build`) - mount it only if present, so local API-only
# development (and every test in this repo) doesn't need web/ at all.
_WEB_DIST = Path(__file__).parent.parent.parent.parent / "web" / "dist"
if _WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=_WEB_DIST, html=True), name="web")
