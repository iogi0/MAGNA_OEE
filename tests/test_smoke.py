"""Smoke test: balík sa dá importovať (overenie nástrojov v P0-01)."""

import oee


def test_package_imports() -> None:
    assert oee.__version__
