import copy
import importlib.util
import json
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location("review_gate", Path(__file__).resolve().parents[1] / "scripts/validate_claude_review.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
SHA = "a" * 40


def valid_gate():
    return {"head_sha": SHA, "score": 88,
            "scores": {"first_impression": 18, "daily_utility": 18, "contradiction_comedy": 17,
                       "character_consistency": 13, "readability": 9,
                       "originality_series": 9, "technical_safety": 4},
            "critical_checks": {str(n): "PASS" for n in range(1, 10)},
            "inspected_assets": sorted(gate.ASSETS), "verdict": "APPROVE"}


def text(data, final=None):
    return ("Review narrative.\n<!-- claude-review-gate\n" + json.dumps(data) +
            "\n-->\n" + (final or data["verdict"]))


def test_accepts_88_only_with_all_checks_and_images():
    result = gate.evaluate(text(valid_gate()), SHA)
    assert result["approved"]
    assert result["score"] == 88


def test_substring_approve_never_accepts_old_82_review():
    old = "82/100, critical #2 FAIL. Do not APPROVE.\nREQUEST_CHANGES"
    with pytest.raises(gate.GateError):
        gate.evaluate(old, SHA)
    data = valid_gate()
    data["scores"]["first_impression"] -= 6
    data["score"] = 82
    result = gate.evaluate(text(data), SHA)
    assert not result["approved"]
    assert "score_below_88" in result["failures"]


@pytest.mark.parametrize("verdict", ["REQUEST_CHANGES", "BLOCK"])
def test_high_score_cannot_override_reviewer_rejection(verdict):
    data = valid_gate()
    data["verdict"] = verdict
    assert not gate.evaluate(text(data), SHA)["approved"]


def test_critical_fail_cannot_be_overridden_by_approve():
    data = valid_gate()
    data["critical_checks"]["2"] = "FAIL"
    result = gate.evaluate(text(data), SHA)
    assert not result["approved"]
    assert "critical_defect_failed" in result["failures"]


@pytest.mark.parametrize("change", [
    lambda data: data.update(head_sha="b" * 40),
    lambda data: data.update(score=100),
    lambda data: data["scores"].update(readability=True),
    lambda data: data["scores"].update(readability=11),
    lambda data: data["critical_checks"].pop("9"),
    lambda data: data["inspected_assets"].remove("24"),
    lambda data: data["inspected_assets"].remove("preview_dark"),
    lambda data: data["inspected_assets"].append("01"),
])
def test_incomplete_stale_or_inconsistent_evidence_fails_closed(change):
    data = valid_gate()
    change(data)
    with pytest.raises(gate.GateError):
        gate.evaluate(text(data), SHA)


def test_conflicting_verdicts_and_duplicate_json_are_rejected():
    with pytest.raises(gate.GateError):
        gate.evaluate(text(valid_gate(), final="BLOCK"), SHA)
    review = text(valid_gate()).replace('"score": 88,', '"score": 88, "score": 99,')
    with pytest.raises(gate.GateError):
        gate.evaluate(review, SHA)
    with pytest.raises(gate.GateError):
        gate.evaluate(text(valid_gate()) + "\n" + text(valid_gate()), SHA)


def test_only_current_commit_bot_comment_is_used():
    marker = "<!-- claude-product-review:" + SHA + " -->"
    forged = {"user": {"login": "some-user"}, "body": marker + text(valid_gate())}
    stale = {"user": {"login": "claude[bot]"}, "body": "<!-- claude-product-review:" + "b" * 40 + " -->"}
    real = {"user": {"login": "claude[bot]"}, "body": marker + text(valid_gate())}
    assert gate.current_bot_review([forged, stale], SHA) is None
    assert gate.current_bot_review([forged, stale, real], SHA) == real["body"]
    with pytest.raises(gate.GateError):
        gate.current_bot_review([real, copy.deepcopy(real)], SHA)


def test_success_subtype_with_is_error_true_cannot_publish(tmp_path):
    file = tmp_path / "execution.json"
    file.write_text(json.dumps([{"type": "result", "subtype": "success", "is_error": True,
                                 "result": text(valid_gate())}]))
    with pytest.raises(gate.GateError):
        gate.transcript_review(file)


def test_posted_comment_is_used_when_transcript_only_says_posted(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for key, value in {"REVIEW_SHA": SHA, "REVIEW_REPO": "owner/repo", "REVIEW_PR": "7"}.items():
        monkeypatch.setenv(key, value)
    comment = {"user": {"login": "claude[bot]"},
               "body": "<!-- claude-product-review:" + SHA + " -->\n" + text(valid_gate())}
    calls = []
    def api(args):
        calls.append(args)
        return json.dumps([[], [comment]]).encode()
    monkeypatch.setattr(gate.subprocess, "check_output", api)
    monkeypatch.setattr(gate.subprocess, "run", lambda *args, **kwargs: pytest.fail("duplicate publication"))
    assert gate.main() == 0
    assert "--paginate" in calls[0]
    assert json.loads((tmp_path / "claude-review-gate.json").read_text())["approved"]
