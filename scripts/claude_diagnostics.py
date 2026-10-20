"""Minimal API preflight and allowlisted Claude Action failure diagnostics.

Never print API keys, raw API bodies, prompts, tool results, or transcripts.
The preflight performs at most one one-token request and never retries.
"""

import argparse
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request


def classify(text, status=None):
    text = str(text).lower()
    if "credit balance" in text:
        return "credit_balance_rejected"
    if "spend limit" in text or "usage limit" in text:
        return "spend_limit_reached"
    if status == 401 or "authentication_error" in text or "invalid x-api-key" in text:
        return "authentication_failed"
    if status == 403 or "permission_error" in text:
        return "permission_denied"
    if status == 404 or "not_found_error" in text:
        return "model_or_endpoint_unavailable"
    if status == 429 or "rate_limit_error" in text:
        return "rate_limited"
    if (status and status >= 500) or "overloaded_error" in text:
        return "provider_unavailable"
    return "unclassified_provider_error"


def request_id(value):
    value = str(value or "")
    return value if re.fullmatch(r"req_[A-Za-z0-9_]{1,100}", value) else None


def api_report(status, body, header_request_id=None):
    error = body.get("error", {}) if isinstance(body, dict) else {}
    if not isinstance(error, dict):
        error = {}
    success = 200 <= status < 300 and isinstance(body, dict) and body.get("type") == "message"
    category = "ok" if success else classify(error.get("message", ""), status)
    # A finite set only: provider-supplied strings are never copied into output.
    known_types = {"invalid_request_error", "authentication_error", "permission_error",
                   "not_found_error", "rate_limit_error", "api_error", "overloaded_error"}
    return {"stage": "messages_api_preflight", "ok": success,
            "http_status": status, "category": category,
            "error_type": error.get("type") if error.get("type") in known_types else None,
            "request_id": request_id(header_request_id or (body.get("request_id") if isinstance(body, dict) else None)),
            "max_output_tokens": 1, "attempts": 1}


def emit(report, filename):
    encoded = json.dumps(report, indent=2, sort_keys=True)
    Path(filename).write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write("\n### Claude connection diagnostic\n\n```json\n" + encoded + "\n```\n")


def preflight():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        report = {"stage": "messages_api_preflight", "ok": False,
                  "category": "missing_repository_secret", "attempts": 0}
    else:
        payload = {"model": os.environ.get("REVIEW_MODEL", "claude-opus-5-5"),
                   "max_tokens": 1,
                   "messages": [{"role": "user", "content": "Reply OK."}]}
        req = urllib.request.Request("https://api.anthropic.com/v1/messages",
                                     data=json.dumps(payload).encode(), method="POST",
                                     headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                report = api_report(response.status, json.load(response), response.headers.get("request-id"))
        except urllib.error.HTTPError as error:
            try:
                body = json.loads(error.read())
            except (ValueError, OSError):
                body = {}
            report = api_report(error.code, body, error.headers.get("request-id"))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            report = {"stage": "messages_api_preflight", "ok": False,
                      "category": "network_or_invalid_response", "attempts": 1}
    emit(report, "claude-api-diagnostic.json")
    return 0 if report["ok"] else 1


def execution_report(events):
    if isinstance(events, dict):
        events = [events]
    if not isinstance(events, list):
        events = []
    events = [event for event in events if isinstance(event, dict)]
    result = next((event for event in reversed(events) if event.get("type") == "result"), {})
    failed = not result or result.get("is_error") is True or result.get("subtype") != "success"
    evidence = []
    for event in events:
        if event.get("type") in {"assistant", "result"}:
            for field in ("error", "errors", "result", "message"):
                evidence.append(str(event.get(field, "")))
    report = {"stage": "claude_action", "ok": not failed,
              "category": classify(" ".join(evidence)) if failed else "ok"}
    # Copy only typed scalar counters. No session content or model output.
    for field in ("duration_ms", "num_turns", "total_cost_usd"):
        value = result.get(field)
        if type(value) in (int, float) and value >= 0:
            report[field] = value
    return report


def execution():
    configured = os.environ.get("REVIEW_EXECUTION_FILE", "")
    path = Path(configured) if configured else Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "claude-execution-output.json"
    try:
        report = execution_report(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        report = {"stage": "claude_action", "ok": False,
                  "category": "execution_file_unavailable"}
    emit(report, "claude-action-diagnostic.json")
    return 0  # The action/preflight's original failure remains the job result.


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("preflight", "execution"))
    args = parser.parse_args()
    sys.exit(preflight() if args.stage == "preflight" else execution())
