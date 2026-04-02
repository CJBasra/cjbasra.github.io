#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen


BASE_URL = "https://www.n1payments.com"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"
BRAND_REPORT_PATH = "n1payments_brand_style_audit.md"
ASSET_MANIFEST_PATH = "n1payments_asset_manifest.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
}

TITLE_RE = re.compile(r"(?is)<title[^>]*>(.*?)</title>")
MAIN_RE = re.compile(r"(?is)<main\b[^>]*>(.*?)</main>")
META_GENERATOR_RE = re.compile(
    r'(?is)<meta[^>]+name=["\']generator["\'][^>]+content=["\'](.*?)["\']'
)
COLOR_RE = re.compile(
    r"#(?:[0-9a-fA-F]{3,8})\b|rgba?\([^)]*\)|hsla?\([^)]*\)"
)
FONT_FAMILY_RE = re.compile(r"font-family\s*:\s*([^;}{]+)")
CSS_VAR_RE = re.compile(r"(--[A-Za-z0-9_-]+)\s*:\s*([^;}{]+)")
URL_IN_STYLE_RE = re.compile(r"url\((.*?)\)", re.I)
HEX_SHORT_RE = re.compile(r"^#([0-9a-fA-F]{3})$")
HEX_LONG_RE = re.compile(r"^#([0-9a-fA-F]{6})$")
SPACE_RE = re.compile(r"\s+")

GENERIC_FONT_NAMES = {
    "arial",
    "helvetica",
    "times new roman",
    "georgia",
    "verdana",
    "tahoma",
    "trebuchet ms",
    "courier new",
}

NEUTRAL_COLOR_VALUES = {
    "#ffffff",
    "#000000",
    "rgb(0,0,0)",
    "rgba(0,0,0,0.2)",
    "#e9ecef",
    "#6c757d",
    "#32373c",
    "#424242",
    "#555555",
    "#212529",
}


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


def normalize_asset_url(raw_url: str, base_url: str) -> str:
    cleaned = raw_url.strip().strip("\"'")
    if not cleaned or cleaned.startswith("data:"):
        return ""
    return urljoin(base_url, cleaned)


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


def extract_title(document_html: str) -> str:
    match = TITLE_RE.search(document_html)
    if not match:
        return ""
    return SPACE_RE.sub(" ", unescape(match.group(1))).strip()


def extract_generators(document_html: str) -> list[str]:
    values = []
    for match in META_GENERATOR_RE.finditer(document_html):
        value = SPACE_RE.sub(" ", unescape(match.group(1))).strip()
        if value and value not in values:
            values.append(value)
    return values


def extract_main(document_html: str) -> str:
    match = MAIN_RE.search(document_html)
    if match:
        return match.group(1)
    return document_html


def canonicalize_color(raw_color: str) -> str:
    color = raw_color.strip().lower()
    short_match = HEX_SHORT_RE.match(color)
    if short_match:
        token = short_match.group(1)
        return "#" + "".join(ch * 2 for ch in token)
    long_match = HEX_LONG_RE.match(color)
    if long_match:
        return "#" + long_match.group(1)
    color = color.replace(" ", "")
    return color


def clean_font_name(raw_font: str) -> str:
    value = raw_font.strip().strip("\"'")
    lower = value.lower()
    if not value:
        return ""
    if lower.startswith("var("):
        return ""
    if lower in {
        "inherit",
        "initial",
        "unset",
        "serif",
        "sans-serif",
        "monospace",
        "cursive",
        "fantasy",
        "system-ui",
        "-apple-system",
        "emoji",
        "math",
        "fangsong",
        "ui-sans-serif",
        "ui-serif",
        "ui-monospace",
        "none",
    }:
        return ""
    return value


def is_tracking_asset(url: str, width: str = "", height: str = "") -> bool:
    url_lower = url.lower()
    if "facebook.com/tr" in url_lower:
        return True
    if width == "1" and height == "1":
        return True
    return False


def is_brand_font(font_name: str) -> bool:
    lower = font_name.lower()
    if lower in GENERIC_FONT_NAMES:
        return False
    if any(token in lower for token in {"font awesome", "fontawesome", "eicons", "jupiterx"}):
        return False
    return True


