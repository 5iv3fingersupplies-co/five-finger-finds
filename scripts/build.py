from __future__ import annotations

import argparse
import html
import json
import os
import shutil
from datetime import date
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ASSETS = ROOT / "assets"
STATIC_ROOT = ROOT / "static-root"


def load_json(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def slug_path(kind: str, slug: str) -> str:
    return f"{kind}/{slug}/"


def page_depth(path: str) -> int:
    if path in ("", "index.html"):
        return 0
    parts = [part for part in path.strip("/").split("/") if part]
    if parts and "." in parts[-1]:
        parts = parts[:-1]
    return len(parts)


def rel(depth: int, target: str) -> str:
    prefix = "../" * depth
    return prefix + target.lstrip("/")


def absolute(base_url: str, path: str) -> str:
    if not path:
        return base_url.rstrip("/") + "/"
    return base_url.rstrip("/") + "/" + path.strip("/") + "/"


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def md_text(items) -> str:
    return " ".join(str(item) for item in items if item)


def load_all():
    site = load_json("site.json")
    affiliate = load_json("affiliate.json")
    automation = load_json("automation.json")
    sources = {item["id"]: item for item in load_json("sources.json")}
    tools = load_json("tools.json")
    guides = load_json("pages.json")
    recommendations = {item["id"]: item for item in load_json("recommendations.json")}
    editorial = load_json("editorial_calendar.json")
    return site, affiliate, automation, sources, tools, guides, recommendations, editorial


def affiliate_href(affiliate, rec):
    if not affiliate.get("monetization_enabled"):
        return ""
    tag = affiliate.get("amazon_associates_tag", "").strip()
    if not tag:
        return ""
    return f"https://www.amazon.com/s?k={quote_plus(rec['query'])}&tag={quote_plus(tag)}"


def disclosure_html(affiliate):
    return (
        f"<strong>{esc(affiliate['required_disclosure'])}</strong> "
        f"{esc(affiliate['plain_language_disclosure'])}"
    )


def nav(depth: int, site):
    return f"""
    <header class="topbar">
      <nav class="nav" aria-label="Main navigation">
        <a class="brand" href="{rel(depth, 'index.html')}"><span class="brand-mark">5F</span><span>{esc(site['name'])}</span></a>
        <div class="nav-links">
          <a href="{rel(depth, 'start-here/index.html')}">Start Here</a>
          <a href="{rel(depth, 'tools/index.html')}">Tools</a>
          <a href="{rel(depth, 'seasonal/index.html')}">Seasonal</a>
          <a href="{rel(depth, 'guides/index.html')}">Guides</a>
          <a href="{rel(depth, 'affiliate-disclosure/index.html')}">Disclosure</a>
          <a href="{rel(depth, 'privacy/index.html')}">Privacy</a>
        </div>
      </nav>
    </header>
    """


def layout(site, affiliate, title, description, path, body, schema=None, extra_js=False):
    depth = page_depth(path)
    url = absolute(site["base_url"], path.replace("index.html", ""))
    schema_json = json.dumps(schema or {}, ensure_ascii=False)
    script = f'<script type="application/ld+json">{schema_json}</script>' if schema else ""
    tools_js = f'<script src="{rel(depth, "assets/js/tools.js")}" defer></script>' if extra_js else ""
    return f"""<!doctype html>
<html lang="{esc(site['language'])}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)} | {esc(site['name'])}</title>
  <meta name="description" content="{esc(description)}">
  <link rel="canonical" href="{esc(url)}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{esc(url)}">
  <meta property="og:site_name" content="{esc(site['name'])}">
  <link rel="alternate" type="application/atom+xml" title="{esc(site['name'])} updates" href="{rel(depth, 'feed.xml')}">
  <link rel="alternate" type="application/atom+xml" title="{esc(site['name'])} updates" href="{rel(depth, 'feed.xml')}">
  <link rel="alternate" type="application/atom+xml" title="{esc(site['name'])} updates" href="{rel(depth, 'feed.xml')}">
  <link rel="alternate" type="application/atom+xml" title="{esc(site['name'])} updates" href="{rel(depth, 'feed.xml')}">
  <link rel="stylesheet" href="{rel(depth, 'assets/css/site.css')}">
  {script}
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
  {nav(depth, site)}
  <div class="disclosure-ribbon"><div class="inner">{disclosure_html(affiliate)}</div></div>
  <main id="main">{body}</main>
  <footer class="footer">
    <div class="wrap">
      <div>
        <strong>{esc(site['name'])}</strong>
        <p class="fineprint">{esc(site['contact_note'])}</p>
      </div>
      <div class="nav-links">
        <a href="{rel(depth, 'about/index.html')}">About</a>
        <a href="{rel(depth, 'publisher-standards/index.html')}">Publisher Standards</a>
        <a href="{rel(depth, 'feed.xml')}">RSS</a>
        <a href="{rel(depth, 'sitemap.xml')}">Sitemap</a>
      </div>
    </div>
  </footer>
  <script src="{rel(depth, 'assets/js/click-tracker.js')}" defer></script>
  {tools_js}
</body>
</html>
"""


def card(title, description, href, icon=None, tag=None):
    icon_html = f'<img class="icon" src="{esc(icon)}" alt="" loading="lazy">' if icon else ""
    tag_html = f'<span class="tag">{esc(tag)}</span>' if tag else ""
    return f"""<article class="card">
  {icon_html}
  {tag_html}
  <h3><a href="{esc(href)}">{esc(title)}</a></h3>
  <p>{esc(description)}</p>
</article>"""


def recommendation_cards(ids, recommendations, affiliate, depth):
    rows = []
    for rec_id in ids:
        rec = recommendations[rec_id]
        href = affiliate_href(affiliate, rec)
        sources = ", ".join(rec["source_ids"])
        if href:
            action = f'<a class="button" href="{esc(href)}" rel="sponsored nofollow noopener" data-affiliate="{esc(rec_id)}">Open option search</a>'
        else:
            action = '<a class="button disabled" aria-disabled="true" href="#">Affiliate link inactive</a>'
        rows.append(f"""<article class="card">
  <span class="tag">Decision fit</span>
  <h3>{esc(rec['label'])}</h3>
  <p>{esc(rec['fit'])}</p>
  <p class="fineprint">Evidence records: {esc(sources)}</p>
  {action}
</article>""")
    return "\n".join(rows)


def sources_block(source_ids, sources):
    items = []
    for source_id in source_ids:
        src = sources[source_id]
        items.append(f'<li><a href="{esc(src["url"])}" rel="nofollow noopener">{esc(src["title"])}</a>, {esc(src["publisher"])}</li>')
    return '<section class="sources"><h2>Source records</h2><ul>' + "".join(items) + "</ul></section>"


def schema_base(site, title, description, path, schema_type):
    return {
        "@context": "https://schema.org",
        "@type": schema_type,
        "name": title,
        "description": description,
        "url": absolute(site["base_url"], path.replace("index.html", "")),
        "publisher": {"@type": "Organization", "name": site["brand"]},
        "dateModified": site["launch_date"],
    }


def write_page(out, rel_path, html_text):
    path = out / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_text, encoding="utf-8", newline="\n")


