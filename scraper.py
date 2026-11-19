import datetime
import html as html_lib
import os
import re
import xml.etree.ElementTree as ET
import requests

OUTPUT_DIR = "public"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "index.html")

REMOTEOK_API_URL = "https://remoteok.com/api"

# Add or swap RSS feed URLs for boards/categories you want to check
RSS_FEEDS = [
    {"name": "WWR Marketing", "url": "https://weworkremotely.com/categories/remote-marketing-jobs.rss"},
    {"name": "WWR Product", "url": "https://weworkremotely.com/categories/remote-product-jobs.rss"},
]

INCLUDE_KEYWORDS = [
    "community manager",
    "community lead",
    "community management",
    "community specialist",
    "community engagement",
    "project manager",
    "project coordinator",
    "program manager",
    "project operations",
    "operations manager",
    "client success",
    "account manager",
]

EXCLUDE_KEYWORDS = [
    "software engineer",
    "full stack",
    "fullstack",
    "frontend",
    "front-end",
    "backend",
    "back-end",
    "devops",
    "devsecops",
    "data engineer",
    "machine learning",
    "ml engineer",
    "solidity",
    "smart contract",
    "rust developer",
    "kubernetes",
    "cloud architect",
    "technical project manager",
    "technical program manager",
]

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, application/json, text/html;q=0.9, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def matches_term(text: str, term: str) -> bool:
    pattern_body = re.escape(term.strip().lower()).replace(r"\ ", r"[\s\-/]+")
    pattern = rf"(?<!\w){pattern_body}(?!\w)"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def evaluate_listing(
    searchable_text: str,
    include_terms: list[str],
    exclude_terms: list[str],
) -> tuple[bool, list[str]]:
    if any(matches_term(searchable_text, term) for term in exclude_terms):
        return False, []

    if not include_terms:
        return True, []

    matched = [term for term in include_terms if matches_term(searchable_text, term)]
    return bool(matched), matched


def fetch_remoteok(url: str) -> tuple[list[dict[str, str]], str | None]:
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        return [], f"RemoteOK error: {exc}"

    listings = data[1:] if isinstance(data, list) and len(data) > 1 else []
    items: list[dict[str, str]] = []

    for row in listings:
        if not isinstance(row, dict):
            continue
        position = (row.get("position") or "").strip()
        company = (row.get("company") or "").strip()
        link = (row.get("url") or "").strip()
        location = (row.get("location") or "").strip()
        tags = [str(t).strip() for t in (row.get("tags") or []) if t]

        if not position or not link:
            continue

        title = f"{position} — {company}" if company else position
        items.append({
            "title": title,
            "link": link,
            "location": location,
            "source": "RemoteOK",
            "searchable": f"{position} {company} {' '.join(tags)}",
        })

    return items, None


def fetch_rss_feed(source_name: str, url: str) -> tuple[list[dict[str, str]], str | None]:
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except (requests.RequestException, ET.ParseError) as exc:
        return [], f"{source_name} RSS error: {exc}"

    items: list[dict[str, str]] = []

    # Supports standard RSS <item> elements
    for item in root.findall(".//item"):
        raw_title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        category = (item.findtext("category") or "").strip()

        if not raw_title or not link:
            continue

        items.append({
            "title": raw_title,
            "link": link,
            "location": "",
            "source": source_name,
            "searchable": f"{raw_title} {category}",
        })

    return items, None


def collect_jobs(
    include_terms: list[str],
    exclude_terms: list[str],
) -> tuple[list[dict[str, object]], list[str]]:
    raw_items: list[dict[str, str]] = []
    notes: list[str] = []

    rok_items, rok_err = fetch_remoteok(REMOTEOK_API_URL)
    if rok_err:
        notes.append(rok_err)
    raw_items.extend(rok_items)

    for feed in RSS_FEEDS:
        rss_items, rss_err = fetch_rss_feed(feed["name"], feed["url"])
        if rss_err:
            notes.append(rss_err)
        raw_items.extend(rss_items)

    seen_links: set[str] = set()
    matched_jobs: list[dict[str, object]] = []

    for entry in raw_items:
        link = entry["link"]
        if link in seen_links:
            continue
        seen_links.add(link)

        is_match, matched_terms = evaluate_listing(
            entry["searchable"], include_terms, exclude_terms
        )
        if not is_match:
            continue

        matched_jobs.append({
            "title": entry["title"],
            "link": link,
            "location": entry["location"],
            "source": entry["source"],
            "matched": matched_terms[:3],
        })

        if len(matched_jobs) >= 40:
            break

    return matched_jobs, notes


def build_html(jobs: list[dict[str, object]], notes: list[str]) -> str:
    updated_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if jobs:
        cards = []
        for job in jobs:
            safe_title = html_lib.escape(str(job["title"]))
            safe_link = html_lib.escape(str(job["link"]), quote=True)
            source = html_lib.escape(str(job.get("source") or ""))
            location = str(job.get("location") or "")
            matched = [str(m) for m in (job.get("matched") or [])]

            meta_parts = []
            if source:
                meta_parts.append(source)
            if location:
                meta_parts.append(html_lib.escape(location))
            if matched:
                meta_parts.append("Matched: " + ", ".join(html_lib.escape(m) for m in matched))

            meta_html = f'<div class="submeta">{" · ".join(meta_parts)}</div>' if meta_parts else ""
            cards.append(
                f"""
                <article class="card">
                    <a href="{safe_link}" target="_blank" rel="noopener noreferrer">{safe_title}</a>
                    {meta_html}
                </article>
                """.strip()
            )
        body_content = "\n".join(cards)
    else:
        fallback = notes[0] if notes else "No jobs matched your current filters on this run."
        body_content = f'<p class="empty">{html_lib.escape(fallback)}</p>'

    notes_banner = ""
    if notes and jobs:
        joined_notes = html_lib.escape(" | ".join(notes))
        notes_banner = f'<p class="warn">Source warnings: {joined_notes}</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily Job Radar</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            max-width: 780px;
            margin: 48px auto;
            padding: 0 20px;
            background: #0d1117;
            color: #e6edf3;
            line-height: 1.5;
        }}
        header {{
            border-bottom: 1px solid #30363d;
            padding-bottom: 16px;
            margin-bottom: 24px;
        }}
        h1 {{
            margin: 0 0 6px 0;
            font-size: 1.75rem;
        }}
        .meta {{
            color: #8b949e;
            font-size: 0.9rem;
            margin: 0;
        }}
        .warn {{
            color: #d29922;
            font-size: 0.85rem;
            margin: 8px 0 0 0;
        }}
        .card {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 14px 18px;
            margin-bottom: 12px;
        }}
        .card a {{
            color: #58a6ff;
            text-decoration: none;
            font-weight: 600;
        }}
        .card a:hover {{
            text-decoration: underline;
        }}
        .submeta {{
            color: #8b949e;
            font-size: 0.82rem;
            margin-top: 6px;
        }}
        .empty {{
            color: #8b949e;
        }}
    </style>
</head>
<body>
    <header>
        <h1>Daily Job Radar</h1>
        <p class="meta">Showing {len(jobs)} matches · Last updated: {updated_at}</p>
        {notes_banner}
    </header>
    <main>
        {body_content}
    </main>
</body>
</html>
"""


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    jobs, notes = collect_jobs(INCLUDE_KEYWORDS, EXCLUDE_KEYWORDS)
    html = build_html(jobs, notes)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {len(jobs)} jobs to {OUTPUT_FILE}")
    for note in notes:
        print(note)


if __name__ == "__main__":
    main()
