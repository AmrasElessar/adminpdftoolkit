# syntax=docker/dockerfile:1.7
# Admin PDF Toolkit — build from the repository root:
#   docker build -t admin-pdf-toolkit .
#   docker build --build-arg WITH_LIBREOFFICE=false -t admin-pdf-toolkit:slim .

# ---- Web UI ------------------------------------------------------------------
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
# Vite writes into ../server/adminpdf/web_dist
RUN mkdir -p /server/adminpdf && npm run build

# ---- Runtime -----------------------------------------------------------------
FROM python:3.13-slim AS runtime
ARG WITH_LIBREOFFICE=true

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APT_HOST=0.0.0.0 \
    APT_PORT=8000 \
    APT_DATA_DIR=/data \
    # Requests arrive from the Docker bridge, not loopback.
    APT_TRUSTED_NETWORKS=172.16.0.0/12

# OCR (Tesseract tr+en), PDF/A (Ghostscript), repair (qpdf), antivirus
# (ClamAV), fonts with Turkish coverage, and optionally LibreOffice for
# high-fidelity Office → PDF.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tini tesseract-ocr tesseract-ocr-tur tesseract-ocr-eng ghostscript qpdf \
        clamav fonts-dejavu-core fonts-liberation2 fonts-noto-core \
    && if [ "$WITH_LIBREOFFICE" = "true" ]; then \
        apt-get install -y --no-install-recommends libreoffice-writer-nogui libreoffice-calc-nogui libreoffice-impress-nogui; \
       fi \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app && useradd --system --gid app --create-home app \
    && mkdir -p /data && chown app:app /data

WORKDIR /app
COPY server/pyproject.toml ./
COPY server/adminpdf ./adminpdf
COPY --from=web /server/adminpdf/web_dist ./adminpdf/web_dist
RUN pip install . \
    && python -c "import adminpdf.app"

USER app
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).status == 200 else 1)"
ENTRYPOINT ["tini", "--"]
CMD ["python", "-m", "adminpdf"]
