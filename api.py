"""HTTP API for the Terravia chatbot.

Exposes the grounded agent (src/: nlu -> query -> answer) as a small JSON API
the static website calls with fetch(). No Streamlit. The data loads once at
startup from the offline snapshot, so the API works without network access.

Run:  uvicorn api:app --reload --port 8000
Endpoints:
  GET  /health        -> liveness + data provenance
  POST /chat {question}-> grounded answer + metadata
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src import config, data_loader, nlu, answer as A
from src.llm import get_provider, provider_health

app = FastAPI(title="Terravia Chatbot API", version="1.0")

# CORS: the static site is served from a different origin (e.g. a file server or
# GitHub Pages), so allow browser calls. Tighten `allow_origins` in production.
_ALLOWED = os.environ.get("TERRAVIA_CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _ALLOWED],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Load data + provider once at startup (cached for the process lifetime).
_DF, _PROV = data_loader.load(prefer_live=False)
_PROVIDER = get_provider(os.environ.get("HOTSPOT_LLM_PROVIDER", config.LLM_PROVIDER))


class ChatRequest(BaseModel):
    question: str = Field(..., max_length=500)


class ChatResponse(BaseModel):
    answer: str
    intent: str
    parsed_by: str          # guardrail | rule | llm
    grounded: bool
    source: str
    data_year: int


@app.get("/health")
def health() -> dict:
    h = provider_health(os.environ.get("HOTSPOT_LLM_PROVIDER", config.LLM_PROVIDER))
    return {
        "status": "ok",
        "source": _PROV.source,
        "release_year": _PROV.release_year,
        "data_year": _PROV.data_year,
        "origin": _PROV.origin,
        "chatbot_engine": {"ok": h.ok, "message": h.message},
    }


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    question = (req.question or "").strip()
    sq = nlu.route(question, provider=_PROVIDER)
    ans = A.answer(_DF, sq)
    text = ans.text if ans.grounded else (
        "I could not fully ground that answer in the data, so I am holding it "
        "back. Try rephrasing.")
    return ChatResponse(
        answer=text, intent=ans.intent, parsed_by=sq.parser,
        grounded=ans.grounded, source=_PROV.source, data_year=_PROV.data_year,
    )


# Optionally serve the static site from the same origin (avoids CORS entirely).
# Enable by setting TERRAVIA_SERVE_SITE=1. The site lives at the repo root.
if os.environ.get("TERRAVIA_SERVE_SITE") == "1":
    app.mount("/", StaticFiles(directory=str(config.ROOT), html=True), name="site")