def build_home(out, site, affiliate, tools, guides, editorial):
    visual_icons = ["air-pump.svg", "power-bank.svg", "car-kit.svg", "house-kit.svg"]
    tiles = []
    for label, icon in zip(["Inflate", "Charge", "Prepare", "Pack"], visual_icons):
        tiles.append(f'<div class="visual-tile"><img src="assets/img/{icon}" alt=""><span>{label}</span></div>')
    tool_cards = "\n".join(card(t["title"], t["description"], f"tools/{t['slug']}/index.html", f"assets/img/{t['icon']}", t["category"]) for t in tools[:6])
    guide_cards = "\n".join(card(g["title"], g["description"], f"guides/{g['slug']}/index.html", None, g["category"]) for g in guides[:6])
    seasonal_cards = "\n".join(card(e["title"], e["description"], f"seasonal/{e['slug']}/index.html", None, e["month"]) for e in editorial.get("seasonal_pages", [])[:4])
    cue_row = '<div class="cue-row"><span class="cue">Free tools</span><span class="cue">No account</span><span class="cue">Private inputs</span><span class="cue">Affiliate disclosed</span></div>'
    body = f"""
    <section class="hero">
      <div>
        <span class="tag">Practical buyer-decision tools</span>
        <h1>{esc(site['name'])}</h1>
        <p>{esc(site['description'])}</p>
        {cue_row}
        <div class="hero-actions">
          <a class="button" href="tools/index.html">Use the tools</a>
          <a class="button secondary" href="guides/index.html">Browse guides</a>
        </div>
      </div>
      <div class="visual-grid" aria-label="Site categories">{''.join(tiles)}</div>
    </section>
    <section class="band"><div class="wrap"><h2 class="section-title">Launch tools</h2><div class="grid">{tool_cards}</div></div></section>
    <section class="band"><div class="wrap"><h2 class="section-title">Evergreen guides</h2><div class="grid">{guide_cards}</div></div></section>
    <section class="band"><div class="wrap"><h2 class="section-title">Seasonal buyer intent</h2><div class="grid">{seasonal_cards}</div><p class="feed-note"><a href="feed.xml">Follow the free update feed</a> for new calculator-first pages without an account.</p></div></section>
    """
    schema = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": site["name"],
        "url": site["base_url"],
        "description": site["description"],
        "publisher": {"@type": "Organization", "name": site["brand"]},
    }
    write_page(out, "index.html", layout(site, affiliate, site["name"], site["description"], "index.html", body, schema))


