# Portable container for the Terravia chatbot API. Works on any container host
# (Render, Railway, Fly.io, Cloud Run, etc.). The host provides $PORT.
FROM python:3.12-slim

WORKDIR /app

# Install deps first for layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code + the offline data snapshot (the agent needs data/ to answer).
COPY api.py .
COPY src/ ./src/
COPY data/ ./data/

ENV HOTSPOT_LLM_PROVIDER=null
EXPOSE 8000

# $PORT defaults to 8000 locally; hosts override it.
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]