def is_logo_asset_url(url: str) -> bool:
    path = urlsplit(url).path.lower()
    return any(
        token in path
        for token in {"colored-logo", "n1-payments-logo", "favicon-2"}
    )


def extract_font_names(raw_value: str) -> list[str]:
    fonts = []
    for part in raw_value.split(","):
        font = clean_font_name(part)
        if font and font not in fonts:
            fonts.append(font)
    return fonts


def extract_google_fonts(url: str) -> list[str]:
    query = parse_qs(urlsplit(url).query)
    family_values = query.get("family", [])
    fonts = []
    for family_value in family_values:
        for item in family_value.split("|"):
            name = item.split(":")[0].replace("+", " ").strip()
            font = clean_font_name(name)
            if font and font not in fonts:
                fonts.append(font)
    return fonts


def classify_zone(tag: str, attrs: dict[str, str], current_zone: str) -> str:
    if tag in {"header", "nav"}:
        return "header"
    if tag in {"footer"}:
        return "footer"
    if tag == "main":
        return "main"

    role = attrs.get("role", "").lower()
    if role in {"banner", "navigation"}:
        return "header"
    if role == "contentinfo":
        return "footer"
    if role == "main":
        return "main"

    class_value = (attrs.get("class", "") + " " + attrs.get("id", "")).lower()
    if any(token in class_value for token in {"header", "nav-menu", "site-logo"}):
        return "header"
    if "footer" in class_value:
        return "footer"
    if any(token in class_value for token in {"jupiterx-main", "main-content", "content-area"}):
        return "main"

    return current_zone


