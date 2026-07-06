# Dospara coupon price tool

`dospara_coupon_tool.py` extracts coupon products from:

https://www.dospara.co.jp/event/diy_parts_accessory.html

It joins two sources on the page:

- coupon amount and coupon code from the campaign HTML
- product name, regular tax-included price, stock text, and product URL from Dospara's `/s/dospara/api/getProducts` endpoint

The output includes:

- `regular_price_yen`: normal tax-included price shown by Dospara
- `coupon_discount_yen`: coupon discount amount
- `coupon_price_yen`: `regular_price_yen - coupon_discount_yen`
- `coupon_code`

## Usage

```bash
python3 dospara_coupon_tool.py
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

The workflow in `.github/workflows/publish-dospara-coupons.yml` runs every 6 hours and commits static files under `public/`:

- `dospara_coupons.json`
- `dospara_coupons.csv`
- `index.html`

It can also be started manually from the GitHub Actions tab with `workflow_dispatch`.

The JSON URL for ChatGPT Tasks is:

```text
https://raw.githubusercontent.com/chijimi33/Dospara-coupon-price-tool/main/public/dospara_coupons.json
```

After pushing this repository to GitHub, run `Update Dospara coupon data` once manually from the GitHub Actions tab.

If the workflow cannot push generated files, open:

```text
Settings -> Actions -> General -> Workflow permissions
```

Then set it to `Read and write permissions`.
