"""Single source of configuration. Every knob is an ``APT_*`` env var."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

VERSION = "2.0.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APT_", env_file=".env", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8000

    data_dir: Path = Path("_data")
    web_dist: Path = Path(__file__).parent / "web_dist"

    max_upload_mb: int = Field(default=200, ge=1)
    file_ttl_minutes: int = Field(default=120, ge=1)
    # Everything stored at once (uploads + results); 0 disables the cap.
    max_storage_mb: int = Field(default=10240, ge=0)

    max_workers: int = Field(default=2, ge=1, le=32)
    job_timeout_seconds: int = Field(default=600, ge=5)
    # Address-space cap for worker processes (POSIX only). 0 disables.
    worker_memory_mb: int = Field(default=4096, ge=0)

    # Extra Host header values to accept (comma-separated), e.g. a DNS name.
    allowed_hosts: str = ""
    # Comma-separated CIDRs treated like this machine (no pairing), e.g. the
    # Docker bridge "172.16.0.0/12" or a locked-down office VLAN.
    trusted_networks: str = ""
    # When true, non-loopback clients must pair with ``pairing_key`` first.
    lan_enabled: bool = False
    pairing_key: str = ""
    # Interactive API docs at /api/docs (development aid; off by default).
    api_docs: bool = False
    # HTTPS with this server's own local certificate authority (core/tls.py).
    # Only turn off behind a TLS reverse proxy of your own.
    tls: bool = True
    # Use your own certificate instead (e.g. from a company CA).
    tls_cert_file: Path | None = None
    tls_key_file: Path | None = None

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def files_dir(self) -> Path:
        return self.data_dir / "files"

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"

    @property
    def tls_dir(self) -> Path:
        return self.data_dir / "tls"

    @property
    def scheme(self) -> str:
        return "https" if self.tls else "http"


@lru_cache
def get_settings() -> Settings:
    return Settings()
