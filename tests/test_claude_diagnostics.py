import importlib.util
import json
from pathlib import Path


spec = importlib.util.spec_from_file_location("diagnostics", Path(__file__).resolve().parents[1] / "scripts/claude_diagnostics.py")
diagnostics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostics)


def test_balance_and_spend_limit_are_distinct_from_auth():
    for message, category in (("Your credit balance is too low", "credit_balance_rejected"),
                              ("Organization spend limit reached", "spend_limit_reached")):
        report = diagnostics.api_report(400, {"error": {"type": "invalid_request_error", "message": message}})
        assert report["category"] == category
        assert not report["ok"]
    assert diagnostics.api_report(401, {})["category"] == "authentication_failed"


def test_reports_cannot_echo_secrets_prompts_or_untrusted_fields():
    secret = "sk-ant-test-secret-123"
    body = {"error": {"type": secret, "message": "invalid input " + secret}, "request_id": secret}
    report = diagnostics.api_report(400, body, secret)
    assert secret not in json.dumps(report)
    assert report["request_id"] is None
    event = {"type": "result", "subtype": "success", "is_error": True,
             "result": "Credit balance is too low " + secret,
             "num_turns": secret, "modelUsage": {"key": secret}}
    result = diagnostics.execution_report([event])
    assert result["category"] == "credit_balance_rejected"
    assert secret not in json.dumps(result)


def test_result_subtype_success_does_not_hide_is_error_true():
    event = {"type": "result", "subtype": "success", "is_error": True,
             "result": "Credit balance is too low", "total_cost_usd": 0, "num_turns": 1}
    report = diagnostics.execution_report([event])
    assert not report["ok"]
    assert report["total_cost_usd"] == 0
    assert report["category"] == "credit_balance_rejected"


def test_success_and_missing_result():
    assert diagnostics.api_report(200, {"type": "message"}, "req_valid_123")["ok"]
    assert diagnostics.execution_report([{"type": "result", "subtype": "success", "is_error": False}])["ok"]
    assert not diagnostics.execution_report([])["ok"]
    assert not diagnostics.execution_report("invalid")["ok"]


def test_preflight_never_calls_provider_without_secret(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(diagnostics.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("unexpected network")))
    assert diagnostics.preflight() == 1
    report = json.loads((tmp_path / "claude-api-diagnostic.json").read_text())
    assert report["category"] == "missing_repository_secret"
    assert report["attempts"] == 0


def test_execution_fallback_keeps_safe_error_evidence(monkeypatch, tmp_path):
    monkeypatch.delenv("REVIEW_EXECUTION_FILE", raising=False)
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    (tmp_path / "claude-execution-output.json").write_text(json.dumps([
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "Credit balance is too low"}]}},
        {"type": "result", "subtype": "success", "is_error": True, "total_cost_usd": 0}]))
    assert diagnostics.execution() == 0
    report = json.loads((tmp_path / "claude-action-diagnostic.json").read_text())
    assert report["category"] == "credit_balance_rejected"