def unique_asset_entries(entries: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    unique = []
    for entry in entries:
        if is_tracking_asset(entry.get("url", ""), entry.get("width", ""), entry.get("height", "")):
            continue
        key = (
            entry.get("asset_type", ""),
            entry.get("url", ""),
            entry.get("zone", ""),
            entry.get("alt", ""),
            entry.get("class", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(entry)
    return unique


class PageAssetParser(HTMLParser):
    def __init__(self, page_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.page_url = page_url
        self.stack: list[str] = []
        self.zone_stack: list[str] = ["document"]
        self.stylesheets: list[str] = []
        self.icons: list[dict[str, str]] = []
        self.images: list[dict[str, str]] = []
        self.inline_styles: list[str] = []
        self.meta: dict[str, str] = {}
        self._in_style_tag = False
        self._style_buffer: list[str] = []

    def current_zone(self) -> str:
        return self.zone_stack[-1]

    def push_style_asset(self, raw_url: str, tag: str, attrs: dict[str, str]) -> None:
        url = normalize_asset_url(raw_url, self.page_url)
        if not url:
            return
        self.images.append(
            {
                "asset_type": "background-image",
                "url": url,
                "zone": self.current_zone(),
                "tag": tag,
                "alt": "",
                "width": attrs.get("width", ""),
                "height": attrs.get("height", ""),
                "class": attrs.get("class", ""),
                "source": "inline-style",
            }
        )

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = {key.lower(): (value or "") for key, value in attrs_list}
        zone = classify_zone(tag, attrs, self.current_zone())
        self.stack.append(tag)
        self.zone_stack.append(zone)

        if tag == "style":
            self._in_style_tag = True
            self._style_buffer = []
            return

        if tag == "meta":
            name = attrs.get("name", "").lower()
            prop = attrs.get("property", "").lower()
            content = attrs.get("content", "").strip()
            if name == "theme-color" and content:
                self.meta["theme-color"] = content
            if prop == "og:image" and content:
                self.meta["og:image"] = content
            return

        if tag == "link":
            rel_tokens = {token.lower() for token in attrs.get("rel", "").split()}
            href = normalize_asset_url(attrs.get("href", ""), self.page_url)
            if href and "stylesheet" in rel_tokens:
                self.stylesheets.append(href)
            if href and rel_tokens.intersection({"icon", "apple-touch-icon", "mask-icon"}):
                self.icons.append(
                    {
                        "rel": " ".join(sorted(rel_tokens)),
                        "url": href,
                        "sizes": attrs.get("sizes", ""),
                        "type": attrs.get("type", ""),
                    }
                )
            return

        if tag == "img":
            url = (
                normalize_asset_url(attrs.get("src", ""), self.page_url)
                or normalize_asset_url(attrs.get("data-src", ""), self.page_url)
            )
            if url:
                self.images.append(
                    {
                        "asset_type": "image",
                        "url": url,
                        "zone": self.current_zone(),
                        "tag": tag,
                        "alt": attrs.get("alt", "").strip(),
                        "width": attrs.get("width", ""),
                        "height": attrs.get("height", ""),
                        "class": attrs.get("class", ""),
                        "source": "img",
                    }
                )
            srcset = attrs.get("srcset", "")
            for candidate in srcset.split(","):
                parts = candidate.strip().split()
                if not parts:
                    continue
                srcset_url = normalize_asset_url(parts[0], self.page_url)
                if srcset_url:
                    self.images.append(
                        {
                            "asset_type": "responsive-image",
                            "url": srcset_url,
                            "zone": self.current_zone(),
                            "tag": tag,
                            "alt": attrs.get("alt", "").strip(),
                            "width": "",
                            "height": "",
                            "class": attrs.get("class", ""),
                            "source": "srcset",
                        }
                    )

        style_value = attrs.get("style", "")
        if style_value and "url(" in style_value.lower():
            for raw_url in URL_IN_STYLE_RE.findall(style_value):
                self.push_style_asset(raw_url, tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if self._in_style_tag and tag == "style":
            style_text = "".join(self._style_buffer).strip()
            if style_text:
                self.inline_styles.append(style_text)
            self._style_buffer = []
            self._in_style_tag = False

        if self.stack:
            self.stack.pop()
        if len(self.zone_stack) > 1:
            self.zone_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._in_style_tag:
            self._style_buffer.append(data)


def fetch_page(url: str) -> tuple[str, str]:
    return url, fetch_text(url)


def fetch_stylesheet(url: str) -> tuple[str, str]:
    return url, fetch_text(url)


def build_manifest() -> dict[str, object]:
    sitemap_urls = parse_sitemap(SITEMAP_URL)

    html_by_url: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(fetch_page, url): url for url in sitemap_urls}
        for future in as_completed(futures):
            url, html = future.result()
            html_by_url[url] = html

    pages = []
    unique_stylesheets = set()
    all_inline_styles: list[str] = []
    generator_counter: Counter[str] = Counter()

    for url in sitemap_urls:
        html = html_by_url[url]
        parser = PageAssetParser(url)
        parser.feed(html)
        parser.close()

        title = extract_title(html)
        generators = extract_generators(html)
        generator_counter.update(generators)
        page_record = {
            "url": url,
            "title": title,
            "generators": generators,
            "stylesheets": sorted(set(parser.stylesheets)),
            "icons": parser.icons,
            "images": unique_asset_entries(parser.images),
            "main_html_length": len(extract_main(html)),
            "meta": parser.meta,
        }
        unique_stylesheets.update(page_record["stylesheets"])
        all_inline_styles.extend(parser.inline_styles)
        pages.append(page_record)

    stylesheet_texts: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(fetch_stylesheet, url): url for url in sorted(unique_stylesheets)
        }
        for future in as_completed(futures):
            url, css_text = future.result()
            stylesheet_texts[url] = css_text

    font_counter: Counter[str] = Counter()
    color_counter: Counter[str] = Counter()
    css_var_counter: Counter[str] = Counter()
    css_var_values: defaultdict[str, Counter[str]] = defaultdict(Counter)

    for stylesheet_url, css_text in stylesheet_texts.items():
        for font in extract_google_fonts(stylesheet_url):
            font_counter[font] += 1
        for raw_font_value in FONT_FAMILY_RE.findall(css_text):
            for font in extract_font_names(raw_font_value):
                font_counter[font] += 1
        for raw_color in COLOR_RE.findall(css_text):
            color_counter[canonicalize_color(raw_color)] += 1
        for var_name, raw_value in CSS_VAR_RE.findall(css_text):
            value = SPACE_RE.sub(" ", raw_value).strip()
            css_var_counter[var_name] += 1
            css_var_values[var_name][value] += 1

    for style_text in all_inline_styles:
        for raw_font_value in FONT_FAMILY_RE.findall(style_text):
            for font in extract_font_names(raw_font_value):
                font_counter[font] += 1
        for raw_color in COLOR_RE.findall(style_text):
            color_counter[canonicalize_color(raw_color)] += 1
        for var_name, raw_value in CSS_VAR_RE.findall(style_text):
            value = SPACE_RE.sub(" ", raw_value).strip()
            css_var_counter[var_name] += 1
            css_var_values[var_name][value] += 1

    asset_counter: Counter[str] = Counter()
    asset_page_counter: defaultdict[str, set[str]] = defaultdict(set)
    asset_zone_counter: defaultdict[str, Counter[str]] = defaultdict(Counter)
    alt_counter: Counter[str] = Counter()

    for page in pages:
        for image in page["images"]:
            url = image["url"]
            asset_counter[url] += 1
            asset_page_counter[url].add(page["url"])
            asset_zone_counter[url][image["zone"]] += 1
            alt = image.get("alt", "").strip()
            if alt:
                alt_counter[alt] += 1

    repeated_assets = []
    for asset_url, occurrences in asset_counter.most_common():
        pages_using = sorted(asset_page_counter[asset_url])
        repeated_assets.append(
            {
                "url": asset_url,
                "occurrences": occurrences,
                "pages_using": pages_using,
                "page_count": len(pages_using),
                "zones": dict(asset_zone_counter[asset_url]),
            }
        )

    logo_candidates = []
    shared_header_assets = []
    shared_footer_assets = []
    logo_candidates = []
    for asset in repeated_assets:
        url_lower = asset["url"].lower()
        if is_tracking_asset(asset["url"]):
            continue
        if asset["zones"].get("header") and asset["page_count"] >= 20:
            shared_header_assets.append(asset)
        if asset["zones"].get("footer") and asset["page_count"] >= 20:
            shared_footer_assets.append(asset)
        if is_logo_asset_url(asset["url"]):
            logo_candidates.append(asset)

    shared_navigation_icons = []
    logo_urls = {asset["url"] for asset in logo_candidates}
    for asset in shared_header_assets:
        if asset["url"] not in logo_urls:
            shared_navigation_icons.append(asset)

    brand_font_counts = Counter()
    for font_name, count in font_counter.items():
        if is_brand_font(font_name) and count >= 20:
            brand_font_counts[font_name] = count

    top_colors = [
        {"value": color, "count": count}
        for color, count in color_counter.most_common(20)
    ]
    likely_brand_colors = [
        {"value": color, "count": count}
        for color, count in color_counter.most_common()
        if color not in NEUTRAL_COLOR_VALUES
    ][:12]
    top_fonts = [
        {"name": font, "count": count}
        for font, count in font_counter.most_common(20)
    ]
    brand_fonts = [
        {"name": font, "count": count}
        for font, count in brand_font_counts.most_common(12)
    ]
    top_css_vars = []
    for var_name, count in css_var_counter.most_common(20):
        top_css_vars.append(
            {
                "name": var_name,
                "count": count,
                "top_values": [
                    {"value": value, "count": value_count}
                    for value, value_count in css_var_values[var_name].most_common(5)
                ],
            }
        )

    brand_css_variables = []
    for var_name, count in css_var_counter.most_common():
        lowered = var_name.lower()
        if not any(token in lowered for token in {"color", "font", "typography", "background"}):
            continue
        brand_css_variables.append(
            {
                "name": var_name,
                "count": count,
                "top_values": [
                    {"value": value, "count": value_count}
                    for value, value_count in css_var_values[var_name].most_common(5)
                ],
            }
        )

    theme_global_colors = [
        entry
        for entry in brand_css_variables
        if entry["name"].startswith("--e-global-color-")
    ]
    theme_global_typography = [
        entry
        for entry in brand_css_variables
        if entry["name"].startswith("--e-global-typography-")
    ]

    theme_font_family_counter = Counter()
    for entry in theme_global_typography:
        if not entry["name"].endswith("-font-family"):
            continue
        for value_entry in entry["top_values"]:
            font_name = clean_font_name(value_entry["value"])
            if font_name:
                theme_font_family_counter[font_name] += value_entry["count"]

    theme_font_families = [
        {"name": font, "count": count}
        for font, count in theme_font_family_counter.most_common()
    ]

    site_icons = []
    seen_icon_urls = set()
    for page in pages:
        for icon in page["icons"]:
            if icon["url"] in seen_icon_urls:
                continue
            seen_icon_urls.add(icon["url"])
            site_icons.append(icon)

    manifest = {
        "site": BASE_URL,
        "sitemap_url": SITEMAP_URL,
        "page_count": len(pages),
        "generators": [
            {"value": value, "count": count}
            for value, count in generator_counter.most_common()
        ],
        "stylesheets": sorted(unique_stylesheets),
        "stylesheet_count": len(unique_stylesheets),
        "top_fonts": top_fonts,
        "brand_fonts": brand_fonts,
        "top_colors": top_colors,
        "likely_brand_colors": likely_brand_colors,
        "top_css_variables": top_css_vars,
        "brand_css_variables": brand_css_variables,
        "theme_global_colors": theme_global_colors,
        "theme_global_typography": theme_global_typography,
        "theme_font_families": theme_font_families,
        "site_icons": site_icons,
        "logo_candidates": logo_candidates,
        "shared_header_assets": shared_header_assets,
        "shared_footer_assets": shared_footer_assets,
        "shared_navigation_icons": shared_navigation_icons,
        "top_alt_texts": [
            {"value": value, "count": count}
            for value, count in alt_counter.most_common(20)
        ],
        "repeated_assets": repeated_assets,
        "pages": pages,
    }
    return manifest


def summarize_page_images(page: dict[str, object]) -> list[dict[str, str]]:
    summary = []
    seen = set()
    for image in page["images"]:
        url = image["url"]
        if url in seen:
            continue
        seen.add(url)
        summary.append(
            {
                "asset_type": image["asset_type"],
                "zone": image["zone"],
                "alt": image["alt"],
                "url": url,
            }
        )
    return summary


def best_css_var_value(entry: dict[str, object]) -> str:
    values = entry.get("top_values", [])
    if not values:
        return ""
    return values[0]["value"]


def write_manifest(manifest: dict[str, object]) -> None:
    with open(ASSET_MANIFEST_PATH, "w", encoding="utf-8") as output_file:
        json.dump(manifest, output_file, indent=2, ensure_ascii=False)


def write_report(manifest: dict[str, object]) -> None:
    pages = manifest["pages"]
    stylesheets = manifest["stylesheets"]
    top_colors = manifest["top_colors"]
    likely_brand_colors = manifest["likely_brand_colors"]
    top_fonts = manifest["top_fonts"]
    brand_fonts = manifest["brand_fonts"]
    brand_css_variables = manifest["brand_css_variables"]
    theme_global_colors = manifest["theme_global_colors"]
    theme_global_typography = manifest["theme_global_typography"]
    theme_font_families = manifest["theme_font_families"]
    logo_candidates = manifest["logo_candidates"]
    shared_navigation_icons = manifest["shared_navigation_icons"]
    site_icons = manifest["site_icons"]
    generators = manifest["generators"]

    with open(BRAND_REPORT_PATH, "w", encoding="utf-8") as output_file:
        output_file.write("# N1 Payments Brand + Style Audit\n\n")
        output_file.write(f"- Site: {manifest['site']}\n")
        output_file.write(f"- Pages crawled from sitemap: {manifest['page_count']}\n")
        output_file.write(f"- Unique stylesheet URLs: {manifest['stylesheet_count']}\n")
        output_file.write(f"- Manifest: `{ASSET_MANIFEST_PATH}`\n\n")

        output_file.write("## Platform Signals\n\n")
        for item in generators:
            output_file.write(f"- {item['value']} ({item['count']} pages)\n")
        output_file.write("\n")

        output_file.write("## Branding Signals\n\n")
        if logo_candidates:
            output_file.write("### Logo / Repeated Brand Asset Candidates\n\n")
            for asset in logo_candidates[:12]:
                output_file.write(
                    f"- {asset['url']} "
                    f"(pages: {asset['page_count']}, zones: {asset['zones']})\n"
                )
            output_file.write("\n")

        if site_icons:
            output_file.write("### Site Icons / Favicons\n\n")
            for icon in site_icons[:12]:
                output_file.write(
                    f"- {icon['rel']} -> {icon['url']} "
                    f"(sizes: {icon['sizes'] or 'n/a'}, type: {icon['type'] or 'n/a'})\n"
                )
            output_file.write("\n")

        if shared_navigation_icons:
            output_file.write("### Shared Header Navigation Icons\n\n")
            for asset in shared_navigation_icons[:12]:
                output_file.write(
                    f"- {asset['url']} "
                    f"(pages: {asset['page_count']}, zones: {asset['zones']})\n"
                )
            output_file.write("\n")

        output_file.write("### Likely Brand Fonts\n\n")
        for font in brand_fonts[:12]:
            output_file.write(f"- {font['name']} ({font['count']} mentions)\n")
        output_file.write("\n")

        output_file.write("### Theme Font Families\n\n")
        for font in theme_font_families[:12]:
            output_file.write(f"- {font['name']} ({font['count']} token matches)\n")
        output_file.write("\n")

        output_file.write("### Frequent Fonts (Including Framework Fonts)\n\n")
        for font in top_fonts[:12]:
            output_file.write(f"- {font['name']} ({font['count']} mentions)\n")
        output_file.write("\n")

        output_file.write("### Theme Global Colors\n\n")
        for entry in theme_global_colors[:20]:
            output_file.write(
                f"- {entry['name']} = {best_css_var_value(entry)} "
                f"({entry['count']} matches)\n"
            )
        output_file.write("\n")

        output_file.write("### Likely Brand Colors\n\n")
        for color in likely_brand_colors[:12]:
            output_file.write(f"- {color['value']} ({color['count']} matches)\n")
        output_file.write("\n")

        output_file.write("### Frequent Colors\n\n")
        for color in top_colors[:15]:
            output_file.write(f"- {color['value']} ({color['count']} matches)\n")
        output_file.write("\n")

        output_file.write("### Brand-Related CSS Variables\n\n")
        for entry in brand_css_variables[:20]:
            output_file.write(
                f"- {entry['name']} = {best_css_var_value(entry)} "
                f"({entry['count']} matches)\n"
            )
        output_file.write("\n")

        output_file.write("### Theme Global Typography Tokens\n\n")
        for entry in theme_global_typography[:30]:
            output_file.write(
                f"- {entry['name']} = {best_css_var_value(entry)} "
                f"({entry['count']} matches)\n"
            )
        output_file.write("\n")

        output_file.write("## Stylesheet URLs\n\n")
        for url in stylesheets:
            output_file.write(f"- {url}\n")
        output_file.write("\n")

        output_file.write("## Page Asset Inventory\n\n")
        for page in pages:
            output_file.write(f"### {page['title']}\n\n")
            output_file.write(f"- URL: {page['url']}\n")
            output_file.write(
                f"- Stylesheets on page: {len(page['stylesheets'])}\n"
            )
            output_file.write(f"- Icons on page: {len(page['icons'])}\n")
            output_file.write(f"- Image assets on page: {len(page['images'])}\n")
            if page["meta"]:
                output_file.write(f"- Meta signals: {page['meta']}\n")
            images = summarize_page_images(page)
            if images:
                output_file.write("- Assets:\n")
                for image in images[:25]:
                    alt_text = image["alt"] or "(no alt)"
                    output_file.write(
                        f"  - [{image['asset_type']}] [{image['zone']}] "
                        f"{alt_text} -> {image['url']}\n"
                    )
                if len(images) > 25:
                    output_file.write(
                        f"  - ... {len(images) - 25} more assets in manifest\n"
                    )
            output_file.write("\n")


def main() -> int:
    manifest = build_manifest()
    write_manifest(manifest)
    write_report(manifest)
    print(
        f"Wrote {BRAND_REPORT_PATH} and {ASSET_MANIFEST_PATH} "
        f"for {manifest['page_count']} pages."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
