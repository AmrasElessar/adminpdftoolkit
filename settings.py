"""Application settings — single source of truth for env-driven configuration.

All knobs that operations / deployment may want to change live here. Reading
them through one typed object (instead of scattered ``os.environ.get`` calls)
makes it trivial to:

- discover what the app supports (just inspect ``Settings``);
- override values from a ``.env`` file in dev;
- get type-safe access (``settings.max_upload_mb`` is an ``int``, not ``str``);
- document defaults in one place.

Add a new knob: declare it as a class attribute with a default and a type.
``BaseSettings`` will pick it up from the matching ``HT_*`` env var
automatically (case-insensitive).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ----- App identity -----
    app_name: str = Field(default="Admin PDF Toolkit", description="Visible product name")
    app_version: str = Field(
        default="1.10.0", description="Semver string (also exposed in /health)"
    )

    # ----- Deployment profile -----
    profile: str = Field(
        default="prod",
        pattern="^(dev|prod)$",
        description=(
            "Deployment profile. 'dev' relaxes defaults (binds 0.0.0.0, "
            "exposes /docs); 'prod' (default) keeps the server loopback-only "
            "and hides API documentation. Override via HT_PROFILE."
        ),
    )

    # ----- Network -----
    # Default 0.0.0.0 — this is a LAN-first tool; remote clients are gated by
    # the mobile-auth middleware (mobile_token), not by binding to loopback.
    host: str = Field(default="0.0.0.0", description="Bind address")
    port: int = Field(default=8000, ge=1, le=65535, description="Listen port")
    https: bool = Field(default=False, description="Enable self-signed HTTPS at startup")
    loopback_bypass: bool = Field(
        default=True,
        description=(
            "When True (default), requests from 127.0.0.1 / ::1 / localhost "
            "skip the mobile-auth check (operator's own browser). Set to "
            "False (HT_LOOPBACK_BYPASS=false) when running behind a reverse "
            "proxy that connects to the app via loopback — otherwise every "
            "remote client becomes 'local' and bypasses authentication."
        ),
    )

    # ----- Upload limits -----
    max_upload_mb: int = Field(
        default=200,
        ge=1,
        description=(
            "Per-file upload cap in megabytes (rejected with 413 above this). "
            "Default 200 MB covers typical PDFs comfortably; operators handling "
            "huge scans can raise via HT_MAX_UPLOAD_MB. Note: combined with the "
            "thread pool, a 2 GB cap is a quick disk-fill DoS — keep this "
            "modest unless you really need it."
        ),
    )

    # ----- Working directories -----
    work_dir: Path = Field(
        default=Path("_work"),
        description="Where in-flight jobs and uploads are staged (will be created if missing)",
    )
    output_dir: Path = Field(
        default=Path("output"),
        description="Default location for persisted outputs (currently unused; reserved)",
    )
    history_db: Path = Field(
        default=Path("_work/history.db"),
        description=(
            "SQLite database file recording every conversion / batch / OCR / "
            "distribute. Resolved relative to the project's BASE_DIR when not "
            "absolute. Default sits under _work/ so it lives with other "
            "ephemeral state but is preserved across the work TTL sweep."
        ),
    )

    # ----- Cleanup / TTLs -----
    work_ttl_seconds: int = Field(
        default=30 * 60,
        ge=60,
        description="Idle subdirectory under work_dir is deleted after this many seconds",
    )
    job_memory_ttl_seconds: int = Field(
        default=60 * 60,
        ge=60,
        description="In-memory job entry is purged after this many seconds",
    )
    cleanup_interval_seconds: int = Field(
        default=10 * 60,
        ge=30,
        description="How often the background sweeper runs",
    )
    max_job_timeout_seconds: int = Field(
        default=30 * 60,
        ge=60,
        description="Hard per-job cap; progress endpoints surface a timeout error past this",
    )

    # ----- Logging -----
    log_level: str = Field(
        default="INFO",
        pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
        description="Root logger level",
    )

    # ----- Behaviour switches -----
    preload_ocr_model: bool = Field(
        default=True,
        description="Warm up the EasyOCR model at startup so the first user request is fast",
    )
    parallel_batch_workers: int = Field(
        default=0,
        ge=0,
        description=(
            "Worker processes for batch Excel merge parsing. 0 = auto "
            "(min(cpu_count, 4)). 1 = serial."
        ),
    )

    # ----- PDF güvenlik politikası -----
    safety_policy: str = Field(
        default="block_danger",
        pattern="^(off|warn|block_danger)$",
        description=(
            "PDF güvenlik tarama politikası. "
            "'off'   → safety check atlanır (geliştirme amaçlı, prod için ÖNERİLMEZ). "
            "'warn'  → tehdit bulunsa da dönüşüm devam eder, sadece header döner. "
            "'block_danger' → 'danger' verdict alan PDF reddedilir (default)."
        ),
    )

    # ----- API documentation -----
    docs_url: str | None = Field(
        default=None,
        description=(
            "Swagger UI path. Disabled by default in prod profile to "
            "shrink the public attack surface; set HT_DOCS_URL=/docs for dev."
        ),
    )
    redoc_url: str | None = Field(
        default=None,
        description="ReDoc UI path (disabled by default — see docs_url note).",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="HT_",
        case_sensitive=False,
        extra="ignore",
    )

    def model_post_init(self, __context) -> None:
        """Apply dev-profile relaxations after env loading.

        ``HT_PROFILE=dev`` re-enables Swagger / ReDoc paths so an operator
        running locally still gets a browseable API. Explicit env overrides
        win over both. (host stays 0.0.0.0 by default in both profiles —
        this is a LAN tool gated by mobile-auth middleware.)
        """
        import os as _os

        if self.profile == "dev":
            if "HT_DOCS_URL" not in _os.environ:
                object.__setattr__(self, "docs_url", "/docs")
            if "HT_REDOC_URL" not in _os.environ:
                object.__setattr__(self, "redoc_url", "/redoc")


# Module-level singleton — import once, share everywhere.
settings = Settings()
