# One image: the built app (with the gallery) and the Python backend, served by one process.

# ---- stage 1: build the pixel-art app ----
FROM node:20-slim AS app
WORKDIR /app
COPY app/package.json app/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY app/ ./
RUN npm run build

# ---- stage 2: the backend ----
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
# git walks lines and clones public repos for live séances. No token is ever configured.
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY backend/pyproject.toml backend/pyproject.toml
COPY backend/ouija backend/ouija
RUN pip install -e backend
COPY --from=app /app/dist /srv/app/dist

ENV OB_STATIC_DIR=/srv/app/dist \
    OB_GALLERY_DIR=/srv/app/dist/gallery \
    OB_CLONE_DIR=/tmp/ouija-clones
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD python -c "import urllib.request,os;urllib.request.urlopen('http://localhost:'+os.environ.get('PORT','8000')+'/api/health')"
CMD ["sh", "-c", "exec uvicorn --app-dir backend --factory ouija.api:app_factory --host 0.0.0.0 --port ${PORT:-8000}"]
