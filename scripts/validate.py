from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, unquote

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

DISCLOSURE = "As an Amazon Associate I earn from qualifying purchases."
FORBIDDEN_PATTERNS = [
    r"\$\s*\d",
    r"\b\d+(\.\d+)?\s*(star|stars)\b",
    r"\bstar rating\b",
    r"\brating(s)?\b",
    r"\bcustomer review(s)?\b",
    r"\bin stock\b",
    r"\bsale\b",
    r"\bdiscount\b",
    r"\bcheapest\b",
    r"\blowest price\b",
    r"\bfree shipping\b",
    r"\b#1\b",
    r"\bbest seller\b",
]
SECRET_PATTERNS = [
    r"sk-[A-Za-z0-9_-]{20,}",
    r"sk-proj-[A-Za-z0-9_-]{20,}",
    "OPENAI" + r"_API_KEY",
    "AWS" + r"_SECRET_ACCESS_KEY",
    "BEGIN" + r" PRIVATE KEY",
    r"ghp_[A-Za-z0-9_]{20,}",
    r"github_pat_[A-Za-z0-9_]{20,}",
]
VERIFICATION_FILE_PATTERNS = [
    r"google[a-z0-9]+\.html",
    r"BingSiteAuth\.xml",
]


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if "href" in data:
            self.hrefs.append(data["href"])
        if tag == "script" and "src" in data:
            self.scripts.append(data["src"])


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def fail(errors, message):
    errors.append(message)


def normalize_words(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def fingerprint(page):
    parts = [page.get("title", ""), page.get("description", "")]
    for section in page.get("sections", []):
        parts.extend([section.get("heading", ""), section.get("body", "")])
        parts.extend(section.get("bullets", []))
    return normalize_words(" ".join(parts))


def ngrams(words, size=5):
    if len(words) < size:
        return words
    return [" ".join(words[i:i + size]) for i in range(len(words) - size + 1)]


def jaccard(a, b):
    sa, sb = set(ngrams(a)), set(ngrams(b))
    if not sa or not sb:
        return 0
    return len(sa & sb) / len(sa | sb)


def scan_text(errors, label, text):
    lower = text.lower()
    lower = lower.replace("does not display amazon customer reviews, star ratings, product images, live cost, or availability.", "")
    lower = lower.replace("amazon_customer_reviews", "")
    lower = lower.replace("amazon_star_ratings", "")
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, lower):
            fail(errors, f"forbidden volatile claim in {label}: {pattern}")
    if "m.media-amazon.com" in lower or "images-na.ssl-images-amazon.com" in lower:
        fail(errors, f"amazon-hosted image reference in {label}")


def validate_data(errors):
    affiliate = load("affiliate.json")
    automation = load("automation.json")
    sources = {item["id"]: item for item in load("sources.json")}
    tools = load("tools.json")
    pages = load("pages.json")
    recs = load("recommendations.json")
    topics = load("optimization_topics.json")

    if automation.get("max_incremental_cost_usd") != 0:
        fail(errors, "automation cost cap is not fixed at 0")
    if automation.get("paid_apis_allowed") is not False:
        fail(errors, "paid APIs are not explicitly disabled")
    if automation.get("retry_limit") != 1 or automation.get("discard_failed_after_retry") is not True:
        fail(errors, "one retry then discard is not configured")
    if affiliate.get("do_not_guess_affiliate_tags") is not True:
        fail(errors, "affiliate tag guessing guard is missing")
    if affiliate.get("monetization_enabled") and not affiliate.get("amazon_associates_tag"):
        fail(errors, "monetization enabled without amazon_associates_tag")
    tag = affiliate.get("amazon_associates_tag", "")
    if tag and not re.match(r"^[A-Za-z0-9][A-Za-z0-9-]{1,48}$", tag):
        fail(errors, "amazon_associates_tag does not match expected public tag shape")

    for src in sources.values():
        parsed = urlparse(src["url"])
        if parsed.scheme != "https":
            fail(errors, f"source is not https: {src['id']}")

    seen = set()
    for collection_name, collection in [("tool", tools), ("page", pages), ("recommendation", recs)]:
        for item in collection:
            key = (collection_name, item["slug"] if "slug" in item else item["id"])
            if key in seen:
                fail(errors, f"duplicate {collection_name} key {key[1]}")
            seen.add(key)
            if not item.get("source_ids"):
                fail(errors, f"{collection_name} missing source evidence: {key[1]}")
            for source_id in item.get("source_ids", []):
                if source_id not in sources:
                    fail(errors, f"{collection_name} {key[1]} references unknown source {source_id}")
            scan_text(errors, f"{collection_name}:{key[1]}", json.dumps(item))

    if len(tools) < 10:
        fail(errors, "fewer than 10 tools")
    if len(pages) < 25:
        fail(errors, "fewer than 25 supporting evergreen pages")

    fingerprints = [(p["slug"], fingerprint(p)) for p in pages]
    for i, (slug_a, fp_a) in enumerate(fingerprints):
        for slug_b, fp_b in fingerprints[i + 1:]:
            score = jaccard(fp_a, fp_b)
            if score > 0.72:
                fail(errors, f"possible duplicate content: {slug_a} and {slug_b} ({score:.2f})")

    recommendation_ids = {item["id"] for item in recs}
    for topic in topics:
        if not topic.get("source_ids"):
            fail(errors, f"optimization topic missing source evidence: {topic.get('id', 'unknown')}")
        for source_id in topic.get("source_ids", []):
            if source_id not in sources:
                fail(errors, f"optimization topic {topic['id']} references unknown source {source_id}")
        for rec_id in topic.get("recommendation_ids", []):
            if rec_id not in recommendation_ids:
                fail(errors, f"optimization topic {topic['id']} references unknown recommendation {rec_id}")


