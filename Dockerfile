# ── Stage 1: Tailwind CSS build ────────────────────────────────────────────
FROM node:20-slim AS css-builder

WORKDIR /build

# Copy lockfile first so this layer is cached until deps change
COPY package.json package-lock.json tailwind.config.js ./
COPY app/static/css/input.css app/static/css/

# ci uses the lockfile exactly — faster and reproducible.
# devDependencies (tailwindcss) are needed to compile CSS, so don't omit them.
RUN npm ci

COPY app/templates app/templates
COPY app/static/js app/static/js

RUN npm run build:css


# ── Stage 2: Python dependency builder ─────────────────────────────────────
FROM python:3.11-slim AS pip-builder

WORKDIR /build

# gcc is required to compile native extensions for some packages.
# It lives only in this stage and is never copied to the runtime image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Build into an isolated venv so we can copy it cleanly to the runtime stage
RUN python -m venv /venv \
    && /venv/bin/pip install --upgrade pip --no-cache-dir \
    && /venv/bin/pip install --no-cache-dir -r requirements.txt


# ── Stage 3: Runtime image ──────────────────────────────────────────────────
FROM python:3.11-slim

# Prevent .pyc files and ensure logs flush immediately
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/venv/bin:$PATH"

WORKDIR /app

# Dedicated non-root user — no home directory, no login shell
RUN groupadd --system coverbound \
    && useradd --system --gid coverbound --no-create-home --shell /sbin/nologin coverbound

# Pre-built venv from pip-builder — no compiler or build tools needed here
COPY --from=pip-builder /venv /venv

# Application code and freshly compiled CSS
COPY ./app ./app
COPY --from=css-builder /build/app/static/css/tailwind.css ./app/static/css/tailwind.css

# Create the data directory and transfer ownership in a single layer
RUN mkdir -p /app/data \
    && chown -R coverbound:coverbound /app

USER coverbound

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["/venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
