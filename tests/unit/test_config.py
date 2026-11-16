"""P0-01: konfigurácia aplikácie (pydantic-settings, prefix OEE_, iba lokálny Ollama)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from oee.config import PROJECT_ROOT, Settings


def make(**kwargs: object) -> Settings:
    """Settings bez čítania vývojárovho .env (ARCHITECTURE §10.1)."""
    return Settings(_env_file=None, **kwargs)  # type: ignore[call-arg]


def test_project_root_contains_pyproject() -> None:
    assert (PROJECT_ROOT / "pyproject.toml").is_file()


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("OEE_DB_PATH", "OEE_DATASET_PATH", "OEE_OLLAMA_URL", "OEE_AI_LANG", "OEE_AI_ENABLED"):
        monkeypatch.delenv(name, raising=False)
    s = make()
    assert s.db_path == PROJECT_ROOT / "data" / "local" / "oee.db"
    assert s.dataset_path == PROJECT_ROOT / "data" / "raw" / "dummy_data.xlsx"
    assert s.ollama_url == "http://127.0.0.1:11434"
    assert s.ollama_model == "qwen2.5:3b"
    assert s.line_id == "L01"
    assert s.ai_enabled is True
    assert s.ai_lang == "en"
    assert s.ai_timeout_s > 0


def test_relative_path_resolves_against_project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)  # aktuálny priečinok nesmie hrať rolu
    s = make(db_path="some/dir/x.db")
    assert s.db_path == PROJECT_ROOT / "some" / "dir" / "x.db"


def test_absolute_path_is_kept(tmp_path: Path) -> None:
    target = tmp_path / "x.db"
    assert make(db_path=target).db_path == target


def test_env_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OEE_AI_LANG", "sk")
    monkeypatch.setenv("OEE_AI_ENABLED", "false")
    s = make()
    assert s.ai_lang == "sk"
    assert s.ai_enabled is False


def test_env_file_is_not_read_when_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / ".env"
    env.write_text("OEE_AI_LANG=sk\n", encoding="utf-8")
    monkeypatch.setitem(Settings.model_config, "env_file", env)  # predvolený .env podstrčíme
    monkeypatch.delenv("OEE_AI_LANG", raising=False)
    assert Settings().ai_lang == "sk"  # kontrola: predvolený súbor sa naozaj číta
    assert make().ai_lang == "en"  # _env_file=None ho vypne


def test_env_file_is_read_as_utf8(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / ".env"
    env.write_text("# komentár: žltý kôň\nOEE_AI_LANG=sk\n", encoding="utf-8")
    monkeypatch.delenv("OEE_AI_LANG", raising=False)
    s = Settings(_env_file=env)  # type: ignore[call-arg]
    assert s.ai_lang == "sk"


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:11434",
        "http://localhost:11434",
        "http://127.0.0.1:11434/",
        "http://LOCALHOST:8080",
    ],
)
def test_local_ollama_url_accepted(url: str) -> None:
    assert make(ollama_url=url).ollama_url == url.rstrip("/")


@pytest.mark.parametrize(
    "url",
    [
        "http://192.168.1.10:11434",
        "https://api.openai.com",
        "http://ollama.example.com:11434",
        "http://127.0.0.1.evil.com:11434",
        "http://localhost.evil.com",
        "http://user@evil.com:11434",
        "ftp://127.0.0.1:11434",
        "127.0.0.1:11434",
        "",
    ],
)
def test_non_local_ollama_url_rejected(url: str) -> None:
    with pytest.raises(ValidationError):
        make(ollama_url=url)


def test_non_local_ollama_url_rejected_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OEE_OLLAMA_URL", "http://10.0.0.5:11434")
    with pytest.raises(ValidationError):
        make()


@pytest.mark.parametrize("lang", ["uk", "de", "", "EN"])
def test_unknown_ai_lang_rejected(lang: str) -> None:
    with pytest.raises(ValidationError):
        make(ai_lang=lang)


@pytest.mark.parametrize("timeout", [0, -1])
def test_non_positive_timeout_rejected(timeout: float) -> None:
    with pytest.raises(ValidationError):
        make(ai_timeout_s=timeout)
