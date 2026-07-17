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
- `api_regular_price_yen`: price returned by Dospara's product API before product-page verification
- `coupon_discount_yen`: coupon discount amount
- `coupon_price_yen`: `regular_price_yen - coupon_discount_yen`
- `coupon_code`
- `campaign_source_url`: campaign page each item came from
- `campaign_title`
- `campaign_end_text`
- `coupon_verified`: `true` only when the same coupon is active on the product page
- `coupon_verification_error`: reason a parsed campaign card was rejected, included under `coupon_verification.rejected_items`
- `product_page_regular_price_yen`: current `productJson.amttax` value read from the product page
- `product_page_stock`: current `productJson.stkname` value read from the product page
- `product_page_verified_at`: timestamp for the product-page snapshot
- `product_page_price_matches_api`: whether the product API and product-page prices matched during the run
- `coupon_expires_at`: machine-readable coupon deadline when the product page supplies a full date
- `source_url`: primary campaign page for this run
- `source_urls`: all campaign pages used for this run
- `pages`: per-campaign metadata and item counts
- `coupon_verification`: product-page verification summary
- `discovery`: inspected candidate pages and whether the fallback URL was used

Campaign pages can retain stale coupon cards after a quantity-limited coupon ends. By default the tool verifies every parsed campaign coupon against the product page and only outputs items where the product page still contains the same active product ID, coupon code, discount amount, current price, stock state, and unexpired deadline. The product-page price and stock become the final values; the earlier product API values remain in `api_regular_price_yen` and `api_stock` for discrepancy reporting. Rejected stale cards are reported in `coupon_verification.rejected_items`.

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

Skip product-page coupon verification:

```bash
python3 dospara_coupon_tool.py --no-product-page-verification
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

The primary JSON URL for ChatGPT Tasks is the branch raw file with a unique cache-busting query on every run:

```text
https://raw.githubusercontent.com/chijimi33/Dospara-coupon-price-tool/main/public/dospara_coupons.json?cache_bust=YYYYMMDDHHmm
```

Some ChatGPT retrieval environments reject the redirect used by GitHub Release downloads. The raw URL with a per-run query avoids that redirect while still bypassing stale branch responses.

Only notify Dospara coupon products when each item has:

```json
{
  "coupon_verified": true
}
```

Treat `coupon_verified: false`, `null`, or a missing field as not notification-eligible. If `coupon_verification.enabled` is missing or false at the top level, do not use coupon-only Dospara deals as confirmed notifications.

For a fresh item with `coupon_verified: true`, `product_page_product_id` matching `product_id`, and a recent `product_page_verified_at`, the JSON already contains a successful product-page check performed by GitHub Actions. A ChatGPT Task that cannot reopen the same product page may report that limitation, but it does not need to turn the entire run into a monitoring error or discard the item. Only a newer, directly fetched official product page with contradictory structured product data should override this snapshot; search snippets and cached page text are not sufficient.

The workflow also overwrites a rolling release asset on every successful run. Use it as the first fallback:

```text
https://github.com/chijimi33/Dospara-coupon-price-tool/releases/download/dospara-coupons-latest/dospara_coupons.json
```

The branch URL without a query remains available for manual checks, but Tasks should not use it as the only route because an intermediary may cache it:

```text
https://raw.githubusercontent.com/chijimi33/Dospara-coupon-price-tool/main/public/dospara_coupons.json
```

If the release asset and branch fallback both fail, and the task can access the GitHub API, resolve the current `main` commit and fetch the commit-pinned raw file:

```text
https://api.github.com/repos/chijimi33/Dospara-coupon-price-tool/git/ref/heads/main
```

Extract `object.sha`, then fetch:

```text
https://raw.githubusercontent.com/chijimi33/Dospara-coupon-price-tool/{object.sha}/public/dospara_coupons.json
```

If `fetched_at` is more than 12 hours old, retry using the fallback URLs above before treating the data as stale. Do not use stale coupon data to resurrect coupons that are absent or unverified on the latest product-page verification run.

After pushing this repository to GitHub, run `Update Dospara coupon data` once manually from the GitHub Actions tab.

If the workflow cannot push generated files, open:

```text
Settings -> Actions -> General -> Workflow permissions
```

Then set it to `Read and write permissions`.
