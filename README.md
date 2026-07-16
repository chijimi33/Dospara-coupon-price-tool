# Dospara coupon price tool

`dospara_coupon_tool.py` extracts coupon products from current Dospara PC parts/peripherals coupon campaigns.

By default it scans the live campaign list first:

https://www.dospara.co.jp/campaign-list

Then it inspects likely campaign pages and aggregates every page that actually contains coupon products, including temporary campaigns such as settlement sales or DIY PC events. The previous fixed page is still used as a fallback when discovery finds no coupon pages:

https://www.dospara.co.jp/event/diy_parts_accessory.html

It joins two sources on the page:

- coupon amount and coupon code from the campaign HTML
- product name, regular tax-included price, stock text, and product URL from Dospara's `/s/dospara/api/getProducts` endpoint

The output includes:

- `regular_price_yen`: normal tax-included price shown by Dospara
- `coupon_discount_yen`: coupon discount amount
- `coupon_price_yen`: `regular_price_yen - coupon_discount_yen`
- `coupon_code`
- `campaign_source_url`: campaign page each item came from
- `campaign_title`
- `campaign_end_text`
- `source_url`: primary campaign page for this run
- `source_urls`: all campaign pages used for this run
- `pages`: per-campaign metadata and item counts
- `discovery`: inspected candidate pages and whether the fallback URL was used

## Usage

```bash
python3 dospara_coupon_tool.py
```

Use a fixed campaign page instead of auto discovery:

```bash
python3 dospara_coupon_tool.py https://www.dospara.co.jp/event/diy_parts_accessory.html
```

Output as CSV:

```bash
python3 dospara_coupon_tool.py --format csv --output dospara_coupons.csv
```

Markdown table for quick reading:

```bash
python3 dospara_coupon_tool.py --format markdown
```

Only parse the HTML and skip the product API:

```bash
python3 dospara_coupon_tool.py --no-api
```

Add another page to scan during auto discovery:

```bash
python3 dospara_coupon_tool.py auto --discovery-url https://www.dospara.co.jp/campaign-list
```

If your local Python cannot find a CA bundle, specify one explicitly:

```bash
python3 dospara_coupon_tool.py --cafile /etc/ssl/cert.pem
```

As a last resort for this public price page:

```bash
python3 dospara_coupon_tool.py --insecure-tls
```

Use from another Python script:

```python
from dospara_coupon_tool import get_dospara_coupon_prices

data = get_dospara_coupon_prices()
for item in data["items"]:
    print(item["product_id"], item["regular_price_yen"], item["coupon_price_yen"])
```

No third-party packages are required.

## GitHub Actions publishing

The workflow in `.github/workflows/publish-dospara-coupons.yml` runs every 6 hours, auto-discovers current Dospara coupon campaign pages, and commits static files under `public/`:

- `dospara_coupons.json`
- `dospara_coupons.csv`
- `index.html`

It can also be started manually from the GitHub Actions tab with `workflow_dispatch`.

The JSON URL for ChatGPT Tasks is:

```text
https://raw.githubusercontent.com/chijimi33/Dospara-coupon-price-tool/main/public/dospara_coupons.json
```

For ChatGPT Tasks, the most reliable fetch flow is to resolve the current `main` commit first and then fetch the commit-pinned raw file. This avoids stale `raw.githubusercontent.com/.../main/...` cache responses:

```text
https://api.github.com/repos/chijimi33/Dospara-coupon-price-tool/git/ref/heads/main
```

Extract `object.sha`, then fetch:

```text
https://raw.githubusercontent.com/chijimi33/Dospara-coupon-price-tool/{object.sha}/public/dospara_coupons.json
```

If the task must use the branch URL directly, append a unique cache-busting query string for each run:

```text
https://raw.githubusercontent.com/chijimi33/Dospara-coupon-price-tool/main/public/dospara_coupons.json?cache_bust=YYYYMMDDHHmm
```

If `fetched_at` is more than 12 hours old, retry using the commit-pinned flow above before treating the data as stale.

After pushing this repository to GitHub, run `Update Dospara coupon data` once manually from the GitHub Actions tab.

If the workflow cannot push generated files, open:

```text
Settings -> Actions -> General -> Workflow permissions
```

Then set it to `Read and write permissions`.
