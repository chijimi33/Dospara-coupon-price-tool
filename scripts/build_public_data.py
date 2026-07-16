#!/usr/bin/env python3
"""Build static public data files."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dospara_coupon_tool import get_dospara_coupon_prices, render_csv


def build_public_data(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    result = get_dospara_coupon_prices()

    json_path = output_dir / "dospara_coupons.json"
    csv_path = output_dir / "dospara_coupons.csv"
    index_path = output_dir / "index.html"
    nojekyll_path = output_dir / ".nojekyll"

    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    csv_path.write_text(render_csv(result), encoding="utf-8", newline="")
    index_path.write_text(render_index(result), encoding="utf-8")
    nojekyll_path.write_text("", encoding="utf-8")

    return result


def render_index(result: dict[str, Any]) -> str:
    page = result.get("page") or {}
    pages = result.get("pages") or []
    verification = result.get("coupon_verification") or {}
    items = result.get("items") or []
    sample_rows = "\n".join(render_item_row(item) for item in items[:10])

    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Dospara Coupon Data</title>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 2rem; line-height: 1.6; }}
    code {{ background: #f4f4f4; padding: 0.1rem 0.25rem; border-radius: 4px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
    th, td {{ border: 1px solid #ddd; padding: 0.5rem; text-align: left; vertical-align: top; }}
    th {{ background: #f7f7f7; }}
  </style>
</head>
<body>
  <h1>Dospara Coupon Data</h1>
  <p>ドスパラ公式セールページから抽出したクーポン補助データです。</p>
  <ul>
    <li>Primary source: <a href="{escape_attr(result.get("source_url"))}">{escape(result.get("source_url"))}</a></li>
    <li>Source count: {len(pages)}</li>
    <li>Fetched at: <code>{escape(result.get("fetched_at"))}</code></li>
    <li>Page title: {escape(page.get("title"))}</li>
    <li>Campaign end text: {escape(page.get("campaign_end_text"))}</li>
    <li>Item count: {len(items)}</li>
    <li>Product-page coupon verification: {escape("enabled" if verification.get("enabled") else "disabled")}</li>
    <li>Rejected stale coupon cards: {escape(verification.get("rejected_item_count", 0))}</li>
  </ul>
  {render_source_list(pages)}
  <p>
    <a href="./dospara_coupons.json">dospara_coupons.json</a>
    /
    <a href="./dospara_coupons.csv">dospara_coupons.csv</a>
  </p>
  <h2>Preview</h2>
  <table>
    <thead>
      <tr>
        <th>Product</th>
        <th>Campaign</th>
        <th>Regular</th>
        <th>Coupon</th>
        <th>After coupon</th>
        <th>Stock</th>
      </tr>
    </thead>
    <tbody>
      {sample_rows}
    </tbody>
  </table>
</body>
</html>
"""


def render_source_list(pages: list[dict[str, Any]]) -> str:
    if not pages:
        return ""

    rows = "\n".join(
        f'<li><a href="{escape_attr(page.get("source_url"))}">{escape(page.get("title") or page.get("source_url"))}</a>'
        f' ({escape(page.get("campaign_end_text"))}, {escape(page.get("count"))} verified'
        f' / {escape(page.get("parsed_count", page.get("count")))} parsed)</li>'
        for page in pages
    )
    return f"""<h2>Sources</h2>
  <ul>
    {rows}
  </ul>"""


def render_item_row(item: dict[str, Any]) -> str:
    product_name = item.get("product_name") or item.get("product_id") or ""
    product_url = item.get("product_url") or ""
    product_cell = f'<a href="{escape_attr(product_url)}">{escape(product_name)}</a>' if product_url else escape(product_name)

    return f"""<tr>
        <td>{product_cell}</td>
        <td>{escape(item.get("campaign_title"))}<br><a href="{escape_attr(item.get("campaign_source_url"))}">source</a></td>
        <td>{format_yen(item.get("regular_price_yen"))}</td>
        <td>{format_yen(item.get("coupon_discount_yen"))}<br><code>{escape(item.get("coupon_code"))}</code></td>
        <td>{format_yen(item.get("coupon_price_yen"))}</td>
        <td>{escape(item.get("stock"))}</td>
      </tr>"""


def format_yen(value: Any) -> str:
    if value is None:
        return ""
    try:
        return f"{int(value):,}円"
    except (TypeError, ValueError):
        return escape(value)


def escape(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=False)


def escape_attr(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build public files for Dospara coupon data.")
    parser.add_argument("--output-dir", default="public", type=Path)
    args = parser.parse_args()

    result = build_public_data(args.output_dir)
    print(f"Wrote {result['count']} items to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
