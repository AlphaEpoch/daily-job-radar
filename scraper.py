import datetime
import os
import requests
from bs4 import BeautifulSoup

OUTPUT_DIR = "public"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "index.html")
TARGET_URL = "https://news.ycombinator.com/jobs"


def fetch_jobs(url: str) -> list[dict[str, str]]:
  headers = {"User-Agent": "Mozilla/5.0"}
  response = requests.get(url, headers=headers, timeout=15)
  response.raise_for_status()

  soup = BeautifulSoup(response.text, "html.parser")
  jobs: list[dict[str, str]] = []

  for row in soup.select("tr.athing")[:20]:
    title_span = row.select_one("span.titleline")
    if not title_span:
      continue
    link_tag = title_span.find("a")
    if not link_tag or not link_tag.get("href"):
      continue

    title = link_tag.get_text(strip=True)
    href = link_tag["href"]
    if href.startswith("item?"):
      href = f"https://news.ycombinator.com/{href}"

    jobs.append({"title": title, "link": href})

  return jobs


def build_html(jobs: list[dict[str, str]]) -> str:
  updated_at = datetime.datetime.now(datetime.timezone.utc).strftime(
      "%Y-%m-%d %H:%M UTC"
  )

  cards = []
  for job in jobs:
    cards.append(
        f"""
        <article class="card">
            <a href="{job["link"]}" target="_blank" rel="noopener noreferrer">{job["title"]}</a>
        </article>
        """.strip()
    )

  cards_html = (
      "\n".join(cards)
      if cards
      else '<p class="empty">No listings found on this run.</p>'
  )

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
        .empty {{
            color: #8b949e;
        }}
    </style>
</head>
<body>
    <header>
        <h1>Daily Job Radar</h1>
        <p class="meta">Last updated: {updated_at}</p>
    </header>
    <main>
        {cards_html}
    </main>
</body>
</html>
"""


def main() -> None:
  os.makedirs(OUTPUT_DIR, exist_ok=True)
  jobs = fetch_jobs(TARGET_URL)
  html = build_html(jobs)
  with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(html)
  print(f"Wrote {len(jobs)} jobs to {OUTPUT_FILE}")


if __name__ == "__main__":
  main()
