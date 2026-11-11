"""P0-06: katalóg — celý číselník, Top-10 ST / Q + Other, páry same_process, príkladový model zmeny.

TASK §5.4, PLANNING D5, D8, D9.
"""

from __future__ import annotations

from datetime import time
from pathlib import Path

import pytest
import yaml

from oee.catalog.loader import (
    CATALOG_DIR,
    CatalogError,
    load_catalog,
    load_example_settings,
    load_example_shift_model,
)
from oee.domain.shift_model import build_shift_plan, validate_shift_model

CAT = load_catalog()

TOP10_STOP = [
    "ST-038",
    "ST-016",
    "ST-046",
    "ST-047",
    "ST-001",
    "ST-017",
    "ST-020",
    "ST-026",
    "ST-032",
    "ST-040",
]
TOP10_DEFECT = ["Q-031", "Q-020", "Q-026", "Q-030", "Q-021", "Q-022", "Q-025", "Q-027", "Q-032", "Q-003"]
DATASET_STOP = {"ST-001", "ST-016", "ST-017", "ST-038", "ST-046", "ST-047"}
DATASET_DEFECT = {"Q-020", "Q-026", "Q-030", "Q-031"}


# --- číselník -----------------------------------------------------------------------------------


def test_codebook_has_82_codes() -> None:
    stops = [c for c in CAT.codes.values() if c.kind == "stop"]
    defects = [c for c in CAT.codes.values() if c.kind == "defect"]
    assert (len(stops), len(defects), len(CAT.codes)) == (48, 34, 82)


def test_st016_is_camera_in_corrected_codebook() -> None:
    assert CAT.codes["ST-016"].category == "camera"


def test_codes_have_both_names() -> None:
    c = CAT.codes["ST-038"]
    assert c.name_en == "Camera light module interrupted operation"
    assert c.name_sk == "Svetelný modul kamery prerušil činnosť"  # UTF-8 bez poškodenia
    assert all(c.name_en and c.name_sk for c in CAT.codes.values())


def test_every_code_category_is_known() -> None:
    assert {c.category for c in CAT.codes.values()} <= set(CAT.categories)


# --- Top-10 + Other -----------------------------------------------------------------------------


def test_top10_lists_match_task() -> None:
    assert list(CAT.top10_stop) == TOP10_STOP
    assert list(CAT.top10_defect) == TOP10_DEFECT
    assert (CAT.other_stop, CAT.other_defect) == ("ST-048", "Q-034")


def test_top10_codes_exist_with_right_kind() -> None:
    assert all(CAT.codes[c].kind == "stop" for c in [*CAT.top10_stop, CAT.other_stop])
    assert all(CAT.codes[c].kind == "defect" for c in [*CAT.top10_defect, CAT.other_defect])


def test_active_codes_are_ten_plus_other() -> None:
    active = CAT.active_codes()
    assert len(active.stop_codes) == 10 and len(active.defect_codes) == 10
    assert active.other_stop_code == "ST-048"
    assert active.other_defect_code == "Q-034"


def test_all_dataset_codes_are_in_top10() -> None:
    assert set(CAT.top10_stop) >= DATASET_STOP
    assert set(CAT.top10_defect) >= DATASET_DEFECT


@pytest.mark.parametrize(
    ("code", "category"),
    [
        ("ST-001", "material_shortage"),  # Top-10 má prednosť pred „General" z číselníka (D9)
        ("ST-017", "tool"),
        ("ST-038", "camera"),
        ("ST-016", "camera"),
        ("ST-046", "leak_test"),
        ("ST-020", "robot"),
        ("ST-026", "pressing"),
        ("ST-032", "screwdriving"),
        ("Q-003", "general"),
        ("ST-048", "other"),
        ("ST-002", "general"),  # mimo Top-10 → kategória číselníka
    ],
)
def test_effective_category(code: str, category: str) -> None:
    assert CAT.category_of(code) == category


@pytest.mark.parametrize(
    ("code", "name"),
    [
        ("ST-038", "Camera malfunction"),
        ("ST-046", "Leak test issue"),
        ("ST-001", "Material shortage"),
        ("ST-017", "Tool issue"),
    ],
)
def test_category_display_names_match_golden(code: str, name: str) -> None:
    assert CAT.category_name(code) == name


def test_unknown_code_raises() -> None:
    with pytest.raises(KeyError):
        CAT.category_of("ST-999")


# --- páry same_process (TASK §5.4, §8.6) --------------------------------------------------------


@pytest.mark.parametrize(
    ("stop", "defect", "expected"),
    [
        ("ST-038", "Q-030", ("same_process", "Camera")),
        ("ST-040", "Q-030", ("same_process", "Camera")),
        ("ST-046", "Q-031", ("same_process", "Leak test")),
        ("ST-047", "Q-032", ("same_process", "Leak test")),
        ("ST-032", "Q-025", ("same_process", "Screwdriving")),
        ("ST-032", "Q-027", ("same_process", "Screwdriving")),
        ("ST-026", "Q-022", ("same_process", "Pressing")),
        ("ST-020", "Q-003", ("same_process", "Robot")),
        ("ST-016", "Q-031", ("cross_process", None)),  # golden §12.8
        ("ST-047", "Q-030", ("cross_process", None)),
        ("ST-017", "Q-031", ("cross_process", None)),
        ("ST-046", "Q-020", ("cross_process", None)),
        ("ST-001", "Q-030", ("cross_process", None)),
    ],
)
def test_link_type(stop: str, defect: str, expected: tuple[str, str | None]) -> None:
    assert CAT.link_type(stop, defect) == expected


