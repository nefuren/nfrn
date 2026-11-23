"""設定。値は環境変数（DESK_*）または .env から読む。秘密情報はコードに書かない。"""

from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent

MIN_TOKEN_LENGTH = 32


def _split_csv(value: object) -> object:
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DESK_",
        env_file=(REPO_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    token: SecretStr = Field(min_length=MIN_TOKEN_LENGTH)
    host: str = "127.0.0.1"
    port: int = Field(default=8787, ge=1, le=65535)
    allowed_origins: Annotated[list[str], NoDecode] = [
        "http://127.0.0.1:8787",
        "http://localhost:8787",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]
    allowed_hosts: Annotated[list[str], NoDecode] = ["127.0.0.1", "localhost"]
    session_ttl_seconds: int = Field(default=12 * 3600, ge=60)
    cookie_secure: bool = False
    geoip_db: Path | None = None
    auth_log: Path = Path("/var/log/auth.log")
    audit_paths: Annotated[list[Path], NoDecode] = []
    audit_interval_seconds: int = Field(default=6 * 3600, ge=600)
    frontend_dist: Path = REPO_DIR / "frontend" / "dist"

    @field_validator("allowed_origins", "allowed_hosts", "audit_paths", mode="before")
    @classmethod
    def _csv(cls, value: object) -> object:
        return _split_csv(value)

    @field_validator("allowed_origins")
    @classmethod
    def _origins_no_trailing_slash(cls, value: list[str]) -> list[str]:
        return [v.rstrip("/") for v in value]

    @field_validator("geoip_db", mode="before")
    @classmethod
    def _empty_is_none(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return value

    @field_validator("geoip_db")
    @classmethod
    def _relative_to_backend(cls, value: Path | None) -> Path | None:
        if value is not None and not value.is_absolute():
            return BACKEND_DIR / value
        return value

    def is_loopback(self) -> bool:
        if self.host == "localhost":
            return True
        try:
            return ipaddress.ip_address(self.host).is_loopback
        except ValueError:
            return False
