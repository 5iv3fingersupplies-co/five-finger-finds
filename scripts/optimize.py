from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PRIVATE_INPUTS = ROOT / os.environ.get("OPTIMIZATION_INPUT_DIR", "private-inputs")


def load_json(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def pick(row: dict[str, str], candidates: list[str]) -> str:
    normalized = {normalize_header(key): value for key, value in row.items()}
    for candidate in candidates:
        value = normalized.get(normalize_header(candidate))
        if value is not None:
            return value.strip()
    return ""


def parse_number(value: str) -> float:
    if not value:
        return 0.0
    cleaned = value.replace(",", "").replace("$", "").strip()
    if cleaned.endswith("%"):
        cleaned = cleaned[:-1]
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_ctr(value: str, clicks: float, impressions: float) -> float:
    if value:
        parsed = parse_number(value)
        return parsed / 100 if parsed > 1 else parsed
    if impressions:
        return clicks / impressions
    return 0.0


def canonical_path(raw_url: str, base_url: str) -> str:
    if not raw_url:
        return ""
    raw_url = raw_url.strip()
    if raw_url.startswith(base_url):
        raw_url = raw_url[len(base_url):]
    elif raw_url.startswith(base_url.rstrip("/")):
        raw_url = raw_url[len(base_url.rstrip("/")):]
    elif raw_url.startswith("http"):
        parsed = urlparse(raw_url)
        raw_url = parsed.path
        prefix = "/" + urlparse(base_url).path.strip("/")
        if raw_url.startswith(prefix):
            raw_url = raw_url[len(prefix):]
    raw_url = raw_url.split("?", 1)[0].split("#", 1)[0].strip("/")
    return raw_url or "index"


def page_path(kind: str, slug: str) -> str:
    if kind == "tool":
        return f"tools/{slug}"
    if kind == "guide":
        return f"guides/{slug}"
    return slug


def read_csvs(input_dir: Path, filenames: list[str]) -> tuple[list[dict[str, str]], list[str]]:
    rows: list[dict[str, str]] = []
    found: list[str] = []
    for filename in filenames:
        path = input_dir / filename
        if not path.exists():
            continue
        found.append(filename)
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows.extend(dict(row) for row in csv.DictReader(handle))
    return rows, found


def load_search_page_metrics(site: dict, input_dir: Path) -> tuple[dict[str, dict], list[str]]:
    rows, found = read_csvs(input_dir, [
        "search-console-pages.csv",
        "google-search-console-pages.csv",
        "gsc-pages.csv",
        "bing-pages.csv",
        "bing-webmaster-pages.csv",
    ])
    metrics: dict[str, dict] = {}
    for row in rows:
        url = pick(row, ["page", "top pages", "landing page", "url", "pages"])
        path = canonical_path(url, site["base_url"])
        if not path:
            continue
        clicks = parse_number(pick(row, ["clicks", "web clicks"]))
        impressions = parse_number(pick(row, ["impressions", "web impressions"]))
        ctr = parse_ctr(pick(row, ["ctr", "click through rate", "click-through rate"]), clicks, impressions)
        position = parse_number(pick(row, ["position", "average position", "avg position"]))
        current = metrics.setdefault(path, {"clicks": 0.0, "impressions": 0.0, "ctr": 0.0, "position": 0.0})
        previous_impressions = current["impressions"]
        current["clicks"] += clicks
        current["impressions"] += impressions
        if current["impressions"]:
            current["ctr"] = current["clicks"] / current["impressions"]
        if position:
            current["position"] = (
                ((current["position"] * previous_impressions) + (position * impressions))
                / current["impressions"]
                if current["impressions"]
                else position
            )
    return metrics, found


def load_search_query_metrics(input_dir: Path) -> tuple[list[dict], list[str]]:
    rows, found = read_csvs(input_dir, [
        "search-console-queries.csv",
        "google-search-console-queries.csv",
        "gsc-queries.csv",
        "bing-queries.csv",
        "bing-webmaster-queries.csv",
    ])
    metrics = []
    for row in rows:
        query = pick(row, ["query", "search query", "keyword"])
        if not query:
            continue
        clicks = parse_number(pick(row, ["clicks", "web clicks"]))
        impressions = parse_number(pick(row, ["impressions", "web impressions"]))
        ctr = parse_ctr(pick(row, ["ctr", "click through rate", "click-through rate"]), clicks, impressions)
        position = parse_number(pick(row, ["position", "average position", "avg position"]))
        metrics.append({
            "query": query,
            "clicks": clicks,
            "impressions": impressions,
            "ctr": ctr,
            "position": position,
            "opportunity_score": round((impressions * max(0.02 - ctr, 0) * 2) + (max(0, 25 - position) if position else 0), 2),
        })
    metrics.sort(key=lambda item: item["opportunity_score"], reverse=True)
    return metrics, found


def load_amazon_metrics(input_dir: Path) -> tuple[dict, list[str]]:
    rows, found = read_csvs(input_dir, [
        "amazon-associates.csv",
        "amazon-associates-report.csv",
        "amazon-links.csv",
    ])
    totals = {"clicks": 0.0, "ordered_items": 0.0, "earnings": 0.0, "rows": len(rows)}
    for row in rows:
        totals["clicks"] += parse_number(pick(row, ["clicks", "link clicks"]))
        totals["ordered_items"] += parse_number(pick(row, ["ordered items", "orders", "items ordered"]))
        totals["earnings"] += parse_number(pick(row, ["earnings", "fees", "commission", "advertising fees"]))
    totals["conversion_rate"] = round(totals["ordered_items"] / totals["clicks"], 4) if totals["clicks"] else 0.0
    totals["earnings_per_click"] = round(totals["earnings"] / totals["clicks"], 4) if totals["clicks"] else 0.0
    return totals, found


def collect_records(site: dict, tools: list[dict], guides: list[dict], recommendations: dict[str, dict]) -> list[dict]:
    records = []
    for tool in tools:
        records.append({
            "kind": "tool",
            "slug": tool["slug"],
            "path": page_path("tool", tool["slug"]),
            "url": f"{site['base_url'].rstrip('/')}/tools/{tool['slug']}/",
            "title": tool["title"],
            "description": tool["description"],
            "category": tool["category"],
            "source_ids": tool["source_ids"],
            "recommendation_ids": tool["recommendation_ids"],
            "monetized_slots": len(tool["recommendation_ids"]),
        })
    for guide in guides:
        related_recs = []
        for tool in tools:
            if tool["category"] == guide["category"] or any(src in tool["source_ids"] for src in guide["source_ids"]):
                related_recs.extend(tool["recommendation_ids"])
        records.append({
            "kind": "guide",
            "slug": guide["slug"],
            "path": page_path("guide", guide["slug"]),
            "url": f"{site['base_url'].rstrip('/')}/guides/{guide['slug']}/",
            "title": guide["title"],
            "description": guide["description"],
            "category": guide["category"],
            "source_ids": guide["source_ids"],
            "recommendation_ids": list(dict.fromkeys(related_recs))[:3],
            "monetized_slots": min(3, len(dict.fromkeys(related_recs))),
        })
    return records


def score_page(record: dict, performance: dict | None, category_counts: Counter) -> dict:
    score = 10 if record["kind"] == "tool" else 6
    reasons = []
    if record["kind"] == "tool":
        reasons.append("interactive tool page")
    if record["monetized_slots"]:
        score += record["monetized_slots"] * 2
        reasons.append(f"{record['monetized_slots']} monetized product-fit slots")
    if len(record["description"]) < 90:
        score += 2
        reasons.append("short description can be sharpened")
    if category_counts[record["category"]] <= 3:
        score += 3
        reasons.append("category has limited page depth")
    if performance:
        clicks = performance["clicks"]
        impressions = performance["impressions"]
        ctr = performance["ctr"]
        position = performance["position"]
        if impressions and ctr < 0.02:
            gain = min(35, impressions * (0.02 - ctr) * 2)
            score += gain
            reasons.append("impressions with low click-through rate")
        if position and 6 <= position <= 25:
            score += min(25, impressions / 50 if impressions else 8)
            reasons.append("ranking distance suggests refresh/internal-link opportunity")
        if clicks and record["monetized_slots"]:
            score += min(10, clicks / 10)
            reasons.append("traffic reaches monetized page")
    else:
        score += 4
        reasons.append("awaiting search performance data")
    return {
        "score": round(score, 2),
        "path": record["path"],
        "url": record["url"],
        "title": record["title"],
        "kind": record["kind"],
        "category": record["category"],
        "reasons": reasons[:4],
        "metrics": performance or {},
    }


def topic_coverage_score(topic: dict, corpus: str, category_counts: Counter) -> dict:
    terms = topic.get("coverage_terms", [])
    covered_terms = [term for term in terms if term.lower() in corpus]
    missing = len(covered_terms) == 0
    score = float(topic.get("priority", 1)) * (3 if missing else 0.75)
    if category_counts[topic.get("category", "")] <= 3:
        score += 4
    return {
        "score": round(score, 2),
        "id": topic["id"],
        "title": topic["title"],
        "suggested_slug": topic["suggested_slug"],
        "category": topic["category"],
        "missing": missing,
        "covered_terms": covered_terms,
        "reason": topic["reason"],
        "source_ids": topic["source_ids"],
        "recommendation_ids": topic["recommendation_ids"],
    }


def build_markdown(report: dict) -> str:
    lines = [
        "# Optimization Report",
        "",
        f"Generated: {report['generated_at']}",
        "",
        "## Inputs",
    ]
    for name, detail in report["inputs"].items():
        status = "found" if detail["found"] else "missing"
        files = ", ".join(detail["files"]) if detail["files"] else "none"
        lines.append(f"- {name}: {status} ({files})")
    lines.extend([
        "",
        "## Site Health",
        f"- Tools: {report['site']['tools']}",
        f"- Evergreen guides: {report['site']['guides']}",
        f"- Recommendation records: {report['site']['recommendations']}",
        f"- Categories: {', '.join(report['site']['categories'])}",
        "",
        "## Next Page Actions",
    ])
    for index, item in enumerate(report["top_page_actions"][:10], 1):
        reasons = "; ".join(item["reasons"])
        lines.append(f"{index}. {item['title']} ({item['path']}) - score {item['score']}: {reasons}")
    lines.extend(["", "## Seasonal Strategy"])
    for index, item in enumerate(report.get("seasonal_actions", [])[:10], 1):
        lines.append(f"{index}. {item['title']} ({item['path']}) - score {item['score']}: {item['reason']}")
    lines.extend(["", "## Source-Derived Actions"])
    for item in report.get("source_strategy_actions", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Content Gap Queue"])
    for index, item in enumerate(report["content_gap_actions"][:10], 1):
        status = "new gap" if item["missing"] else "covered, consider supporting angle"
        lines.append(f"{index}. {item['title']} - score {item['score']} ({status}): {item['reason']}")
    lines.extend(["", "## Private Data Note"])
    lines.append("Performance exports belong in gitignored private-inputs/ and are not required for the public scheduled report.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="reports")
    parser.add_argument("--input-dir", default=str(PRIVATE_INPUTS))
    args = parser.parse_args()

    out = (ROOT / args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    input_dir = Path(args.input_dir)

    site = load_json("site.json")
    tools = load_json("tools.json")
    guides = load_json("pages.json")
    recommendations = {item["id"]: item for item in load_json("recommendations.json")}
    topics = load_json("optimization_topics.json")
    editorial = load_json("editorial_calendar.json")
    editorial = load_json("editorial_calendar.json")
    editorial = load_json("editorial_calendar.json")
    editorial = load_json("editorial_calendar.json")

    page_metrics, page_files = load_search_page_metrics(site, input_dir)
    query_metrics, query_files = load_search_query_metrics(input_dir)
    amazon_metrics, amazon_files = load_amazon_metrics(input_dir)

    records = collect_records(site, tools, guides, recommendations)
    category_counts = Counter(record["category"] for record in records)
    page_actions = [
        score_page(record, page_metrics.get(record["path"]) or page_metrics.get(record["path"] + "/"), category_counts)
        for record in records
    ]
    page_actions.sort(key=lambda item: item["score"], reverse=True)

    corpus = json.dumps({"tools": tools, "guides": guides}, ensure_ascii=False).lower()
    content_gap_actions = [topic_coverage_score(topic, corpus, category_counts) for topic in topics]
    content_gap_actions.sort(key=lambda item: item["score"], reverse=True)
    seasonal_actions = []
    for entry in editorial.get("seasonal_pages", []):
        seasonal_actions.append({"score": 24 + len(entry.get("recommendation_ids", [])) * 2, "title": entry["title"], "path": f"seasonal/{entry['slug']}", "category": entry["category"], "reason": "seasonal buyer-intent page from supplied affiliate strategy"})
    seasonal_actions.sort(key=lambda item: item["score"], reverse=True)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok",
        "cost": {"incremental_usd": 0, "paid_apis_used": False},
        "inputs": {
            "search_pages": {"found": bool(page_files), "files": page_files},
            "search_queries": {"found": bool(query_files), "files": query_files},
            "amazon_associates": {"found": bool(amazon_files), "files": amazon_files},
        },
        "site": {
            "tools": len(tools),
            "guides": len(guides),
            "recommendations": len(recommendations),
            "categories": sorted(category_counts),
            "category_counts": dict(sorted(category_counts.items())),
            "seasonal_pages": len(editorial.get("seasonal_pages", [])),
            "traffic_channels": editorial.get("traffic_channels", []),
        },
        "amazon_summary": amazon_metrics,
        "top_queries": query_metrics[:20],
        "top_page_actions": page_actions[:20],
        "content_gap_actions": content_gap_actions[:20],
        "seasonal_actions": seasonal_actions[:20],
        "source_strategy_actions": editorial.get("source_action_items", []),
    }

    (out / "optimization-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (out / "optimization-report.md").write_text(build_markdown(report), encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "top_page_actions": len(report["top_page_actions"]),
        "content_gap_actions": len(report["content_gap_actions"]),
        "private_inputs_found": any(item["found"] for item in report["inputs"].values()),
        "out": str(out),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