def build_tool_index(out, site, affiliate, tools):
    cards = "\n".join(card(t["title"], t["description"], f"{t['slug']}/index.html", f"../assets/img/{t['icon']}", t["category"]) for t in tools)
    body = f"""
    <section class="page-head"><span class="tag">10 calculators</span><h1>Interactive buyer tools</h1><p>Use measurements and requirements before choosing practical gear.</p></section>
    <section class="wrap"><div class="grid">{cards}</div></section>
    """
    write_page(out, "tools/index.html", layout(site, affiliate, "Interactive buyer tools", "Ten static calculators for practical household, travel, auto, camping, and power decisions.", "tools/index.html", body, schema_base(site, "Interactive buyer tools", "Ten static calculators for practical decisions.", "tools/index.html", "CollectionPage")))


def build_tool(out, site, affiliate, tool, sources, recommendations):
    depth = 2
    fields = []
    for field in tool["fields"]:
        attrs = f'name="{esc(field["id"])}" id="{esc(field["id"])}"'
        if field["type"] == "select":
            options = "".join(f'<option value="{esc(opt)}">{esc(opt)}</option>' for opt in field["options"])
            control = f"<select {attrs}>{options}</select>"
        else:
            extra = []
            for attr in ("min", "max", "step", "value"):
                if attr in field:
                    extra.append(f'{attr}="{esc(field[attr])}"')
            control = f'<input type="number" {attrs} {" ".join(extra)}>'
        fields.append(f'<label for="{esc(field["id"])}">{esc(field["label"])}{control}</label>')
    recs = recommendation_cards(tool["recommendation_ids"], recommendations, affiliate, depth)
    body = f"""
    <section class="page-head">
      <span class="tag">{esc(tool['category'])}</span>
      <h1>{esc(tool['title'])}</h1>
      <p>{esc(tool['description'])}</p>
    </section>
    <section class="content tool-shell">
      <div class="tool-panel">
        <form class="tool-form" data-tool-type="{esc(tool['tool_type'])}">
          {''.join(fields)}
          <button type="submit">Calculate</button>
        </form>
      </div>
      <div class="result-box" aria-live="polite"></div>
    </section>
    <section class="wrap band"><h2 class="section-title">Product-fit cards</h2><div class="grid">{recs}</div></section>
    <section class="content">{sources_block(tool['source_ids'], sources)}</section>
    """
    path = f"tools/{tool['slug']}/index.html"
    schema = schema_base(site, tool["title"], tool["description"], path, "WebApplication")
    schema["applicationCategory"] = "UtilityApplication"
    schema["operatingSystem"] = "Any"
    write_page(out, path, layout(site, affiliate, tool["title"], tool["description"], path, body, schema, extra_js=True))


