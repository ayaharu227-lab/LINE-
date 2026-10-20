"""Publish the independent review and fail closed unless every gate passes."""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


LIMITS = {"first_impression": 20, "daily_utility": 20, "contradiction_comedy": 20,
          "character_consistency": 15, "readability": 10,
          "originality_series": 10, "technical_safety": 5}
ASSETS = {f"{n:02d}" for n in range(1, 25)} | {"main", "tab", "preview_light", "preview_dark"}
AUTHORS = {"claude[bot]", "github-actions[bot]"}


class GateError(ValueError):
    pass


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise GateError("Duplicate JSON keys in review gate")
        result[key] = value
    return result


def evaluate(review, head_sha):
    if not re.fullmatch(r"[0-9a-f]{40}", head_sha):
        raise GateError("Invalid current head SHA")
    blocks = re.findall(r"<!--\s*claude-review-gate\s*\n(.*?)\n\s*-->", review, re.S)
    if len(blocks) != 1:
        raise GateError("Exactly one structured review gate is required")
    try:
        gate = json.loads(blocks[0], object_pairs_hook=unique_object)
    except (json.JSONDecodeError, TypeError):
        raise GateError("Invalid review gate JSON") from None
    fields = {"head_sha", "score", "scores", "critical_checks", "inspected_assets", "verdict"}
    if not isinstance(gate, dict) or set(gate) != fields:
        raise GateError("Review gate fields are incomplete or unexpected")
    if gate["head_sha"] != head_sha:
        raise GateError("Review is for a different commit")
    scores = gate["scores"]
    if not isinstance(scores, dict) or set(scores) != set(LIMITS):
        raise GateError("All seven score categories are required")
    if any(type(scores[key]) is not int or not 0 <= scores[key] <= cap for key, cap in LIMITS.items()):
        raise GateError("Score category is outside its allocation")
    if type(gate["score"]) is not int or gate["score"] != sum(scores.values()):
        raise GateError("Total does not equal the sum of category scores")
    checks = gate["critical_checks"]
    if (not isinstance(checks, dict) or set(checks) != {str(n) for n in range(1, 10)}
            or any(value not in ("PASS", "FAIL") for value in checks.values())):
        raise GateError("Exactly nine PASS/FAIL critical checks are required")
    assets = gate["inspected_assets"]
    if (not isinstance(assets, list) or any(type(value) is not str for value in assets)
            or len(assets) != len(ASSETS) or set(assets) != ASSETS):
        raise GateError("Inspection of all 24 stickers, main/tab and both previews is required")
    verdict = gate["verdict"]
    if verdict not in ("APPROVE", "REQUEST_CHANGES", "BLOCK"):
        raise GateError("Explicit final verdict is required")
    if not review.strip() or review.strip().splitlines()[-1].strip() != verdict:
        raise GateError("Final verdict conflicts with the structured gate")
    failures = []
    if gate["score"] < 88:
        failures.append("score_below_88")
    if any(value != "PASS" for value in checks.values()):
        failures.append("critical_defect_failed")
    if verdict != "APPROVE":
        failures.append("reviewer_did_not_approve")
    return {"approved": not failures, "head_sha": head_sha, "score": gate["score"],
            "critical_checks": checks, "verdict": verdict, "failures": failures}


def current_bot_review(comments, head_sha):
    marker = "<!-- claude-product-review:" + head_sha + " -->"
    matches = [item.get("body", "") for item in comments
               if item.get("user", {}).get("login") in AUTHORS
               and item.get("body", "").startswith(marker)]
    if len(matches) > 1:
        raise GateError("Multiple bot reviews for this commit; resolve the conflict")
    return matches[0] if matches else None


def transcript_review(path):
    try:
        events = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise GateError("Claude execution file is missing or invalid") from None
    if not isinstance(events, list):
        raise GateError("Claude execution events are invalid")
    result = next((event for event in reversed(events)
                   if isinstance(event, dict) and event.get("type") == "result"), {})
    if result.get("is_error") is not False or result.get("subtype") != "success":
        raise GateError("Claude execution did not succeed")
    text = result.get("result")
    if not isinstance(text, str) or not text.strip():
        raise GateError("Claude did not return a review")
    return text


def main():
    sha = os.environ["REVIEW_SHA"]
    report = {"approved": False, "head_sha": sha}
    try:
        repo, pr = os.environ["REVIEW_REPO"], os.environ["REVIEW_PR"]
        pages = json.loads(subprocess.check_output([
            "gh", "api", "--paginate", "--slurp", f"repos/{repo}/issues/{pr}/comments?per_page=100"]))
        comments = [item for page in pages for item in page]
        review = current_bot_review(comments, sha)
        if review is None:
            review = transcript_review(os.environ.get("REVIEW_FILE", ""))
            report = evaluate(review, sha)  # Never publish an incomplete fallback.
            marker = "<!-- claude-product-review:" + sha + " -->"
            with tempfile.TemporaryDirectory() as directory:
                body = Path(directory) / "review.md"
                body.write_text(marker + "\n\n" + review, encoding="utf-8")
                subprocess.run(["gh", "pr", "comment", pr, "--repo", repo,
                                "--body-file", str(body)], check=True, stdout=subprocess.DEVNULL)
        else:
            report = evaluate(review, sha)
    except GateError as error:
        report["failures"] = [str(error)]  # All GateError messages are static.
    except (OSError, ValueError, subprocess.SubprocessError):
        report["approved"] = False
        report["failures"] = ["Review retrieval or publication failed"]
    encoded = json.dumps(report, indent=2, sort_keys=True)
    Path("claude-review-gate.json").write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as output:
            output.write("\n### Independent product acceptance\n\n```json\n" + encoded + "\n```\n")
    return 0 if report["approved"] else 1


if __name__ == "__main__":
    sys.exit(main())