# --- príkladový model zmeny (D8) ----------------------------------------------------------------


def test_example_shift_model_passes_domain_validation() -> None:
    cfg = load_example_shift_model()
    assert validate_shift_model(cfg) == []
    assert cfg.rate_per_hour == 60
    assert cfg.start == time(6, 0)
    assert cfg.duration_min == 480
    assert (cfg.break_.minutes, cfg.break_.hour_no) == (30, 5)
    assert (cfg.am.minutes, cfg.am.hour_no) == (10, 1)
    assert cfg.target_oee == 0.85
    assert cfg.working_days == frozenset({0, 1, 2, 3, 4})


def test_example_shift_model_gives_target_440() -> None:
    from datetime import date

    assert build_shift_plan(load_example_shift_model(), date(2026, 11, 25)).target == pytest.approx(440)


# --- chybné katalógy sa odmietnu ----------------------------------------------------------------


def copy_catalog(tmp_path: Path) -> Path:
    for name in ("codes.yaml", "top10.yaml", "links.yaml"):
        (tmp_path / name).write_text((CATALOG_DIR / name).read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def edit_top10(base: Path, change: object) -> None:
    path = base / "top10.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    change(data)  # type: ignore[operator]
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def test_copied_catalog_loads(tmp_path: Path) -> None:
    assert load_catalog(copy_catalog(tmp_path)).top10_stop == CAT.top10_stop


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["stop"].pop(),  # iba 9 ST
        lambda d: d["defect"].append({"code": "Q-001", "category": "general"}),  # 11 Q
        lambda d: d["stop"].__setitem__(0, {"code": "ST-999", "category": "camera"}),  # neexistuje
        lambda d: d["stop"].__setitem__(0, {"code": "Q-001", "category": "general"}),  # zlý druh
        lambda d: d["stop"].__setitem__(1, {"code": "ST-038", "category": "camera"}),  # duplicita
        lambda d: d["stop"].__setitem__(0, {"code": "ST-038", "category": "nonsense"}),  # neznáma kategória
        lambda d: d.__setitem__("other_stop", "ST-038"),  # Other musí mať kategóriu other
    ],
    ids=["nine", "eleven", "unknown", "wrong_kind", "duplicate", "bad_category", "bad_other"],
)
def test_invalid_top10_rejected(tmp_path: Path, change: object) -> None:
    base = copy_catalog(tmp_path)
    edit_top10(base, change)
    with pytest.raises(CatalogError):
        load_catalog(base)


@pytest.mark.parametrize(
    "process",
    [
        {"name": "X", "stop_categories": ["nonsense"], "defects": ["Q-030"]},
        {"name": "X", "stop_categories": ["camera"], "defects": ["Q-999"]},
        {"name": "X", "stop_categories": ["camera"], "defects": ["ST-038"]},
    ],
    ids=["bad_category", "unknown_defect", "stop_as_defect"],
)
def test_invalid_links_rejected(tmp_path: Path, process: dict[str, object]) -> None:
    base = copy_catalog(tmp_path)
    path = base / "links.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["processes"].append(process)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    with pytest.raises(CatalogError):
        load_catalog(base)


@pytest.mark.parametrize(
    ("key", "value"),
    [("rate_per_hour", 0), ("duration_min", 450), ("start", "6h"), ("target_oee", None)],
)
def test_invalid_example_shift_model_rejected(tmp_path: Path, key: str, value: object) -> None:
    data = yaml.safe_load((CATALOG_DIR / "example_shift_model.yaml").read_text(encoding="utf-8"))
    data[key] = value
    path = tmp_path / "model.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(CatalogError):
        load_example_shift_model(path)


def test_example_settings_include_product_and_grace() -> None:
    example = load_example_settings()
    assert example.config == load_example_shift_model()
    assert (example.product, example.grace_min) == ("P01", 60)  # TASK §4.3: grace predvolene 60 min


@pytest.mark.parametrize(("key", "value"), [("product", ""), ("grace_min", -1), ("grace_min", "x")])
def test_invalid_example_settings_rejected(tmp_path: Path, key: str, value: object) -> None:
    data = yaml.safe_load((CATALOG_DIR / "example_shift_model.yaml").read_text(encoding="utf-8"))
    data[key] = value
    path = tmp_path / "model.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(CatalogError):
        load_example_settings(path)


def test_process_for_category_works_without_code_in_catalog() -> None:
    catalog = load_catalog()
    # kód pridaný v Settings (D15) nie je v codes.yaml — proces sa určí z jeho kategórie v DB
    assert catalog.process_for_category("camera", "Q-030") == "Camera"
    assert catalog.process_for_category("general", "Q-030") is None