def build_guide_index(out, site, affiliate, guides):
    cards = "\n".join(card(g["title"], g["description"], f"{g['slug']}/index.html", None, g["category"]) for g in guides)
    body = f"""
    <section class="page-head"><span class="tag">{len(guides)} evergreen pages</span><h1>Practical buying guides</h1><p>Source-backed evergreen pages for household, travel, auto, camping, emergency-prep, portable-power, and convenience products.</p></section>
    <section class="wrap"><div class="grid">{cards}</div></section>
    """
    write_page(out, "guides/index.html", layout(site, affiliate, "Practical buying guides", "Evergreen practical buying guides backed by public source records.", "guides/index.html", body, schema_base(site, "Practical buying guides", "Evergreen practical buying guides.", "guides/index.html", "CollectionPage")))


def build_guide(out, site, affiliate, guide, sources, recommendations, tools):
    sections = []
    for section in guide["sections"]:
        bullets = "".join(f"<li>{esc(item)}</li>" for item in section["bullets"])
        sections.append(f"<h2>{esc(section['heading'])}</h2><p>{esc(section['body'])}</p><ul>{bullets}</ul>")
    related_tools = [t for t in tools if t["category"] == guide["category"] or any(src in t["source_ids"] for src in guide["source_ids"])][:3]
    tool_links = "".join(card(t["title"], t["description"], f"../../tools/{t['slug']}/index.html", f"../../assets/img/{t['icon']}", t["category"]) for t in related_tools)
    related_rec_ids = []
    for t in related_tools:
        related_rec_ids.extend(t["recommendation_ids"])
    related_rec_ids = list(dict.fromkeys(related_rec_ids))[:3]
    recs = recommendation_cards(related_rec_ids, recommendations, affiliate, 2) if related_rec_ids else ""
    path = f"guides/{guide['slug']}/index.html"
    body = f"""
    <section class="page-head">
      <span class="tag">{esc(guide['category'])}</span>
      <h1>{esc(guide['title'])}</h1>
      <p>{esc(guide['description'])}</p>
    </section>
    <article class="content">
      {''.join(sections)}
      {sources_block(guide['source_ids'], sources)}
    </article>
    <section class="wrap band"><h2 class="section-title">Related tools</h2><div class="grid">{tool_links}</div></section>
    <section class="wrap band"><h2 class="section-title">Product-fit cards</h2><div class="grid">{recs}</div></section>
    """
    schema = schema_base(site, guide["title"], guide["description"], path, "Article")
    schema["headline"] = guide["title"]
    schema["mainEntityOfPage"] = absolute(site["base_url"], path)
    write_page(out, path, layout(site, affiliate, guide["title"], guide["description"], path, body, schema))


