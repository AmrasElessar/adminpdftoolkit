# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# Admin PDF Toolkit — production image
# Multi-stage build: builder installs deps, runtime is minimal.
# ---------------------------------------------------------------------------

# ---- Builder ---------------------------------------------------------------
FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# System deps for pdfplumber / pymupdf / easyocr / pycairo (xhtml2pdf chain).
# pycairo ships sdist-only on Linux so libcairo2-dev + pkg-config are
# required to build the wheel here in the builder stage.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libgl1 \
        libglib2.0-0 \
        libcairo2-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --wheel-dir=/wheels -r requirements.txt

# ---- Runtime ---------------------------------------------------------------
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_HOME=/app \
    HOST=0.0.0.0 \
    PORT=8000 \
    MAX_UPLOAD_MB=2048

# Runtime libs only — libcairo2 (no -dev) for the pre-built pycairo wheel
# imported by svglib.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libcairo2 \
        clamav \
        tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app \
    && useradd  --system --gid app --home ${APP_HOME} app

WORKDIR ${APP_HOME}

COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

COPY --chown=app:app app.py app_http.py state.py settings.py \
                     pdf_converter.py pdf_safety.py ./
COPY --chown=app:app core/ ./core/
COPY --chown=app:app routers/ ./routers/
COPY --chown=app:app pipelines/ ./pipelines/
COPY --chown=app:app parsers/ ./parsers/
COPY --chown=app:app templates/ ./templates/
COPY --chown=app:app static/ ./static/
COPY --chown=app:app LICENSE NOTICE.txt THIRD_PARTY_LICENSES.md ./

# ClamAV in the container is expected to come from the system package
# (installed in the builder stage if desired); pdf_safety falls back to
# whatever clamscan is on PATH. The bundled ./clamav/ Windows portable is
# not relevant inside Linux containers.

RUN mkdir -p _work output && chown -R app:app _work output

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/',timeout=3).status==200 else 1)" || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "app.py"]

LABEL org.opencontainers.image.title="Admin PDF Toolkit" \
      org.opencontainers.image.description="Offline PDF toolkit by Engin — convert / edit / annotate / replace, 35+ tools, web UI" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later" \
      org.opencontainers.image.source="https://github.com/orhanenginokay/pdfconverter" \
      org.opencontainers.image.version="1.10.0"
