from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def fingerprint(record):
    payload = json.dumps(record, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def candidate_is_valid(candidate, source_ids, existing_slugs):
    errors = []
    slug = candidate.get("slug", "")
    if not slug or slug in existing_slugs:
        errors.append("missing_or_duplicate_slug")
    if not candidate.get("title") or not candidate.get("sections"):
        errors.append("missing_title_or_sections")
    for source_id in candidate.get("source_ids", []):
        if source_id not in source_ids:
            errors.append(f"unknown_source:{source_id}")
    text = json.dumps(candidate).lower()
    for blocked in ["star rating", "customer review", "in stock", "sale", "discount", "lowest price"]:
        if blocked in text:
            errors.append(f"volatile_or_forbidden_claim:{blocked}")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="reports")
    args = parser.parse_args()
    out = (ROOT / args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    automation = load("automation.json")
    sources = {item["id"] for item in load("sources.json")}
    pages = load("pages.json")
    tools = load("tools.json")
    queue = load("content_queue.json")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kill_switch": automation.get("kill_switch"),
        "max_incremental_cost_usd": automation.get("max_incremental_cost_usd"),
        "paid_apis_allowed": automation.get("paid_apis_allowed"),
        "retry_limit": automation.get("retry_limit"),
        "queue_seen": len(queue),
        "accepted": [],
        "retried": [],
        "discarded": [],
        "duplicates_blocked": [],
        "status": "ok",
    }

    if automation.get("kill_switch"):
        report["status"] = "skipped_by_kill_switch"
    else:
        existing_slugs = {item["slug"] for item in pages} | {item["slug"] for item in tools}
        existing_fingerprints = {fingerprint(item) for item in pages}
        for candidate in queue:
            cid = candidate.get("slug", "unknown")
            if fingerprint(candidate) in existing_fingerprints:
                report["duplicates_blocked"].append(cid)
                continue
            final_errors = []
            for attempt in range(automation.get("retry_limit", 1) + 1):
                final_errors = candidate_is_valid(candidate, sources, existing_slugs)
                if not final_errors:
                    report["accepted"].append(cid)
                    existing_slugs.add(cid)
                    existing_fingerprints.add(fingerprint(candidate))
                    break
                if attempt < automation.get("retry_limit", 1):
                    report["retried"].append({"slug": cid, "attempt": attempt + 1, "errors": final_errors})
            else:
                report["discarded"].append({"slug": cid, "errors": final_errors})

    (out / "automation-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
