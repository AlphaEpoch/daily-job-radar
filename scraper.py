import datetime
import html as html_lib
import os
import re
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import requests

OUTPUT_DIR = "public"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "index.html")

RSS_FEEDS = [
    {
        "name": "WWR Sales & Marketing",
        "url": "https://weworkremotely.com/categories/remote-sales-and-marketing-jobs.rss",
    },
    {
        "name": "WWR Management & Finance",
        "url": "https://weworkremotely.com/categories/remote-management-and-finance-jobs.rss",
    },
    {
        "name": "WWR Product",
        "url": "https://weworkremotely.com/categories/remote-product-jobs.rss",
    },
    {
        "name": "WWR All Other",
        "url": "https://weworkremotely.com/categories/all-other-remote-jobs.rss",
    },
    {
        "name": "Remotive",
        "url": "https://remotive.com/remote-jobs/feed",
    },
    {
        "name": "Himalayas",
        "url": "https://himalayas.app/jobs/rss",
    },
    {
        "name": "Jobicy",
        "url": "https://jobicy.com/?feed=job_feed",
    },
    {
        "name": "RemoteFirstJobs Marketing",
        "url": "https://remotefirstjobs.com/rss/jobs/marketing.rss",
    },
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
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "application/rss+xml, application/atom+xml, application/xml,"
        " text/xml;q=0.9, */*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def strip_html(raw_html: str) -> str:
  if not raw_html:
    return ""
  return BeautifulSoup(raw_html, "html.parser").get_text(" ", strip=True)


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

  matched = [
      term for term in include_terms if matches_term(searchable_text, term)
  ]
  return bool(matched), matched


def extract_atom_link(entry_elem: ET.Element) -> str:
  ns = {"atom": "http://www.w3.org/2005/Atom"}
  for link_elem in entry_elem.findall("atom:link", ns) + entry_elem.findall(
      "link"
  ):
    rel = (link_elem.attrib.get("rel") or "alternate").strip()
    href = (link_elem.attrib.get("href") or "").strip()
    if href and rel in ("alternate", ""):
      return href
  return ""


def fetch_rss_feed(
    source_name: str, url: str
) -> tuple[list[dict[str, str]], str | None]:
  try:
    resp = requests.get(url, headers=REQUEST_HEADERS, timeout=15)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
  except (requests.RequestException, ET.ParseError) as exc:
    return [], f"{source_name}: {exc}"

  items: list[dict[str, str]] = []

  # Standard RSS <item> nodes
  for item in root.findall(".//item"):
    title = (item.findtext("title") or "").strip()
    link = (item.findtext("link") or "").strip()
    categories = " ".join(
        (c.text or "").strip() for c in item.findall("category") if c.text
    )
    summary_text = strip_html(
        item.findtext("description")
        or item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded")
        or ""
    )

    if not title or not link:
      continue

    items.append({
        "title": title,
        "link": link,
        "source": source_name,
        "searchable": f"{title} {categories} {summary_text[:400]}",
    })

  # Atom <entry> nodes fallback if no <item> nodes exist
  if not items:
    atom_ns = "{http://www.w3.org/2005/Atom}"
    for entry in root.findall(f".//{atom_ns}entry"):
      title = (entry.findtext(f"{atom_ns}title") or "").strip()
      link = extract_atom_link(entry)
      summary_text = strip_html(
          entry.findtext(f"{atom_ns}summary")
          or entry.findtext(f"{atom_ns}content")
          or ""
      )

      if not title or not link:
        continue

      items.append({
          "title": title,
          "link": link,
          "source": source_name,
          "searchable": f"{title} {summary_text[:400]}",
      })

  return items, None


def collect_jobs(
    feeds: list[dict[str, str]],
    include_terms: list[str],
    exclude_terms: list[str],
) -> tuple[list[dict[str, object]], list[str]]:
  raw_items: list[dict[str, str]] = []
  notes: list[str] = []

  for feed in feeds:
    feed_items, err = fetch_rss_feed(feed["name"], feed["url"])
    if err:
      notes.append(err)
    raw_items.extend(feed_items)

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
        "source": entry["source"],
        "matched": matched_terms[:3],
    })

    if len(matched_jobs) >= 50:
      break

  return matched_jobs, notes


def build_html(jobs: list[dict[str, object]], notes: list[str]) -> str:
  updated_at = datetime.datetime.now(datetime.timezone.utc).strftime(
      "%Y-%m-%d %H:%M UTC"
  )

  if jobs:
    cards = []
    for job in jobs:
      safe_title = html_lib.escape(str(job["title"]))
      safe_link = html_lib.escape(str(job["link"]), quote=True)
      source = html_lib.escape(str(job.get("source") or ""))
      matched = [str(m) for m in (job.get("matched") or [])]

      meta_parts = []
      if source:
        meta_parts.append(source)
      if matched:
        meta_parts.append(
            "Matched: " + ", ".join(html_lib.escape(m) for m in matched)
        )

      meta_html = (
          f'<div class="submeta">{" · ".join(meta_parts)}</div>'
          if meta_parts
          else ""
      )
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
    fallback = (
        notes[0]
        if notes
        else "No jobs matched your current include/exclude filters."
    )
    body_content = f'<p class="empty">{html_lib.escape(fallback)}</p>'

  notes_banner = ""
  if notes and jobs:
    joined_notes = html_lib.escape(" | ".join(notes))
    notes_banner = f'<p class="warn">Feed warnings: {joined_notes}</p>'

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
  jobs, notes = collect_jobs(RSS_FEEDS, INCLUDE_KEYWORDS, EXCLUDE_KEYWORDS)
  html = build_html(jobs, notes)
  with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(html)
  print(f"Wrote {len(jobs)} jobs to {OUTPUT_FILE}")
  for note in notes:
    print(note)


if __name__ == "__main__":
  main()
