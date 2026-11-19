import datetime
import html as html_lib
import os
import re
import requests

OUTPUT_DIR = "public"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "index.html")
API_URL = "https://remoteok.com/api"

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


def fetch_jobs(
    url: str,
    include_terms: list[str],
    exclude_terms: list[str],
) -> tuple[list[dict[str, object]], str | None]:
  headers = {
      "User-Agent": "DailyJobRadarBot/1.0 (github-pages-tracker)",
      "Accept": "application/json",
  }

  try:
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()
  except requests.RequestException as exc:
    return [], f"Fetch failed for {url}: {exc}"
  except ValueError as exc:
    return [], f"Invalid JSON response from {url}: {exc}"

  listings = data[1:] if isinstance(data, list) and len(data) > 1 else []
  jobs: list[dict[str, object]] = []

  for item in listings:
    if not isinstance(item, dict):
      continue

    position = (item.get("position") or "").strip()
    company = (item.get("company") or "").strip()
    url_link = (item.get("url") or "").strip()
    location = (item.get("location") or "").strip()
    tags = [str(t).strip() for t in (item.get("tags") or []) if t]

    if not position or not url_link:
      continue

    # Focus matching on title, company, and tags (full descriptions often mention "engineering" even for PM/community roles)
    searchable = f"{position} {company} {' '.join(tags)}"
    is_match, matched_terms = evaluate_listing(
        searchable, include_terms, exclude_terms
    )
    if not is_match:
      continue

    label = f"{position} — {company}" if company else position
    jobs.append({
        "title": label,
        "link": url_link,
        "location": location,
        "matched": matched_terms[:3],
    })

    if len(jobs) >= 30:
      break

  if not jobs:
    return (
        [],
        "Connected, but 0 jobs matched your current include/exclude filters.",
    )

  return jobs, None


def build_html(
    jobs: list[dict[str, object]], status_note: str | None
) -> str:
  updated_at = datetime.datetime.now(datetime.timezone.utc).strftime(
      "%Y-%m-%d %H:%M UTC"
  )

  if jobs:
    cards = []
    for job in jobs:
      safe_title = html_lib.escape(str(job["title"]))
      safe_link = html_lib.escape(str(job["link"]), quote=True)
      location = str(job.get("location") or "")
      matched = [str(m) for m in (job.get("matched") or [])]

      meta_parts = []
      if location:
        meta_parts.append(html_lib.escape(location))
      if matched:
        meta_parts.append("Matched: " + ", ".join(html_lib.escape(m) for m in matched))
      meta_line = (
          f'<div class="submeta">{" · ".join(meta_parts)}</div>'
          if meta_parts
          else ""
      )

      cards.append(
          f"""
            <article class="card">
                <a href="{safe_link}" target="_blank" rel="noopener noreferrer">{safe_title}</a>
                {meta_line}
            </article>
            """.strip()
      )
    body_content = "\n".join(cards)
  else:
    safe_note = html_lib.escape(
        status_note or "No listings found on this run."
    )
    body_content = f'<p class="empty">{safe_note}</p>'

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
    </header>
    <main>
        {body_content}
    </main>
</body>
</html>
"""


def main() -> None:
  os.makedirs(OUTPUT_DIR, exist_ok=True)
  jobs, status_note = fetch_jobs(API_URL, INCLUDE_KEYWORDS, EXCLUDE_KEYWORDS)
  html = build_html(jobs, status_note)
  with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(html)
  print(f"Wrote {len(jobs)} jobs to {OUTPUT_FILE}")
  if status_note:
    print(status_note)


if __name__ == "__main__":
  main()