def internal_target_exists(dist, current_file, href):
    if href.startswith("#") or href.startswith("mailto:"):
        return True
    parsed = urlparse(href)
    if parsed.scheme in ("http", "https"):
        return True
    if parsed.scheme:
        return True
    clean = unquote(parsed.path)
    if not clean or clean == "#":
        return True
    if clean.endswith("/"):
        target = (current_file.parent / clean / "index.html").resolve()
    elif clean.endswith(".html") or "." in Path(clean).name:
        target = (current_file.parent / clean).resolve()
    else:
        target = (current_file.parent / clean / "index.html").resolve()
    try:
        target.relative_to(dist.resolve())
    except ValueError:
        return False
    return target.exists()


def validate_dist(errors, dist):
    html_files = []
    for file in dist.rglob("*.html"):
        rel = file.relative_to(dist).as_posix()
        is_root_file = "/" not in rel
        is_verification_file = any(re.fullmatch(pattern, rel) for pattern in VERIFICATION_FILE_PATTERNS)
        if is_root_file and is_verification_file:
            continue
        html_files.append(file)
    if not html_files:
        fail(errors, "no generated html files")
        return
    for file in html_files:
        text = file.read_text(encoding="utf-8")
        parser = LinkParser()
        parser.feed(text)
        if DISCLOSURE not in text:
            fail(errors, f"missing affiliate disclosure in {file.relative_to(dist)}")
        if '<link rel="canonical"' not in text:
            fail(errors, f"missing canonical in {file.relative_to(dist)}")
        if 'application/ld+json' not in text:
            fail(errors, f"missing structured data in {file.relative_to(dist)}")
        scan_text(errors, str(file.relative_to(dist)), text)
        for href in parser.hrefs:
            if not internal_target_exists(dist, file, href):
                fail(errors, f"broken internal link from {file.relative_to(dist)} to {href}")
        if "click-tracker.js" not in text:
            fail(errors, f"missing click tracker in {file.relative_to(dist)}")
    for required in ["sitemap.xml", "robots.txt", "assets/js/tools.js", "assets/js/click-tracker.js", "assets/css/site.css"]:
        if not (dist / required).exists():
            fail(errors, f"missing generated asset {required}")


def validate_workflows(errors):
    workflow_dir = ROOT / ".github" / "workflows"
    workflows = list(workflow_dir.glob("*.yml"))
    if not workflows:
        fail(errors, "no GitHub Actions workflows")
        return
    text = "\n".join(path.read_text(encoding="utf-8") for path in workflows)
    if "cron:" not in text:
        fail(errors, "no scheduled workflow cron")
    if "deploy-pages" not in text:
        fail(errors, "no GitHub Pages deploy action")
    if "python scripts/maintenance.py" not in text:
        fail(errors, "maintenance script not wired into workflow")
    if "python scripts/optimize.py" not in text:
        fail(errors, "optimization script not wired into workflow")


def scan_repo_secrets(errors):
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith((".git/", "site/", "private-inputs/")):
            continue
        if Path(rel).name.startswith(".env"):
            fail(errors, f"env file present: {rel}")
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in SECRET_PATTERNS:
            if re.search(pattern, text):
                fail(errors, f"possible secret pattern {pattern} in {rel}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", default="site")
    args = parser.parse_args()
    errors = []
    validate_data(errors)
    dist = (ROOT / args.dist).resolve()
    validate_dist(errors, dist)
    validate_workflows(errors)
    scan_repo_secrets(errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "ok", "checks": ["data", "dist", "workflows", "public-safety"], "dist": str(dist)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
