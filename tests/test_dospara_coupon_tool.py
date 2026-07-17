import datetime as dt
import unittest

from dospara_coupon_tool import (
    DEFAULT_PAGE_URL,
    discover_coupon_page,
    enrich_items,
    extract_product_page_coupon,
    get_dospara_coupon_prices,
    parse_coupon_items,
    verify_product_page_coupons,
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

    def fake_product_page_fetcher(self, url, **_kwargs):
        pages = {
            "https://www.dospara.co.jp/SBR1/IC111111.html": """
            <script>
              var productJson = {"productID":"IC111111","pname":"Active Product","amttax":19800,"stkname":"24時間以内に出荷"};
            </script>
            <script>
              switch (productJson.productID) {
                case 'IC111111':
                  productMap.amount = '5000';
                  productMap.couponcode = 'LIVEA';
                  productMap.campaign = 'campaign-weekly';
                  break;
              }
              const campaignDeadlines = {
                "campaign-weekly": "2026年7月17日(金) 16:59",
              };
            </script>
            """,
            "https://www.dospara.co.jp/SBR1/IC222222.html": """
            <script>
              var productJson = {"productID":"IC222222","pname":"Ended Product","amttax":9800,"stkname":"24時間以内に出荷"};
            </script>
            <script>
              switch (productJson.productID) {
                // case 'IC222222':
                //   productMap.amount = '1000';
                //   productMap.couponcode = 'LIVEB';
                //   productMap.campaign = 'campaign-weekly';
                //   break;
              }
            </script>
            """,
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

    def test_extract_product_page_coupon_ignores_commented_out_case(self):
        active_html = self.fake_product_page_fetcher("https://www.dospara.co.jp/SBR1/IC111111.html")
        ended_html = self.fake_product_page_fetcher("https://www.dospara.co.jp/SBR1/IC222222.html")

        active_coupon = extract_product_page_coupon(active_html, "IC111111")
        ended_coupon = extract_product_page_coupon(ended_html, "IC222222")

        self.assertIsNotNone(active_coupon)
        self.assertEqual(active_coupon.amount_yen, 5000)
        self.assertEqual(active_coupon.coupon_code, "LIVEA")
        self.assertEqual(active_coupon.expire_text, "2026年7月17日(金) 16:59")
        self.assertIsNone(ended_coupon)

    def test_verify_product_page_coupons_drops_campaign_cards_missing_from_product_page(self):
        items = parse_coupon_items(
            """
            <h2 class="section-title"><span>Weekly coupons</span></h2>
            <li class="model-card get_product_data" data-code="IC111111">
              <div class="coupon-wrapper coupon-5000">
                <div class="coupon-code__text">LIVEA</div>
              </div>
            </li>
            <li class="model-card get_product_data" data-code="IC222222">
              <div class="coupon-wrapper coupon-1000">
                <div class="coupon-code__text">LIVEB</div>
              </div>
            </li>
            """
        )
        product_info = {
            "IC111111": {
                "productID": "IC111111",
                "pname": "Active Product",
                "amttax": 19800,
                "url": "/SBR1/IC111111.html",
            },
            "IC222222": {
                "productID": "IC222222",
                "pname": "Ended Product",
                "amttax": 9800,
                "url": "/SBR1/IC222222.html",
            },
        }

        enrich_items(items, product_info, page_url="https://www.dospara.co.jp/event/example.html")
        verified_items = verify_product_page_coupons(
            items,
            fetcher=self.fake_product_page_fetcher,
            now=dt.datetime(2026, 7, 17, 6, 0, tzinfo=dt.timezone.utc),
        )

        self.assertEqual([item.product_id for item in verified_items], ["IC111111"])
        self.assertTrue(verified_items[0].coupon_verified)
        self.assertEqual(verified_items[0].product_page_coupon_expire_text, "2026年7月17日(金) 16:59")
        self.assertEqual(verified_items[0].product_page_regular_price_yen, 19800)
        self.assertEqual(verified_items[0].product_page_stock, "24時間以内に出荷")
        self.assertEqual(verified_items[0].coupon_expires_at, "2026-07-17T16:59:00+09:00")
        self.assertFalse(items[1].coupon_verified)
        self.assertEqual(items[1].coupon_verification_error, "coupon not active on product page")

    def test_product_page_snapshot_overrides_stale_api_price(self):
        items = parse_coupon_items(
            """
            <li class="model-card get_product_data" data-code="IC333333">
              <div class="coupon-wrapper coupon-2000">
                <div class="coupon-code__text">CURRENT</div>
              </div>
            </li>
            """
        )
        enrich_items(
            items,
            {
                "IC333333": {
                    "productID": "IC333333",
                    "pname": "API Product Name",
                    "amttax": 12980,
                    "stkname": "残りわずか",
                    "url": "/SBR1/IC333333.html",
                }
            },
            page_url="https://www.dospara.co.jp/event/example.html",
        )

        def fetch_product_page(_url, **_kwargs):
            return """
            <script>
              var productJson = {"productID":"IC333333","pname":"Current Product Name","amttax":10980,"stkname":"24時間以内に出荷"};
            </script>
            <script>
              const campaignExpire = {"campaign-weekly":"2026年7月24日(金)10:59"};
              switch (productJson.productID) {
                case 'IC333333':
                  productMap.amount = '2000';
                  productMap.couponcode = 'CURRENT';
                  productMap.campaign = 'campaign-weekly';
                  break;
              }
            </script>
            """

        verified_items = verify_product_page_coupons(
            items,
            fetcher=fetch_product_page,
            now=dt.datetime(2026, 7, 17, 8, 0, tzinfo=dt.timezone.utc),
        )

        self.assertEqual(len(verified_items), 1)
        record = verified_items[0].to_record()
        self.assertEqual(record["api_regular_price_yen"], 12980)
        self.assertEqual(record["product_page_regular_price_yen"], 10980)
        self.assertFalse(record["product_page_price_matches_api"])
        self.assertEqual(record["regular_price_yen"], 10980)
        self.assertEqual(record["coupon_price_yen"], 8980)
        self.assertEqual(record["stock"], "24時間以内に出荷")

    def test_expired_product_page_coupon_is_rejected(self):
        items = parse_coupon_items(
            """
            <li class="model-card get_product_data" data-code="IC111111">
              <div class="coupon-wrapper coupon-5000">
                <div class="coupon-code__text">LIVEA</div>
              </div>
            </li>
            """
        )
        enrich_items(
            items,
            {
                "IC111111": {
                    "productID": "IC111111",
                    "pname": "Active Product",
                    "amttax": 19800,
                    "stkname": "24時間以内に出荷",
                    "url": "/SBR1/IC111111.html",
                }
            },
            page_url="https://www.dospara.co.jp/event/example.html",
        )

        verified_items = verify_product_page_coupons(
            items,
            fetcher=self.fake_product_page_fetcher,
            now=dt.datetime(2026, 7, 17, 8, 0, tzinfo=dt.timezone.utc),
        )

        self.assertEqual(verified_items, [])
        self.assertFalse(items[0].coupon_verified)
        self.assertEqual(
            items[0].coupon_verification_error,
            "coupon expired on product page: 2026年7月17日(金) 16:59",
        )

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
