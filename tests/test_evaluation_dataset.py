"""Check evaluation references, not retrieval performance or answer correctness."""

import json
from pathlib import Path

import pytest

from backend.markdown import headings

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data"
DATASET = json.loads((ROOT / "tests" / "evaluation_queries.json").read_text(encoding="utf-8"))
CASES = DATASET["cases"]


def test_evaluation_ids_are_unique():
    assert DATASET["schema_version"] == 1
    assert CASES
    assert len({case["id"] for case in CASES}) == len(CASES)


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_evaluation_case_has_valid_sources_and_verbatim_evidence(case):
    assert case["question"].strip()
    assert case["category"].strip()
    assert case["answer_mode"] in {"answer", "partial_answer", "correct_premise", "abstain"}
    assert case["required_facts"]
    assert all(isinstance(fact, str) and fact.strip() for fact in case["required_facts"])
    assert case["forbidden_claims"]
    assert all(isinstance(claim, str) and claim.strip() for claim in case["forbidden_claims"])
    sources = case["expected_sources"]
    assert len(sources) == len(set(sources))
    assert set(sources) == {item["source"] for item in case["evidence"]}
    if not sources:
        assert case["answer_mode"] == "abstain"
        assert case["review_note"].strip()

    for source in sources:
        path = (DATA_ROOT / source).resolve()
        assert path.is_relative_to(DATA_ROOT.resolve())
        assert not path.name.startswith("example_")
        assert path.is_file()

    for evidence in case["evidence"]:
        text = (DATA_ROOT / evidence["source"]).read_text(encoding="utf-8")
        # A source edit should prompt review of affected expectations.
        assert evidence["quote"] and evidence["quote"] in text
        sections = list(headings(text))
        matching_sections = []
        for index, (start, _, title) in enumerate(sections):
            end = sections[index + 1][0] if index + 1 < len(sections) else len(text)
            if title == evidence["section"]:
                matching_sections.append(text[start:end])
        assert any(evidence["quote"] in section for section in matching_sections)
