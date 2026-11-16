"""P0-01: architektonické pravidlá (CLAUDE.md, ARCHITECTURE §3).

- `domain` je čistý Python: žiadne importy iných vrstiev ani IO / web / DB knižníc.
- V `src/` nie sú cloudové AI knižnice ani URL mimo localhost (vendorované assety sa neskenujú).
- Závislosti v `pyproject.toml` neobsahujú cloudové AI SDK.
"""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "oee"
VENDOR = SRC / "web" / "static" / "vendor"

DOMAIN_FORBIDDEN = (
    "oee.persistence",
    "oee.services",
    "oee.web",
    "oee.ai",
    "oee.catalog",
    "oee.config",
    "pandas",
    "httpx",
    "requests",
    "urllib",
    "socket",
    "sqlalchemy",
    "sqlite3",
    "fastapi",
    "starlette",
    "jinja2",
    "uvicorn",
    "openpyxl",
    "yaml",
    "pydantic_settings",
)

CLOUD_AI_FORBIDDEN = (
    "anthropic",
    "openai",
    "google.generativeai",
    "google.genai",
    "google.ai",
    "vertexai",
    "cohere",
    "mistralai",
    "groq",
    "together",
    "replicate",
    "huggingface_hub",
    "langchain_openai",
    "langchain_anthropic",
    "langchain_google_genai",
    "litellm",
)
CLOUD_AI_PACKAGES = {
    "anthropic",
    "openai",
    "google-generativeai",
    "google-genai",
    "google-cloud-aiplatform",
    "cohere",
    "mistralai",
    "groq",
    "together",
    "replicate",
    "huggingface-hub",
    "langchain-openai",
    "langchain-anthropic",
    "langchain-google-genai",
    "litellm",
}

LOCAL_HOSTS = {"localhost", "127.0.0.1"}
URL_RE = re.compile(r"\b[a-z][a-z0-9+.-]*://([^/\s\"'<>:?#]+)", re.IGNORECASE)


# --- pomocné funkcie ---------------------------------------------------------------------------


def module_name(path: Path) -> str:
    rel = path.relative_to(SRC.parent).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def imported_modules(source: str, current_module: str, is_package: bool = False) -> set[str]:
    """Absolútne názvy importovaných modulov (vrátane rozlíšených relatívnych importov)."""
    found: set[str] = set()
    package = current_module if is_package else current_module.rpartition(".")[0]
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base_parts = package.split(".")
                base_parts = base_parts[: len(base_parts) - (node.level - 1)]
                base = ".".join(base_parts)
                mod = f"{base}.{node.module}" if node.module else base
            else:
                mod = node.module or ""
            found.add(mod)
            found.update(f"{mod}.{alias.name}" for alias in node.names)
    return found


def violations(modules: set[str], forbidden: tuple[str, ...]) -> set[str]:
    return {m for m in modules for f in forbidden if m == f or m.startswith(f + ".")}


def non_local_hosts(text: str) -> set[str]:
    return {h for h in URL_RE.findall(text) if h.lower() not in LOCAL_HOSTS}


def python_files(base: Path) -> list[Path]:
    return [p for p in base.rglob("*.py") if VENDOR not in p.parents]


# --- samotné detektory musia fungovať -----------------------------------------------------------


def test_detector_finds_absolute_and_relative_imports() -> None:
    src = "import httpx\nfrom ..persistence import db\nfrom . import kpi\nfrom openai import OpenAI\n"
    mods = imported_modules(src, "oee.domain.kpi")
    assert violations(mods, DOMAIN_FORBIDDEN) == {"httpx", "oee.persistence", "oee.persistence.db"}
    assert violations(mods, CLOUD_AI_FORBIDDEN) == {"openai", "openai.OpenAI"}
    assert "oee.domain.kpi" in mods


def test_detector_relative_import_from_package_init() -> None:
    mods = imported_modules("from ..web import app\n", "oee.domain", is_package=True)
    assert "oee.web" in mods


def test_detector_does_not_flag_similar_names() -> None:
    assert violations({"oee.domain.ai_facts", "httpxlike"}, DOMAIN_FORBIDDEN) == set()


def test_detector_finds_non_local_urls() -> None:
    text = 'a = "http://127.0.0.1:11434"; b = "http://localhost/x"; c = "https://api.openai.com/v1"'
    assert non_local_hosts(text) == {"api.openai.com"}


# --- pravidlá nad skutočným kódom ---------------------------------------------------------------


@pytest.mark.parametrize("path", python_files(SRC / "domain"), ids=lambda p: p.name)
def test_domain_has_no_forbidden_imports(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    mods = imported_modules(source, module_name(path), is_package=path.name == "__init__.py")
    assert violations(mods, DOMAIN_FORBIDDEN) == set()


@pytest.mark.parametrize("path", python_files(SRC), ids=lambda p: str(p.relative_to(SRC)))
def test_no_cloud_ai_imports(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    mods = imported_modules(source, module_name(path), is_package=path.name == "__init__.py")
    assert violations(mods, CLOUD_AI_FORBIDDEN) == set()


@pytest.mark.parametrize("path", python_files(SRC), ids=lambda p: str(p.relative_to(SRC)))
def test_no_non_local_urls_in_source(path: Path) -> None:
    assert non_local_hosts(path.read_text(encoding="utf-8")) == set()


def test_env_example_has_only_local_urls() -> None:
    assert non_local_hosts((ROOT / ".env.example").read_text(encoding="utf-8")) == set()


def test_no_cloud_ai_dependencies() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = data["project"]
    deps = list(project["dependencies"])
    for extra in project.get("optional-dependencies", {}).values():
        deps.extend(extra)
    names = {re.split(r"[\s\[<>=!~;]", d, maxsplit=1)[0].lower().replace("_", "-") for d in deps}
    assert names & CLOUD_AI_PACKAGES == set()


def web_asset_files() -> list[Path]:
    web = SRC / "web"
    return [
        p
        for pattern in ("templates/**/*.html", "static/**/*.js", "static/**/*.css")
        for p in web.glob(pattern)
        if VENDOR not in p.parents
    ]


def test_web_assets_exist_to_scan() -> None:
    assert any(p.suffix == ".html" for p in web_asset_files())


@pytest.mark.parametrize("path", web_asset_files(), ids=lambda p: str(p.relative_to(SRC)))
def test_no_non_local_urls_in_templates_and_static(path: Path) -> None:
    # demo musí fungovať offline (CLAUDE.md Konvencie, ARCHITECTURE §10.7); vendor sa neskenuje
    assert non_local_hosts(path.read_text(encoding="utf-8")) == set()
