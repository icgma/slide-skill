"""Local-renderer decision gate tests (LOC-01/LOC-02).

Pins the decision artifact's discoverable path, its defer status, the three
REDESIGN_v5 Phase 5 triggers, and the build contract constraints.
"""
from __future__ import annotations

from pathlib import Path

import pytest

DECISION_PATH = Path(__file__).resolve().parents[1] / "benchmarks" / "local-renderer-decision.md"


@pytest.fixture(scope="module")
def decision_text() -> str:
    assert DECISION_PATH.exists(), f"decision artifact missing at {DECISION_PATH}"
    return DECISION_PATH.read_text(encoding="utf-8")


class TestLocDecision:
    def test_artifact_exists_at_discoverable_path(self, decision_text):
        assert "local-renderer-decision" in str(DECISION_PATH)

    def test_defer_is_the_recorded_decision(self, decision_text):
        assert "DEFER" in decision_text
        assert "NO-BUILD" in decision_text

    def test_all_three_triggers_are_evaluated(self, decision_text):
        for trigger in (
            "confirmed core need",
            "quality or cost targets",
            "outperforms the AI path",
        ):
            assert trigger in decision_text

    def test_evidence_status_references_the_bench04_manifest(self, decision_text):
        assert "six-family-manifest.json" in decision_text
        assert "benchmark-briefs --yes" in decision_text

    def test_build_contract_constraints_are_binding(self, decision_text):
        # LOC-02: the conditional contract is recorded even though not triggered.
        assert "no new `semantic_shape.py`" in decision_text
        assert "comparison" in decision_text and "metric-highlight" in decision_text
        assert "text_wrap.py" in decision_text
        assert "not declared the production default" in decision_text

    def test_no_local_slice_was_built(self):
        # LOC-02 antecedent is false: no semantic_shape module may exist.
        import slide_skill

        package_dir = Path(slide_skill.__file__).parent
        assert not (package_dir / "semantic_shape.py").exists()
