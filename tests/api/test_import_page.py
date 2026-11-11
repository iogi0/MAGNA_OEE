"""P0-18: Import cez UI = import cez službu; stránka ukáže počty a kontroly TASK §11.7."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from oee.config import PROJECT_ROOT, Settings
from oee.persistence.models import HourlyReportRow, IssueEvent, QualityRecord, Shift
from oee.web.app import create_app

DATASET = PROJECT_ROOT / "data" / "raw" / "dummy_data.xlsx"
needs_dataset = pytest.mark.skipif(not DATASET.is_file(), reason="dataset data/raw/dummy_data.xlsx missing")


def make_client(tmp_path: Path, dataset: Path) -> TestClient:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None, db_path=tmp_path / "oee.db", dataset_path=dataset, ai_enabled=False
    )
    return TestClient(create_app(settings))


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    with make_client(tmp_path, DATASET) as c:
        yield c


def text(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def counts(client: TestClient) -> tuple[int, int, int, int]:
    with client.app.state.session_factory() as s:  # type: ignore[attr-defined]
        return tuple(  # type: ignore[return-value]
            int(s.scalar(select(func.count()).select_from(m)) or 0)
            for m in (Shift, HourlyReportRow, IssueEvent, QualityRecord)
        )


def test_import_page_shows_dataset_and_button(client: TestClient) -> None:
    html = client.get("/import").text
    assert "dummy_data.xlsx" in html and 'action="/import"' in html and "Import dataset" in html
    assert counts(client) == (0, 0, 0, 0)  # GET nič neimportuje


@needs_dataset
def test_import_via_ui_equals_service_and_shows_counts_and_checks(client: TestClient) -> None:
    before = hashlib.sha256(DATASET.read_bytes()).hexdigest()
    r = client.post("/import")
    assert r.status_code == 200
    page = text(r.text)
    # TASK §11.2, §16 bod 3: 21 zmien / 168 hodín / 33 udalostí / 112 záznamov zmätkov
    for label, value in (("Shifts", 21), ("Hours", 168), ("Downtime events", 33), ("Reject records", 112)):
        assert f"{label} {value}" in page, label
    assert counts(client) == (21, 168, 33, 112)
    assert "21 / 21 shifts passed" in page  # kontroly TASK §11.7
    assert 'data-check="fail"' not in r.text
    assert "L01-20261125-M" in page and "60 pcs/h" in page  # odvodený model zmeny zo súboru
    assert hashlib.sha256(DATASET.read_bytes()).hexdigest() == before  # Excel sa neukladá (CLAUDE.md bod 9)


@needs_dataset
def test_repeated_import_adds_nothing(client: TestClient) -> None:
    client.post("/import")
    page = text(client.post("/import").text)
    assert "Shifts 0" in page and "Hours skipped (already imported) 168" in page
    assert counts(client) == (21, 168, 33, 112)


def test_missing_dataset_is_a_clear_error(tmp_path: Path) -> None:
    with make_client(tmp_path, tmp_path / "nope.xlsx") as c:
        page = c.get("/import").text
        assert "not found" in page and re.search(r"<button[^>]*disabled", page)
        r = c.post("/import")
        assert r.status_code == 422 and "Import failed" in r.text
        assert counts(c) == (0, 0, 0, 0)


def test_corrupt_dataset_is_a_clear_error_and_nothing_is_imported(tmp_path: Path) -> None:
    broken = tmp_path / "broken.xlsx"
    broken.write_bytes(b"this is not an excel file")
    with make_client(tmp_path, broken) as c:
        r = c.post("/import")
        assert r.status_code == 422 and "Import failed" in r.text
        assert counts(c) == (0, 0, 0, 0)


def test_failed_and_unverifiable_checks_are_shown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from oee.services import importer
    from oee.web import app as web_app

    fake = importer.ImportResult(
        shifts_added=2,
        checks=[
            importer.ShiftCheck("L01-20261201-M", {"plan_min": True, "downtime": False}),
            importer.ShiftCheck("L01-20261202-M", {"plan_min": True, "balance_s": None}),
        ],
    )
    monkeypatch.setattr(web_app, "import_excel", lambda *a, **k: fake)
    with make_client(tmp_path, tmp_path / "any.xlsx") as c:
        r = c.post("/import")
    assert "1 / 2 shifts passed" in text(r.text)
    assert r.text.count('data-check="fail"') == 1 and 'data-check="na"' in r.text


def test_example_file_link_and_download(tmp_path: Path) -> None:
    with make_client(tmp_path, tmp_path / "nope.xlsx") as c:  # vzor je dostupný aj bez datasetu
        html = c.get("/import").text
        button, link = html.index("Import dataset</button>"), html.index('href="/import/example.xlsx"')
        assert button < link  # odkaz je hneď pod tlačidlom
        r = c.get("/import/example.xlsx")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument.spreadsheetml")
    assert 'attachment; filename="oee_import_example.xlsx"' in r.headers["content-disposition"]
    assert r.content[:2] == b"PK"  # xlsx = zip