def build_static_pages(out, site, affiliate):
    monetized_note = (
        "Product-fit cards may link to Amazon search results with the public Associates tracking tag. "
        "This site does not display Amazon customer reviews, star ratings, product images, live cost, or availability."
        if affiliate.get("monetization_enabled")
        else
        "When monetization is disabled, product-fit cards are informational and do not send visitors to live affiliate destinations. "
        "This site does not display Amazon customer reviews, star ratings, product images, live cost, or availability."
    )
    static_pages = {
        "about": (
            "About",
            "Five Finger Finds explains practical product decisions with static calculators and source-backed guides.",
            "<p>Five Finger Finds is a Five Finger Supplies project for practical household, travel, auto, camping, emergency-prep, portable-power, and convenience decisions. The site is static and does not require customer accounts, checkout, fulfillment, or product support.</p><p>The calculators use deterministic browser-side JavaScript. The guides are generated from structured source records and templates.</p>",
        ),
        "affiliate-disclosure": (
            "Affiliate Disclosure",
            "Affiliate disclosure for Five Finger Finds.",
            f"<p><strong>{esc(affiliate['required_disclosure'])}</strong></p><p>{esc(affiliate['plain_language_disclosure'])}</p><p>{esc(monetized_note)}</p>",
        ),
        "privacy": (
            "Privacy",
            "Privacy notes for a static first-party site.",
            "<p>This static site does not use customer accounts, payment forms, comments, or paid analytics. Browser-side calculator inputs stay in the browser.</p><p>Affiliate-click counting, when a live outbound link exists, uses localStorage in the visitor's browser to keep a first-party local count. It does not create a server-side profile on GitHub Pages.</p>",
        ),
        "contact": (
            "Contact",
            "Informational contact fallback without support obligations.",
            "<p>This is an informational buyer-decision site. Five Finger Finds does not sell products directly, process orders, handle returns, or provide product support.</p><p>For product orders, warranties, delivery, or returns, use the merchant or manufacturer channel connected to the item you bought.</p>",
        ),
    }
    for slug, (title, description, body_text) in static_pages.items():
        body = f'<section class="page-head"><h1>{esc(title)}</h1><p>{esc(description)}</p></section><article class="content">{body_text}</article>'
        path = f"{slug}/index.html"
        write_page(out, path, layout(site, affiliate, title, description, path, body, schema_base(site, title, description, path, "WebPage")))



def build_start_here(out, site, affiliate, tools, guides, editorial):
    first_tools = "\n".join(card(t["title"], t["description"], f"../tools/{t['slug']}/index.html", f"../assets/img/{t['icon']}", t["category"]) for t in tools[:4])
    first_guides = "\n".join(card(g["title"], g["description"], f"../guides/{g['slug']}/index.html", None, g["category"]) for g in guides[:4])
    seasonal_cards = "\n".join(card(e["title"], e["description"], f"../seasonal/{e['slug']}/index.html", None, e["month"]) for e in editorial.get("seasonal_pages", [])[:4])
    body = f"""
    <section class="page-head"><span class="tag">Start here</span><h1>Start with the decision, not the cart</h1><p>Use one calculator, confirm the source-backed constraint, then open only product-fit links that match the result.</p></section>
    <section class="decision-strip"><div><strong>Measure</strong><span>Get the requirement.</span></div><div><strong>Narrow</strong><span>Pick the category.</span></div><div><strong>Decide</strong><span>Leave only when the fit is clear.</span></div></section>
    <section class="wrap"><h2 class="section-title">Best first tools</h2><div class="grid">{first_tools}</div></section>
    <section class="wrap"><h2 class="section-title">Seasonal entry points</h2><div class="grid">{seasonal_cards}</div></section>
    <section class="wrap"><h2 class="section-title">Trust-building guides</h2><div class="grid">{first_guides}</div></section>
    """
    write_page(out, "start-here/index.html", layout(site, affiliate, "Start Here", "Fast routing to the right tool, guide, or seasonal buyer-decision page.", "start-here/index.html", body, schema_base(site, "Start Here", "Fast routing to the right decision page.", "start-here/index.html", "WebPage")))


