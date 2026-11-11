"""Načítanie katalógov z YAML (TASK §5.4, PLANNING D5, D8, D9).

- `codes.yaml` — celý číselník (82 kódov), kandidáti na výber v Settings;
- `top10.yaml` — predvolene aktívne kódy (10 ST + Other, 10 Q + Other), ich kategórie a názvy kategórií;
- `links.yaml` — páry same_process;
- `example_shift_model.yaml` — iba príklad z prezentácie (tlačidlo „Fill with example", demo, testy);
  `load_example_settings` pridáva produkt a grace.

Katalóg sa pri načítaní overí; chyba = `CatalogError`. Súbory sa čítajú v UTF-8 cez cestu voči tomuto modulu.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from oee.domain.shift_model import ShiftModelConfig, ShiftModelError, config_from_snapshot
from oee.domain.validation import ActiveCodes

CATALOG_DIR = Path(__file__).resolve().parent
TOP10_SIZE = 10  # TASK §5.4: Top-10 ST a Top-10 Q
OTHER_CATEGORY = "other"

Kind = Literal["stop", "defect"]
LinkType = Literal["same_process", "cross_process"]


class CatalogError(ValueError):
    """Katalóg (YAML) je nekonzistentný."""


@dataclass(frozen=True)
class Code:
    code: str
    kind: Kind
    category: str
    """Kategória z číselníka (Excel)."""
    name_en: str
    name_sk: str


@dataclass(frozen=True)
class ProcessLink:
    name: str
    stop_categories: frozenset[str]
    defects: frozenset[str]


@dataclass(frozen=True)
class Catalog:
    codes: Mapping[str, Code]
    categories: Mapping[str, str]
    """id kategórie → zobrazovaný názov."""
    top10_stop: tuple[str, ...]
    top10_defect: tuple[str, ...]
    other_stop: str
    other_defect: str
    top10_categories: Mapping[str, str]
    """Kategória kódov Top-10 a Other — má prednosť pred číselníkom (D9)."""
    processes: tuple[ProcessLink, ...]

    def category_of(self, code: str) -> str:
        if code in self.top10_categories:
            return self.top10_categories[code]
        return self.codes[code].category

    def category_name(self, code: str) -> str:
        return self.categories[self.category_of(code)]

    def active_codes(self) -> ActiveCodes:
        return ActiveCodes(
            stop_codes=frozenset(self.top10_stop),
            defect_codes=frozenset(self.top10_defect),
            other_stop_code=self.other_stop,
            other_defect_code=self.other_defect,
        )

    def link_type(self, stop_code: str, defect_code: str) -> tuple[LinkType, str | None]:
        """(`same_process`, názov procesu) alebo (`cross_process`, None)."""
        process = self.process_for_category(self.category_of(stop_code), defect_code)
        return ("same_process", process) if process else ("cross_process", None)

    def process_for_category(self, stop_category: str, defect_code: str) -> str | None:
        """Proces, do ktorého patrí kategória prestoja aj zmätok (aj pre kód pridaný v Settings, D15)."""
        for p in self.processes:
            if stop_category in p.stop_categories and defect_code in p.defects:
                return p.name
        return None


# --- načítanie ----------------------------------------------------------------------------------


def _read_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise CatalogError(f"cannot read {path.name}: {exc}") from exc


def _load_codes(data: Any) -> dict[str, Code]:
    codes: dict[str, Code] = {}
    for item in data["codes"]:
        code = Code(
            code=item["code"],
            kind=item["kind"],
            category=item["category"],
            name_en=item["name_en"],
            name_sk=item["name_sk"],
        )
        if code.kind not in ("stop", "defect"):
            raise CatalogError(f"{code.code}: unknown kind {code.kind!r}")
        if code.code in codes:
            raise CatalogError(f"duplicate code {code.code}")
        codes[code.code] = code
    return codes


def _check_top10(
    entries: list[dict[str, str]],
    other: str,
    kind: Kind,
    codes: Mapping[str, Code],
    categories: Mapping[str, str],
) -> None:
    listed = [e["code"] for e in entries]
    if len(listed) != TOP10_SIZE:
        raise CatalogError(f"Top-10 {kind} must have exactly {TOP10_SIZE} codes, has {len(listed)}")
    if len(set(listed)) != len(listed) or other in listed:
        raise CatalogError(f"Top-10 {kind} contains duplicate codes")
    for e in entries:
        code = e["code"]
        if code not in codes:
            raise CatalogError(f"Top-10 {kind}: {code} is not in codes.yaml")
        if codes[code].kind != kind:
            raise CatalogError(f"Top-10 {kind}: {code} is a {codes[code].kind} code")
        if e["category"] not in categories:
            raise CatalogError(f"Top-10 {kind}: {code} has unknown category {e['category']!r}")
    if other not in codes or codes[other].kind != kind or codes[other].category != OTHER_CATEGORY:
        raise CatalogError(
            f"Other {kind} code {other!r} must be a {kind} code with category {OTHER_CATEGORY!r}"
        )


def load_catalog(base: Path = CATALOG_DIR) -> Catalog:
    try:
        codes = _load_codes(_read_yaml(base / "codes.yaml"))
        top = _read_yaml(base / "top10.yaml")
        links = _read_yaml(base / "links.yaml")
        categories: dict[str, str] = dict(top["categories"])

        unknown = {c.category for c in codes.values()} - set(categories)
        if unknown:
            raise CatalogError(f"codes.yaml uses unknown categories {sorted(unknown)}")

        _check_top10(top["stop"], top["other_stop"], "stop", codes, categories)
        _check_top10(top["defect"], top["other_defect"], "defect", codes, categories)

        top10_categories = {e["code"]: e["category"] for e in [*top["stop"], *top["defect"]]}
        top10_categories[top["other_stop"]] = OTHER_CATEGORY
        top10_categories[top["other_defect"]] = OTHER_CATEGORY

        processes = []
        for p in links["processes"]:
            link = ProcessLink(p["name"], frozenset(p["stop_categories"]), frozenset(p["defects"]))
            if not link.stop_categories <= set(categories):
                raise CatalogError(f"links.yaml: process {link.name} has unknown categories")
            if any(d not in codes or codes[d].kind != "defect" for d in link.defects):
                raise CatalogError(f"links.yaml: process {link.name} lists an unknown defect code")
            processes.append(link)
    except (KeyError, TypeError) as exc:
        raise CatalogError(f"malformed catalog: {exc!r}") from exc

    return Catalog(
        codes=codes,
        categories=categories,
        top10_stop=tuple(e["code"] for e in top["stop"]),
        top10_defect=tuple(e["code"] for e in top["defect"]),
        other_stop=top["other_stop"],
        other_defect=top["other_defect"],
        top10_categories=top10_categories,
        processes=tuple(processes),
    )


def load_example_shift_model(path: Path = CATALOG_DIR / "example_shift_model.yaml") -> ShiftModelConfig:
    """Príkladový model zmeny z prezentácie (D8) — rovnaký tvar ako snapshot, overený doménovou validáciou."""
    data = _read_yaml(path)
    if not isinstance(data, dict):
        raise CatalogError(f"{path.name}: expected a mapping")
    try:
        return config_from_snapshot(data)
    except ShiftModelError as exc:
        raise CatalogError(f"{path.name}: {exc}") from exc


@dataclass(frozen=True)
class ExampleSettings:
    """Príklad pre tlačidlo „Fill with example" v Settings: model zmeny + produkt a grace (D8)."""

    config: ShiftModelConfig
    product: str
    grace_min: int


def load_example_settings(path: Path = CATALOG_DIR / "example_shift_model.yaml") -> ExampleSettings:
    config = load_example_shift_model(path)
    data = _read_yaml(path)
    product, grace = data.get("product"), data.get("grace_min")
    if not isinstance(product, str) or not product.strip():
        raise CatalogError(f"{path.name}: product must be a non-empty string")
    if not isinstance(grace, int) or isinstance(grace, bool) or grace < 0:
        raise CatalogError(f"{path.name}: grace_min must be a non-negative integer")
    return ExampleSettings(config, product.strip(), grace)
