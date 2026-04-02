#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


BASE_URL = "https://www.n1payments.com"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"
PAGES_API_URL = (
    f"{BASE_URL}/wp-json/wp/v2/pages"
    "?per_page=100&_fields=link,title,content"
)
OUTPUT_PATH = "n1payments_site_text.txt"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
}

BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "br",
    "caption",
    "dd",
    "details",
    "div",
    "dl",
    "dt",
    "fieldset",
    "figcaption",
    "figure",
    "footer",
    "form",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "li",
    "main",
    "ol",
    "p",
    "section",
    "summary",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "ul",
}

SKIP_TAGS = {
    "audio",
    "canvas",
    "iframe",
    "img",
    "meta",
    "noscript",
    "path",
    "picture",
    "script",
    "source",
    "style",
    "svg",
    "video",
}

SKIP_CLASS_SUBSTRINGS = (
    "cookie",
    "cmplz",
    "complianz",
    "gdpr",
    "notice",
    "screen-reader",
    "screenreader",
    "elementor-screen-only",
    "skip-link",
    "swiper-button",
    "swiper-pagination",
)

SKIP_ID_SUBSTRINGS = (
    "cookie",
    "cmplz",
    "complianz",
    "gdpr",
    "notice",
)

HIDDEN_ALL_BREAKPOINTS = {
    "elementor-hidden-desktop",
    "elementor-hidden-tablet",
    "elementor-hidden-mobile",
}

TITLE_RE = re.compile(r"(?is)<title[^>]*>(.*?)</title>")
MAIN_RE = re.compile(r"(?is)<main\b[^>]*>(.*?)</main>")
SPACE_RE = re.compile(r"\s+")


def fetch_text(url: str) -> str:
    request = Request(url, headers=HEADERS)
    with urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, "ignore")


def normalize_url(url: str) -> str:
    split = urlsplit(url.strip())
    scheme = split.scheme or "https"
    netloc = split.netloc.lower()
    path = split.path or "/"
    if path != "/" and not path.endswith("/"):
        path += "/"
    return urlunsplit((scheme, netloc, path, "", ""))


def parse_sitemap(url: str) -> list[str]:
    xml_text = fetch_text(url)
    root = ET.fromstring(xml_text)
    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    if root.tag.endswith("sitemapindex"):
        urls: list[str] = []
        for loc in root.findall("sm:sitemap/sm:loc", namespace):
            urls.extend(parse_sitemap(loc.text or ""))
        return urls

    results: list[str] = []
    for loc in root.findall("sm:url/sm:loc", namespace):
        value = (loc.text or "").strip()
        if value:
            results.append(value)
    return results


def fetch_pages_api() -> dict[str, dict[str, str]]:
    raw = fetch_text(PAGES_API_URL)
    pages = json.loads(raw)
    result: dict[str, dict[str, str]] = {}
    for page in pages:
        link = page.get("link", "")
        result[normalize_url(link)] = {
            "link": link,
            "title": unescape(page.get("title", {}).get("rendered", "")).strip(),
            "content": page.get("content", {}).get("rendered", "") or "",
        }
    return result


def extract_title(document_html: str) -> str:
    match = TITLE_RE.search(document_html)
    if not match:
        return ""
    title = unescape(match.group(1))
    return SPACE_RE.sub(" ", title).strip()


def extract_main(document_html: str) -> str:
    match = MAIN_RE.search(document_html)
    if match:
        return match.group(1)
    return document_html


def is_hidden_element(tag: str, attrs: dict[str, str]) -> bool:
    if tag in SKIP_TAGS:
        return True

    role = attrs.get("role", "").lower()
    if role in {"banner", "contentinfo", "navigation"}:
        return True

    if attrs.get("hidden") is not None:
        return True

    if attrs.get("aria-hidden", "").lower() == "true":
        return True

    style = attrs.get("style", "").lower().replace(" ", "")
    if "display:none" in style or "visibility:hidden" in style:
        return True

    class_attr = attrs.get("class", "")
    class_tokens = set(class_attr.split())
    class_lower = class_attr.lower()
    if HIDDEN_ALL_BREAKPOINTS.issubset(class_tokens):
        return True
    if any(token in class_lower for token in SKIP_CLASS_SUBSTRINGS):
        return True

    element_id = attrs.get("id", "").lower()
    if any(token in element_id for token in SKIP_ID_SUBSTRINGS):
        return True

    return False


class VisibleTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_stack: list[bool] = []

    def current_skip(self) -> bool:
        return self.skip_stack[-1] if self.skip_stack else False

    def newline(self) -> None:
        if self.parts and self.parts[-1] != "\n":
            self.parts.append("\n")

    def add_text(self, text: str) -> None:
        clean = SPACE_RE.sub(" ", text.replace("\xa0", " ")).strip()
        if not clean:
            return
        if not self.parts:
            self.parts.append(clean)
            return
        if self.parts[-1] == "\n":
            self.parts.append(clean)
        elif self.parts[-1].endswith(" "):
            self.parts.append(clean)
        else:
            self.parts.append(" ")
            self.parts.append(clean)

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = {key.lower(): (value or "") for key, value in attrs_list}
        skip = self.current_skip() or is_hidden_element(tag, attrs)
        self.skip_stack.append(skip)
        if skip:
            return
        if tag in BLOCK_TAGS:
            self.newline()
        if tag in {"input", "textarea"}:
            input_type = attrs.get("type", "").lower()
            if input_type != "hidden":
                placeholder = attrs.get("placeholder", "").strip()
                value = attrs.get("value", "").strip()
                if placeholder:
                    self.add_text(placeholder)
                    self.newline()
                elif input_type in {"submit", "button"} and value:
                    self.add_text(value)
                    self.newline()

    def handle_endtag(self, tag: str) -> None:
        skip = self.skip_stack.pop() if self.skip_stack else False
        if skip:
            return
        if tag in BLOCK_TAGS:
            self.newline()

    def handle_data(self, data: str) -> None:
        if self.current_skip():
            return
        self.add_text(data)

    def get_text(self) -> str:
        raw = "".join(self.parts)
        lines = []
        last_line = None
        for line in raw.splitlines():
            clean = SPACE_RE.sub(" ", line).strip()
            if not clean:
                continue
            if clean in {"Previous", "Next"}:
                continue
            if clean == last_line:
                continue
            lines.append(clean)
            last_line = clean
        return "\n".join(lines).strip()


def extract_visible_text(fragment_html: str) -> str:
    parser = VisibleTextExtractor()
    parser.feed(fragment_html)
    parser.close()
    return parser.get_text()


def fetch_document(url: str) -> tuple[str, str]:
    return url, fetch_text(url)


def build_records() -> list[dict[str, str]]:
    sitemap_urls = parse_sitemap(SITEMAP_URL)
    page_map = fetch_pages_api()

    documents: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(fetch_document, url): url for url in sitemap_urls}
        for future in as_completed(futures):
            url, document_html = future.result()
            documents[url] = document_html

    records: list[dict[str, str]] = []
    for url in sitemap_urls:
        normalized = normalize_url(url)
        page_data = page_map.get(normalized)
        document_html = documents.get(url, "")
        title = extract_title(document_html)
        if not title and page_data:
            title = page_data["title"]
        body_source = page_data["content"] if page_data else extract_main(document_html)
        body_text = extract_visible_text(body_source)
        if not body_text:
            body_text = extract_visible_text(extract_main(document_html))
        records.append(
            {
                "url": url,
                "title": title or url,
                "text": body_text or "(No visible body text extracted.)",
            }
        )
    return records


def write_output(records: list[dict[str, str]]) -> None:
    separator = "=" * 100
    with open(OUTPUT_PATH, "w", encoding="utf-8") as output_file:
        output_file.write("N1 Payments Site Crawl\n")
        output_file.write(f"Total pages: {len(records)}\n")
        output_file.write(f"Source sitemap: {SITEMAP_URL}\n")
        for index, record in enumerate(records, start=1):
            output_file.write("\n\n")
            output_file.write(separator + "\n")
            output_file.write(f"PAGE {index}\n")
            output_file.write(f"URL: {record['url']}\n")
            output_file.write(f"TITLE: {record['title']}\n")
            output_file.write("TEXT:\n")
            output_file.write(record["text"])
            output_file.write("\n")


def main() -> int:
    records = build_records()
    write_output(records)
    print(f"Wrote {len(records)} pages to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
