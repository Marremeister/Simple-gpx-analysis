"""Application entrypoint for the FastAPI backend."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router
from .database import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI(title="49er GPX Race Analyzer")
app.include_router(router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "49er GPX Race Analyzer backend"}
