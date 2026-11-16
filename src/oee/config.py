"""Konfigurácia aplikácie (premenné prostredia s prefixom `OEE_`, súbor `.env` v koreni projektu).

Pravidlá (CLAUDE.md, ARCHITECTURE §9, §10.1):
- relatívne cesty sa rozlišujú voči koreňu projektu, nie voči aktuálnemu priečinku;
- `.env` sa číta v UTF-8 (systémové kódovanie Windows je cp1251);
- lokálne AI: povolený je iba Ollama na `localhost` / `127.0.0.1` (žiadne cloudové AI API);
- testy vytvárajú `Settings(_env_file=None, ...)`, aby nečítali vývojárov `.env`.

Model zmeny (výkon linky, target, cieľ OEE …) sem nepatrí — zadáva ho manažér v Settings (PLANNING D8).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# src/oee/config.py -> koreň projektu (projekt sa inštaluje editovateľne: `pip install -e .`)
PROJECT_ROOT = Path(__file__).resolve().parents[2]

LOCAL_OLLAMA_HOSTS = frozenset({"localhost", "127.0.0.1"})

AiLang = Literal["en", "sk"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OEE_",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    line_id: str = "L01"
    """Linka, pre ktorú web hlási a zobrazuje dáta (MVP: jedna linka)."""
    db_path: Path = Path("data/local/oee.db")
    dataset_path: Path = Path("data/raw/dummy_data.xlsx")

    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:3b"
    ai_enabled: bool = True
    ai_lang: AiLang = "en"
    ai_timeout_s: float = Field(default=30.0, gt=0)

    @field_validator("db_path", "dataset_path", mode="after")
    @classmethod
    def _resolve_against_project_root(cls, value: Path) -> Path:
        return value if value.is_absolute() else PROJECT_ROOT / value

    @field_validator("ollama_url", mode="after")
    @classmethod
    def _only_local_ollama(cls, value: str) -> str:
        url = value.strip().rstrip("/")
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"}:
            raise ValueError("OEE_OLLAMA_URL must start with http:// or https://")
        if parts.username or parts.password or parts.path or parts.query or parts.fragment:
            raise ValueError("OEE_OLLAMA_URL must be a bare base URL, e.g. http://127.0.0.1:11434")
        if (parts.hostname or "") not in LOCAL_OLLAMA_HOSTS:
            raise ValueError(
                "OEE_OLLAMA_URL must point to localhost or 127.0.0.1 (cloud / remote AI is not allowed)"
            )
        return url


def get_settings() -> Settings:
    """Nastavenia aplikácie z prostredia a `.env` (testy si vytvárajú vlastné `Settings`)."""
    return Settings()
