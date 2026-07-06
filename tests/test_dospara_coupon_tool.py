import unittest

from dospara_coupon_tool import enrich_items, parse_coupon_items


class DosparaCouponToolTest(unittest.TestCase):
    def test_parse_active_coupon_cards_and_ignore_comments(self):
        page_html = """
        <h2 class="section-title"><span>Limited items</span></h2>
        <!--
        <li class="model-card get_product_data" data-code="IC000000">
          <div class="coupon-wrapper coupon-9999">
            <div class="coupon-code__text">DEADCODE</div>
          </div>
        </li>
        -->
        <li class="model-card get_product_data" data-code="IC111111">
          <div class="coupon-wrapper coupon-5000">
            <div class="coupon-code__text">LIVEA</div>
          </div>
        </li>
        <h2 class="section-title"><span>Weekly coupons</span></h2>
        <li class="model-card get_product_data" data-code="IC222222">
          <div class="coupon-wrapper coupon-1000">
            <div class="coupon-code__text">LIVEB</div>
          </div>
        </li>
        """

        items = parse_coupon_items(page_html)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].product_id, "IC111111")
        self.assertEqual(items[0].coupon_discount_yen, 5000)
        self.assertEqual(items[0].coupon_code, "LIVEA")
        self.assertEqual(items[0].section, "Limited items")
        self.assertEqual(items[1].section, "Weekly coupons")

    def test_enrich_items_adds_prices_and_absolute_url(self):
        items = parse_coupon_items(
            """
            <h2 class="section-title"><span>Limited items</span></h2>
            <li class="model-card get_product_data" data-code="IC111111">
              <div class="coupon-wrapper coupon-5000">
                <div class="coupon-code__text">LIVEA</div>
              </div>
            </li>
            """
        )
        product_info = {
            "IC111111": {
                "productID": "IC111111",
                "pname": "Sample Product",
                "amttax": 19800,
                "stkname": "24 hours",
                "url": "/SBR1/IC111111.html",
                "imgurl": "https://example.test/image.jpg",
                "simplespec": "Sample spec",
            }
        }

        enrich_items(items, product_info, page_url="https://www.dospara.co.jp/event/example.html")
        record = items[0].to_record()

        self.assertEqual(record["regular_price_yen"], 19800)
        self.assertEqual(record["coupon_price_yen"], 14800)
        self.assertEqual(record["product_name"], "Sample Product")
        self.assertEqual(record["product_url"], "https://www.dospara.co.jp/SBR1/IC111111.html")


if __name__ == "__main__":
    unittest.main()
