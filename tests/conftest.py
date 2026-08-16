"""Shared test fixtures.

Browser discovery is defaulted to "not found" so every browser-dependent
path (publish render gate GATE-01, validated-repair render gate QA-03, DOM
geometry measurement BENCH-03, gate-deck render smoke GATE-03) takes its
honest no-browser branch — real logic, deterministic outcome, no
headless-Chrome cost per unit test.

Tests that need a (fake or real) browser override this by patching the
discovery/measurement functions themselves — a test-level monkeypatch
overrides the autouse default (last write wins). Tests marked
``@pytest.mark.real_browser`` are exempt and use the host's actual Chrome
(the committed measurement-contract render scenarios).
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _hermetic_no_browser(monkeypatch, request):
    if request.node.get_closest_marker("real_browser"):
        return
    import slide_skill.chrome_geometry as chrome_geometry
    import slide_skill.measurement_contracts as mc

    monkeypatch.setattr(chrome_geometry, "find_chrome", lambda: None)
    monkeypatch.setattr(mc, "_find_browser", lambda: None)
