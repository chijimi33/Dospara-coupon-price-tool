#!/usr/bin/env python3
"""Fetch Dospara coupon products and return regular/coupon prices.

The target page stores coupon amounts in HTML classes such as
``coupon-wrapper coupon-5000`` and fills product prices through
``/s/dospara/api/getProducts``. This module joins those two sources.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import io
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_PAGE_URL = "https://www.dospara.co.jp/event/diy_parts_accessory.html"
DEFAULT_TIMEOUT = 20.0
DEFAULT_BATCH_SIZE = 50
COMMON_CA_BUNDLES = [
    "/etc/ssl/cert.pem",
    "/opt/homebrew/etc/openssl@3/cert.pem",
    "/opt/homebrew/etc/ca-certificates/cert.pem",
    "/usr/local/etc/openssl@3/cert.pem",
    "/usr/local/etc/openssl/cert.pem",
]

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
)

CSV_FIELDS = [
    "section",
    "product_id",
    "product_name",
    "regular_price_yen",
    "coupon_discount_yen",
    "coupon_price_yen",
    "coupon_code",
    "stock",
    "product_url",
]


@dataclass
class CouponItem:
    section: str | None
    product_id: str
    coupon_code: str | None
    coupon_discount_yen: int
    regular_price_yen: int | None = None
    coupon_price_yen: int | None = None
    product_name: str | None = None
    stock: str | None = None
    product_url: str | None = None
    image_url: str | None = None
    simple_spec: str | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "section": self.section,
            "product_id": self.product_id,
            "product_name": self.product_name,
            "regular_price_yen": self.regular_price_yen,
            "coupon_discount_yen": self.coupon_discount_yen,
            "coupon_price_yen": self.coupon_price_yen,
            "coupon_code": self.coupon_code,
            "stock": self.stock,
            "product_url": self.product_url,
            "image_url": self.image_url,
            "simple_spec": self.simple_spec,
        }


def fetch_text(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    method: str | None = None,
    cafile: str | None = None,
    insecure_tls: bool = False,
) -> str:
    request_headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    }
    if headers:
        request_headers.update(headers)

    request = urllib.request.Request(
        url,
        data=data,
        headers=request_headers,
        method=method,
    )
    urlopen_kwargs: dict[str, Any] = {"timeout": timeout}
    if urllib.parse.urlparse(url).scheme == "https":
        urlopen_kwargs["context"] = make_ssl_context(cafile=cafile, insecure_tls=insecure_tls)

    with urllib.request.urlopen(request, **urlopen_kwargs) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def make_ssl_context(*, cafile: str | None = None, insecure_tls: bool = False) -> ssl.SSLContext:
    if insecure_tls:
        return ssl._create_unverified_context()

    ca_bundle = cafile or find_ca_bundle()
    if ca_bundle:
        return ssl.create_default_context(cafile=ca_bundle)
    return ssl.create_default_context()


def find_ca_bundle() -> str | None:
    candidates = [
        os.environ.get("SSL_CERT_FILE"),
        ssl.get_default_verify_paths().cafile,
        *COMMON_CA_BUNDLES,
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return None


def strip_html_comments(markup: str) -> str:
    return re.sub(r"<!--.*?-->", "", markup, flags=re.DOTALL)


def clean_text(markup: str) -> str:
    markup = re.sub(r"<br\b[^>]*>", "\n", markup, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", markup)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_attrs(start_tag: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    attr_re = re.compile(
        r"""([:\w-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""",
        flags=re.DOTALL,
    )
    for match in attr_re.finditer(start_tag):
        value = match.group(2) or match.group(3) or match.group(4) or ""
        attrs[match.group(1).lower()] = html.unescape(value)
    return attrs


def extract_section_title(markup_without_comments: str, position: int) -> str | None:
    window = markup_without_comments[max(0, position - 30_000) : position]
    patterns = [
        r'<h2\b[^>]*class=["\'][^"\']*section-title[^"\']*["\'][^>]*>(.*?)</h2>',
        r'<h3\b[^>]*class=["\'][^"\']*section-subtitle[^"\']*["\'][^>]*>(.*?)</h3>',
    ]
    for pattern in patterns:
        matches = list(re.finditer(pattern, window, flags=re.IGNORECASE | re.DOTALL))
        if matches:
            title = clean_text(matches[-1].group(1))
            if title:
                return title
    return None


def extract_coupon_discount(card_html: str) -> int | None:
    wrapper_match = re.search(
        r'<div\b[^>]*class=["\'][^"\']*coupon-wrapper[^"\']*["\'][^>]*>',
        card_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if wrapper_match:
        class_match = re.search(r"\bcoupon-(\d+)\b", wrapper_match.group(0))
        if class_match:
            return int(class_match.group(1))

    text_match = re.search(r"(\d[\d,]*)\s*円\s*OFF", clean_text(card_html), flags=re.IGNORECASE)
    if text_match:
        return int(text_match.group(1).replace(",", ""))
    return None


def extract_coupon_code(card_html: str) -> str | None:
    code_match = re.search(
        r'<[^>]*class=["\'][^"\']*coupon-code__text[^"\']*["\'][^>]*>(.*?)</[^>]+>',
        card_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not code_match:
        return None

    code = clean_text(code_match.group(1))
    return code or None


def parse_coupon_items(page_html: str) -> list[CouponItem]:
    markup = strip_html_comments(page_html)
    items: list[CouponItem] = []
    seen: set[tuple[str, str | None, int]] = set()

    li_re = re.compile(r"(<li\b[^>]*>)(.*?)</li>", flags=re.IGNORECASE | re.DOTALL)
    for match in li_re.finditer(markup):
        start_tag = match.group(1)
        card_html = match.group(2)
        attrs = parse_attrs(start_tag)
        class_names = attrs.get("class", "")

        if "model-card" not in class_names or "get_product_data" not in class_names:
            continue
        if "coupon-wrapper" not in card_html:
            continue

        product_id = attrs.get("data-code")
        if not product_id:
            continue

        discount = extract_coupon_discount(card_html)
        if discount is None:
            continue

        coupon_code = extract_coupon_code(card_html)
        dedupe_key = (product_id, coupon_code, discount)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        items.append(
            CouponItem(
                section=extract_section_title(markup, match.start()),
                product_id=product_id,
                coupon_code=coupon_code,
                coupon_discount_yen=discount,
            )
        )

    return items


def chunked(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def fetch_product_info(
    product_ids: list[str],
    *,
    page_url: str,
    timeout: float = DEFAULT_TIMEOUT,
    batch_size: int = DEFAULT_BATCH_SIZE,
    cafile: str | None = None,
    insecure_tls: bool = False,
) -> dict[str, dict[str, Any]]:
    unique_ids = list(dict.fromkeys(product_ids))
    api_url = urllib.parse.urljoin(page_url, "/s/dospara/api/getProducts")
    product_info: dict[str, dict[str, Any]] = {}

    for batch in chunked(unique_ids, max(1, batch_size)):
        payload = {"paramList": [{"pid": product_id, "q": "", "kflg": ""} for product_id in batch]}
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        raw = fetch_text(
            api_url,
            timeout=timeout,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Origin": urllib.parse.urljoin(page_url, "/").rstrip("/"),
                "Referer": page_url,
            },
            cafile=cafile,
            insecure_tls=insecure_tls,
        )
        data = json.loads(raw)

        if data.get("returnCode") != "000000":
            message = data.get("errorMsg") or "Dospara product API returned an error"
            raise RuntimeError(message)

        for info in data.get("productInfoList", {}).values():
            product_id = info.get("productID")
            if product_id:
                product_info[str(product_id)] = info

    return product_info


def enrich_items(
    items: list[CouponItem],
    product_info: dict[str, dict[str, Any]],
    *,
    page_url: str,
) -> list[CouponItem]:
    for item in items:
        info = product_info.get(item.product_id)
        if not info:
            continue

        regular_price = parse_int(info.get("amttax"))
        item.regular_price_yen = regular_price
        item.coupon_price_yen = (
            max(regular_price - item.coupon_discount_yen, 0) if regular_price is not None else None
        )
        item.product_name = blank_to_none(info.get("pname"))
        item.stock = blank_to_none(info.get("stkname"))
        item.product_url = absolute_url(info.get("url"), page_url)
        item.image_url = absolute_url(info.get("imgurl"), page_url)
        item.simple_spec = blank_to_none(info.get("simplespec"))

    return items


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    digits = re.sub(r"\D", "", str(value))
    return int(digits) if digits else None


def blank_to_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def absolute_url(value: Any, base_url: str) -> str | None:
    text = blank_to_none(value)
    if not text:
        return None
    return urllib.parse.urljoin(base_url, text)


def extract_page_meta(page_html: str) -> dict[str, str | None]:
    title_match = re.search(r"<title\b[^>]*>(.*?)</title>", page_html, flags=re.IGNORECASE | re.DOTALL)
    return {
        "title": clean_text(title_match.group(1)) if title_match else None,
        "updated_text": extract_first_class_text(page_html, "hero-image__date-upper"),
        "campaign_end_text": extract_first_class_text(page_html, "hero-image__date-bottom"),
    }


def extract_first_class_text(page_html: str, class_name: str) -> str | None:
    match = re.search(
        rf'<[^>]*class=["\'][^"\']*{re.escape(class_name)}[^"\']*["\'][^>]*>(.*?)</div>',
        page_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    text = clean_text(match.group(1))
    return text or None


def get_dospara_coupon_prices(
    page_url: str = DEFAULT_PAGE_URL,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    batch_size: int = DEFAULT_BATCH_SIZE,
    html_text: str | None = None,
    fetch_prices: bool = True,
    in_stock_only: bool = False,
    cafile: str | None = None,
    insecure_tls: bool = False,
) -> dict[str, Any]:
    if html_text is None:
        html_text = fetch_text(page_url, timeout=timeout, cafile=cafile, insecure_tls=insecure_tls)

    items = parse_coupon_items(html_text)
    if fetch_prices and items:
        product_info = fetch_product_info(
            [item.product_id for item in items],
            page_url=page_url,
            timeout=timeout,
            batch_size=batch_size,
            cafile=cafile,
            insecure_tls=insecure_tls,
        )
        enrich_items(items, product_info, page_url=page_url)

    if in_stock_only:
        items = [item for item in items if "在庫なし" not in (item.stock or "")]

    records = [item.to_record() for item in items]
    return {
        "source_url": page_url,
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "page": extract_page_meta(html_text),
        "count": len(records),
        "items": records,
    }


def render_json(result: dict[str, Any], *, indent: int = 2) -> str:
    return json.dumps(result, ensure_ascii=False, indent=indent)


def render_csv(result: dict[str, Any]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(result["items"])
    return output.getvalue()


def render_markdown(result: dict[str, Any]) -> str:
    rows = [CSV_FIELDS]
    for item in result["items"]:
        rows.append([format_markdown_cell(item.get(field)) for field in CSV_FIELDS])

    widths = [max(len(str(row[index])) for row in rows) for index in range(len(CSV_FIELDS))]
    header = "| " + " | ".join(str(value).ljust(widths[index]) for index, value in enumerate(rows[0])) + " |"
    divider = "| " + " | ".join("-" * widths[index] for index in range(len(CSV_FIELDS))) + " |"
    body = [
        "| " + " | ".join(str(value).ljust(widths[index]) for index, value in enumerate(row)) + " |"
        for row in rows[1:]
    ]
    return "\n".join([header, divider, *body])


def format_markdown_cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("|", r"\|").replace("\n", " ")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract Dospara regular prices, coupon discounts, and after-coupon prices.",
    )
    parser.add_argument("url", nargs="?", default=DEFAULT_PAGE_URL, help="Dospara campaign page URL")
    parser.add_argument(
        "-f",
        "--format",
        choices=("json", "csv", "markdown"),
        default="json",
        help="Output format",
    )
    parser.add_argument("-o", "--output", help="Write output to this file instead of stdout")
    parser.add_argument("--html-file", help="Read campaign HTML from a local file instead of fetching it")
    parser.add_argument("--no-api", action="store_true", help="Do not call the product API")
    parser.add_argument("--in-stock-only", action="store_true", help="Drop items whose stock text contains '在庫なし'")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="HTTP timeout in seconds")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="Product API batch size")
    parser.add_argument("--cafile", help="CA bundle path for TLS verification")
    parser.add_argument(
        "--insecure-tls",
        action="store_true",
        help="Disable TLS certificate verification if this local Python cannot find a CA bundle",
    )
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation")
    return parser


def render_result(result: dict[str, Any], output_format: str, *, indent: int) -> str:
    if output_format == "json":
        return render_json(result, indent=indent)
    if output_format == "csv":
        return render_csv(result)
    if output_format == "markdown":
        return render_markdown(result)
    raise ValueError(f"Unsupported output format: {output_format}")


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    try:
        html_text = None
        if args.html_file:
            with open(args.html_file, "r", encoding="utf-8") as file:
                html_text = file.read()

        result = get_dospara_coupon_prices(
            args.url,
            timeout=args.timeout,
            batch_size=args.batch_size,
            html_text=html_text,
            fetch_prices=not args.no_api,
            in_stock_only=args.in_stock_only,
            cafile=args.cafile,
            insecure_tls=args.insecure_tls,
        )
        rendered = render_result(result, args.format, indent=args.indent)

        if args.output:
            with open(args.output, "w", encoding="utf-8", newline="") as file:
                file.write(rendered)
        else:
            print(rendered)
    except (OSError, urllib.error.URLError, json.JSONDecodeError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