def build_seasonal_pages(out, site, affiliate, editorial, tools, guides, recommendations):
    tools_by_slug = {tool["slug"]: tool for tool in tools}
    guides_by_slug = {guide["slug"]: guide for guide in guides}
    index_cards = "\n".join(card(e["title"], e["description"], f"{e['slug']}/index.html", None, e["month"]) for e in editorial.get("seasonal_pages", []))
    body = f'<section class="page-head"><span class="tag">Seasonal intent</span><h1>Seasonal buyer-decision pages</h1><p>Recurring buying moments mapped to calculators, guides, and disclosed product-fit links.</p></section><section class="wrap"><div class="grid">{index_cards}</div></section>'
    write_page(out, "seasonal/index.html", layout(site, affiliate, "Seasonal Buyer Decisions", "Seasonal buyer-decision pages for practical household and travel needs.", "seasonal/index.html", body, schema_base(site, "Seasonal Buyer Decisions", "Seasonal buyer-decision pages.", "seasonal/index.html", "CollectionPage")))
    for entry in editorial.get("seasonal_pages", []):
        tool_cards = "\n".join(card(t["title"], t["description"], f"../../tools/{t['slug']}/index.html", f"../../assets/img/{t['icon']}", t["category"]) for t in (tools_by_slug[s] for s in entry.get("tool_slugs", []) if s in tools_by_slug))
        guide_cards = "\n".join(card(g["title"], g["description"], f"../../guides/{g['slug']}/index.html", None, g["category"]) for g in (guides_by_slug[s] for s in entry.get("guide_slugs", []) if s in guides_by_slug))
        rec_cards = recommendation_cards([rid for rid in entry.get("recommendation_ids", []) if rid in recommendations], recommendations, affiliate, 2)
        prompts = "".join(f"<li>{esc(item)}</li>" for item in entry.get("decision_prompts", []))
        avoids = "".join(f"<li>{esc(item)}</li>" for item in entry.get("avoid_prompts", []))
        body = f"""
        <section class="page-head"><span class="tag">{esc(entry['month'])}</span><h1>{esc(entry['title'])}</h1><p>{esc(entry['description'])}</p></section>
        <article class="content"><p class="notice"><strong>Why now:</strong> {esc(entry['reason'])}</p><h2>Decision prompts</h2><ul>{prompts}</ul><h2>Use this sequence</h2><ul><li>Open the calculator before browsing.</li><li>Read the supporting guide for setup details.</li><li>Use product-fit links only when the result confirms the need.</li><li>Follow the feed for future seasonal passes.</li></ul><h2>Skip these traps</h2><ul>{avoids}</ul></article>
        <section class="wrap band"><h2 class="section-title">Tools for this moment</h2><div class="grid">{tool_cards}</div></section>
        <section class="wrap band"><h2 class="section-title">Supporting guides</h2><div class="grid">{guide_cards}</div></section>
        <section class="wrap band"><h2 class="section-title">Product-fit cards</h2><div class="grid">{rec_cards}</div></section>
        """
        path = f"seasonal/{entry['slug']}/index.html"
        write_page(out, path, layout(site, affiliate, entry["title"], entry["description"], path, body, schema_base(site, entry["title"], entry["description"], path, "Article")))


def build_publisher_standards(out, site, affiliate, editorial):
    channels = "".join(f"<li><strong>{esc(item['channel'])}:</strong> {esc(item['implementation'])}</li>" for item in editorial.get("traffic_channels", []))
    standards = ["Every monetized page includes the Amazon Associate disclosure.", "Product-fit cards do not rehost Amazon Program Content.", "Calculator inputs stay in the visitor browser.", "No paid placement is accepted inside the automated build.", "Volatile marketplace details are omitted unless a permitted source verifies them during the build."]
    body = f'<section class="page-head"><span class="tag">Publisher standards</span><h1>Useful pages first, disclosed affiliate links second</h1><p>{esc(site["name"])} is built for self-serve buyer decisions and public-safe partner review.</p></section><article class="content"><h2>Operating standards</h2><ul>{"".join(f"<li>{esc(item)}</li>" for item in standards)}</ul><h2>Traffic approach</h2><ul>{channels}</ul><h2>Partner fit</h2><p>Future direct affiliate programs should fit the audience, allow clear disclosure, and support self-serve transactions without creating a customer-support queue for this site.</p></article>'
    write_page(out, "publisher-standards/index.html", layout(site, affiliate, "Publisher Standards", "Affiliate publisher standards and no-cost traffic approach.", "publisher-standards/index.html", body, schema_base(site, "Publisher Standards", "Affiliate publisher standards.", "publisher-standards/index.html", "WebPage")))


