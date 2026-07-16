import unittest

from dospara_coupon_tool import (
    DEFAULT_PAGE_URL,
    discover_coupon_page,
    enrich_items,
    get_dospara_coupon_prices,
    parse_coupon_items,
)


class DosparaCouponToolTest(unittest.TestCase):
    CAMPAIGN_LIST_URL = "https://www.dospara.co.jp/campaign-list"
    CURRENT_COUPON_URL = "https://www.dospara.co.jp/event/current_parts_coupon.html"
    SPECIAL_COUPON_URL = "https://www.dospara.co.jp/event/summer_self_build_pc.html"

    def fake_discovery_fetcher(self, url, **_kwargs):
        pages = {
            self.CAMPAIGN_LIST_URL: f"""
            <a href="/goods/parts">PCパーツ</a>
            <a href="/event/gaming_pc_sale.html">ゲーミングPC セール</a>
            <a href="{self.CURRENT_COUPON_URL}">PCパーツ・周辺機器 週替わりクーポン</a>
            <a href="{self.CURRENT_COUPON_URL}?side">対象PCパーツ・周辺機器数量限定SALE</a>
            <a href="{self.SPECIAL_COUPON_URL}">ドスパラ大決算セール 夏の自作PC強化祭り クーポン</a>
            """,
            DEFAULT_PAGE_URL: """
            <html>
              <title>Old fixed page</title>
              <h2 class="section-title"><span>Old coupons</span></h2>
              <li class="model-card get_product_data" data-code="IC999999">
                <div class="coupon-wrapper coupon-999">
                  <div class="coupon-code__text">OLDCODE</div>
                </div>
              </li>
            </html>
            """,
            self.CURRENT_COUPON_URL: """
            <html>
              <title>Current parts coupons</title>
              <h2 class="section-title"><span>Weekly coupons</span></h2>
              <li class="model-card get_product_data" data-code="IC333333">
                <div class="coupon-wrapper coupon-3000">
                  <div class="coupon-code__text">NEWCODE</div>
                </div>
              </li>
            </html>
            """,
            self.SPECIAL_COUPON_URL: """
            <html>
              <title>ドスパラ大決算セール 夏の自作PC強化祭り</title>
              <div class="hero-image__date-bottom">8月1日（土）10:59まで</div>
              <h2 class="section-title"><span>自作PC強化祭り</span></h2>
              <li class="model-card get_product_data" data-code="IC444444">
                <div class="coupon-wrapper coupon-4000">
                  <div class="coupon-code__text">SUMMERPC</div>
                </div>
              </li>
            </html>
            """,
            "https://www.dospara.co.jp/goods/parts": "<html><title>Parts category</title></html>",
            "https://www.dospara.co.jp/event/gaming_pc_sale.html": "<html><title>PC sale</title></html>",
        }
        if url not in pages:
            raise OSError(f"Unexpected URL: {url}")
        return pages[url]

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

    def test_discover_coupon_page_selects_current_campaign_from_campaign_list(self):
        discovery = discover_coupon_page(
            start_urls=[self.CAMPAIGN_LIST_URL],
            fetcher=self.fake_discovery_fetcher,
        )

        self.assertEqual(discovery.selected_url, self.CURRENT_COUPON_URL)
        self.assertEqual(discovery.selected_urls, [self.CURRENT_COUPON_URL, self.SPECIAL_COUPON_URL])
        self.assertFalse(discovery.fallback_used)
        self.assertEqual(discovery.selected_candidate.item_count, 1)

    def test_get_dospara_coupon_prices_collects_multiple_discovered_coupon_pages(self):
        result = get_dospara_coupon_prices(
            fetch_prices=False,
            discovery_start_urls=[self.CAMPAIGN_LIST_URL],
            fetcher=self.fake_discovery_fetcher,
        )

        self.assertEqual(result["source_url"], self.CURRENT_COUPON_URL)
        self.assertEqual(result["source_urls"], [self.CURRENT_COUPON_URL, self.SPECIAL_COUPON_URL])
        self.assertTrue(result["discovery"]["enabled"])
        self.assertEqual(result["discovery"]["coupon_page_count"], 2)
        self.assertEqual(result["count"], 2)
        self.assertEqual({item["coupon_code"] for item in result["items"]}, {"NEWCODE", "SUMMERPC"})
        self.assertEqual(result["items"][1]["campaign_source_url"], self.SPECIAL_COUPON_URL)
        self.assertEqual(result["items"][1]["campaign_end_text"], "8月1日（土）10:59まで")


if __name__ == "__main__":
    unittest.main()
