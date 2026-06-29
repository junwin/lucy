"""Simple webpage text scraper.

Usage:
    python3 src/utils/scrape.py <url>

Prints extracted readable text to stdout.
"""

from __future__ import annotations

import re
import sys
from typing import Iterable, Optional

import requests
from bs4 import BeautifulSoup


DEFAULT_TIMEOUT_SECONDS = 10
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36 LucyScraper/1.0"
)


def _remove_elements(soup: BeautifulSoup, selectors: Iterable[str]) -> None:
    for sel in selectors:
        for el in soup.select(sel):
            el.decompose()


def extract_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # Remove common non-content elements.
    _remove_elements(
        soup,
        selectors=[
            "script",
            "style",
            "noscript",
            "svg",
            "canvas",
            "header",
            "footer",
            "nav",
            "aside",
            "form",
            "button",
            "input",
            "textarea",
            "select",
            "option",
        ],
    )

    # Prefer <main> if present.
    main = soup.select_one("main")
    root = main if main is not None else soup.body if soup.body is not None else soup

    text = root.get_text("\n", strip=True)

    # Normalize whitespace: collapse excessive blank lines.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def scrape_url(url: str, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    resp = requests.get(url, headers=headers, timeout=timeout_seconds)
    resp.raise_for_status()

    # requests will guess encoding; if server provides one, it will use it.
    html = resp.text
    return extract_text_from_html(html)


def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help"}:
        print(__doc__.strip())
        return 2

    url = argv[0].strip()
    if not url:
        print("ERROR: url is required", file=sys.stderr)
        return 2

    try:
        text = scrape_url(url)
    except requests.exceptions.Timeout:
        print(f"ERROR: request timed out after {DEFAULT_TIMEOUT_SECONDS}s for URL: {url}", file=sys.stderr)
        return 1
    except requests.exceptions.ConnectionError:
        print(f"ERROR: could not connect to URL: {url}", file=sys.stderr)
        return 1
    except requests.exceptions.HTTPError as e:
        print(f"ERROR: HTTP {e.response.status_code} for URL: {url}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: {type(e).__name__} for URL {url}: {e}", file=sys.stderr)
        return 1

    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