def feed_xml(site, items):
    updated = date.today().isoformat()
    entries = []
    for item in items[:50]:
        url = absolute(site["base_url"], item["path"].replace("index.html", ""))
        entries.append(f'<entry><title>{esc(item["title"])}</title><link href="{esc(url)}"/><id>{esc(url)}</id><updated>{updated}</updated><summary>{esc(item["description"])}</summary></entry>')
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>{esc(site["name"])} updates</title>
<link href="{esc(site["base_url"].rstrip("/") + "/feed.xml")}" rel="self"/>
<link href="{esc(site["base_url"].rstrip("/") + "/")}"/>
<updated>{updated}</updated>
<id>{esc(site["base_url"].rstrip("/") + "/")}</id>
{''.join(entries)}
</feed>
"""

def build_sitemap(out, site, paths):
    today = site["launch_date"] or date.today().isoformat()
    urls = []
    for path in sorted(paths):
        loc = absolute(site["base_url"], "" if path == "index.html" else path.replace("index.html", ""))
        urls.append(f"<url><loc>{esc(loc)}</loc><lastmod>{today}</lastmod></url>")
    write_page(out, "sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + "\n</urlset>\n")


def build_robots(out, site):
    write_page(out, "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {site['base_url'].rstrip('/')}/sitemap.xml\n")


def copy_assets(out):
    dest = out / "assets"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(ASSETS, dest)


def copy_static_root_files(out):
    if not STATIC_ROOT.exists():
        return
    for source in STATIC_ROOT.rglob("*"):
        if not source.is_file():
            continue
        rel_path = source.relative_to(STATIC_ROOT)
        if any(part.startswith(".") for part in rel_path.parts):
            continue
        target = out / rel_path
        if target.exists():
            raise FileExistsError(f"static-root file would overwrite generated output: {rel_path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="site")
    parser.add_argument("--automation-report", default="")
    args = parser.parse_args()
    out = (ROOT / args.out).resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    site, affiliate, automation, sources, tools, guides, recommendations, editorial = load_all()
    site["base_url"] = os.environ.get("SITE_BASE_URL", site["base_url"]).rstrip("/")

    copy_assets(out)
    build_home(out, site, affiliate, tools, guides, editorial)
    build_tool_index(out, site, affiliate, tools)
    for tool in tools:
        build_tool(out, site, affiliate, tool, sources, recommendations)
    build_guide_index(out, site, affiliate, guides)
    for guide in guides:
        build_guide(out, site, affiliate, guide, sources, recommendations, tools)
    build_start_here(out, site, affiliate, tools, guides, editorial)
    build_seasonal_pages(out, site, affiliate, editorial, tools, guides, recommendations)
    build_publisher_standards(out, site, affiliate, editorial)
    build_static_pages(out, site, affiliate)
    if args.automation_report and Path(args.automation_report).exists():
        shutil.copyfile(args.automation_report, out / "automation-report.json")
    feed_items = [{"title": site["name"], "description": site["description"], "path": "index.html"}]
    feed_items += [{"title": t["title"], "description": t["description"], "path": f'tools/{t["slug"]}/index.html'} for t in tools]
    feed_items += [{"title": e["title"], "description": e["description"], "path": f'seasonal/{e["slug"]}/index.html'} for e in editorial.get("seasonal_pages", [])]
    feed_items += [{"title": g["title"], "description": g["description"], "path": f'guides/{g["slug"]}/index.html'} for g in guides[:20]]
    write_page(out, "feed.xml", feed_xml(site, feed_items))
    paths = [str(p.relative_to(out)).replace("\\", "/") for p in out.rglob("*.html")]
    build_sitemap(out, site, paths)
    build_robots(out, site)
    copy_static_root_files(out)
    print(json.dumps({"out": str(out), "tools": len(tools), "guides": len(guides), "seasonal_pages": len(editorial.get("seasonal_pages", [])), "html_pages": len(paths)}, indent=2))


if __name__ == "__main__":
    main()
