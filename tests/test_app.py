"""Reproducible unit and loopback API tests for ReLoop Market.

All integration tests use a temporary SQLite database and an ephemeral loopback
HTTP server. They do not contact external payment, email, or production services.
Run from the project root with: python -m unittest discover -s tests -v
"""
from __future__ import annotations

import http.cookiejar
import json
import os
import tempfile
import threading
import time
import unittest
from datetime import date, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener
from unittest.mock import patch

from backend import app


class HelperTests(unittest.TestCase):
    def test_slugify_removes_accents_and_normalizes_separators(self):
        self.assertEqual(app.slugify("Đèn đọc sách — Gỗ phục hồi!"), "den-doc-sach-go-phuc-hoi")

    def test_slugify_empty_value_has_fallback(self):
        self.assertEqual(app.slugify("你好"), "san-pham")

    def test_safe_product_text_trims_plain_text(self):
        self.assertEqual(app.safe_product_text("  Bàn gỗ cũ  ", 100, "Tên"), "Bàn gỗ cũ")

    def test_safe_product_text_rejects_markup_and_javascript(self):
        for value in ("<script>alert(1)</script>", "javascript:alert(1)", "x" * 11):
            with self.subTest(value=value[:20]), self.assertRaises(app.APIError):
                app.safe_product_text(value, 10, "Tên")

    def test_vnpay_signature_ignores_signature_fields(self):
        params = {"vnp_TxnRef": "RL1234", "vnp_Amount": "100000", "vnp_SecureHashType": "SHA512"}
        signature = app.vnpay_signature(params, "test-secret")
        params["vnp_SecureHash"] = "ignored"
        self.assertEqual(signature, app.vnpay_signature(params, "test-secret"))

    def test_vnpay_url_fails_closed_without_sandbox_credentials(self):
        with patch.dict(os.environ, {}, clear=False):
            for key in ("RELOOP_VNPAY_TMN_CODE", "RELOOP_VNPAY_HASH_SECRET", "RELOOP_VNPAY_RETURN_URL", "RELOOP_VNPAY_IPN_URL"):
                os.environ.pop(key, None)
            with self.assertRaises(app.APIError) as caught:
                app.build_vnpay_url("RL1234", 100000, "127.0.0.1")
        self.assertEqual(caught.exception.status, 503)

    def test_password_hash_verifies_and_rejects_wrong_password(self):
        encoded = app.password_hash("correct horse battery")
        self.assertTrue(app.password_matches("correct horse battery", encoded))
        self.assertFalse(app.password_matches("incorrect", encoded))


class ApiIntegrationTests(unittest.TestCase):
    def setUp(self):
        local_temp_root = Path(__file__).resolve().parent.parent / ".test-tmp"
        local_temp_root.mkdir(exist_ok=True)
        self.tempdir = tempfile.TemporaryDirectory(prefix="reloop-test-", dir=local_temp_root)
        self.previous_db_path = app.DB_PATH
        app.DB_PATH = Path(self.tempdir.name) / "test.sqlite3"
        app.init_db()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"
        self.cookie_jar = http.cookiejar.CookieJar()
        self.client = build_opener(HTTPCookieProcessor(self.cookie_jar))

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        app.DB_PATH = self.previous_db_path
        self.tempdir.cleanup()

    def request_json(self, method, path, payload=None, headers=None):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request_headers = {"Accept": "application/json"}
        if body is not None:
            request_headers["Content-Type"] = "application/json"
            request_headers["Origin"] = self.base_url
        request_headers.update(headers or {})
        request = Request(self.base_url + path, data=body, headers=request_headers, method=method)
        try:
            response = self.client.open(request, timeout=5)
        except HTTPError as error:
            response = error
        return response.code, json.loads(response.read().decode("utf-8"))

    def register(self, email="buyer@example.test"):
        return self.request_json("POST", "/api/register", {
            "name": "Test Buyer", "email": email, "password": "CorrectHorseBattery12!"
        })

    def prepare_recommendation_catalog(self):
        with app.connect() as db:
            db.execute("UPDATE products SET lifecycle_status='archived'")

    def add_recommendation_product(self, product_id, category="Danh mục A", condition="Tốt", price=100000,
                                   stock=10, status="approved", lifecycle_status="active", rentable=0,
                                   created_at=100):
        with app.connect() as db:
            db.execute(
                "INSERT INTO products(id,name,category,condition,seller,price,emoji,bg,badge,stock,status,lifecycle_status,rentable,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (product_id,product_id,category,condition,"Người bán",price,"♻","#eee","Đồ cũ",
                 stock,status,lifecycle_status,rentable,created_at))

    def add_voucher(self, code, *, discount_type="fixed", value=10000, min_order=0,
                    max_discount=None, starts_at=None, ends_at=None, usage_limit=None,
                    per_user_limit=1, is_active=1):
        now = int(time.time())
        with app.connect() as db:
            db.execute(
                "INSERT INTO vouchers(code,discount_type,value,min_order,max_discount,starts_at,ends_at,"
                "usage_limit,per_user_limit,is_active,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (code,discount_type,value,min_order,max_discount,starts_at or now-60,
                 ends_at or now+3600,usage_limit,per_user_limit,is_active,now))

    def make_admin_and_login(self):
        password = "AdminTestPassword123!"
        with app.connect() as db:
            db.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)",
                       ("Test Admin","admin@example.test",app.password_hash(password),"admin",int(time.time())))
        self.cookie_jar.clear()
        return self.request_json("POST", "/api/login", {
            "email":"admin@example.test","password":password
        })

    def test_products_endpoint_returns_seeded_catalog(self):
        status, products = self.request_json("GET", "/api/products")
        self.assertEqual(status, 200)
        self.assertTrue(any(product["id"] == "p1" for product in products))

    def test_product_recommendations_exclude_source_unavailable_items_and_include_reason_and_image(self):
        self.prepare_recommendation_catalog()
        self.add_recommendation_product("rec-source")
        self.add_recommendation_product("rec-match",category="Danh mục A")
        self.add_recommendation_product("rec-no-image",category="Danh mục B")
        self.add_recommendation_product("rec-no-stock",stock=0)
        self.add_recommendation_product("rec-inactive",lifecycle_status="archived")
        with app.connect() as db:
            db.execute("INSERT INTO product_images(product_id,image_path,sort_order,created_at) VALUES(?,?,?,?)",
                       ("rec-match","/assets/recommendation.jpg",0,100))

        status, result = self.request_json("GET", "/api/recommendations/rec-source")
        self.assertEqual(status, 200)
        self.assertEqual(result["method"], "rule-based")
        self.assertNotIn("rec-source", [item["id"] for item in result["items"]])
        self.assertNotIn("rec-no-stock", [item["id"] for item in result["items"]])
        self.assertNotIn("rec-inactive", [item["id"] for item in result["items"]])
        match = next(item for item in result["items"] if item["id"] == "rec-match")
        self.assertEqual(match["reason"], "Cùng danh mục")
        self.assertEqual(match["image"], "/assets/recommendation.jpg")
        no_image=next(item for item in result["items"] if item["id"]=="rec-no-image")
        self.assertIsNone(no_image["image"])

    def test_recommendation_context_validation_limit_and_unknown_product(self):
        self.prepare_recommendation_catalog()
        for index in range(14):
            self.add_recommendation_product(f"rec-limit-{index}")

        status, result = self.request_json("GET", "/api/recommendations?context=home&limit=99")
        self.assertEqual(status, 200)
        self.assertEqual(len(result["items"]), 12)
        self.assertEqual(result["method"], "rule-based")
        status, _ = self.request_json("GET", "/api/recommendations?context=unknown")
        self.assertEqual(status, 400)
        status, _ = self.request_json("GET", "/api/recommendations/not-a-real-product")
        self.assertEqual(status, 404)

    def test_recommendation_script_is_served_and_product_page_loads_external_script(self):
        response = self.client.open(self.base_url + "/recommendations.js", timeout=5)
        self.assertEqual(response.code, 200)
        self.assertIn("api(path)", response.read().decode("utf-8"))
        product = self.request_json("GET", "/api/products")[1][0]
        response = self.client.open(self.base_url + "/p/" + product["slug"], timeout=5)
        self.assertEqual(response.code, 200)
        page = response.read().decode("utf-8")
        self.assertIn('id="productRecommendations"', page)
        self.assertIn('<script src="/recommendations.js"></script>', page)

    def test_guest_and_signed_in_recommendations_and_favorite_category_priority(self):
        self.prepare_recommendation_catalog()
        self.add_recommendation_product("rec-favorite-sample",category="Danh mục yêu thích",status="pending")
        self.add_recommendation_product("rec-favorite-target",category="Danh mục yêu thích")
        self.add_recommendation_product("rec-other-target",category="Danh mục khác")

        guest_status, guest = self.request_json("GET", "/api/recommendations?context=home")
        self.assertEqual(guest_status, 200)
        self.assertEqual(guest["method"], "rule-based")
        self.assertTrue(guest["items"])

        register_status, registration = self.register("recommendation-buyer@example.test")
        self.assertEqual(register_status, 200)
        user_id = registration["user"]["id"]
        with app.connect() as db:
            db.execute("INSERT INTO favorites(user_id,product_id,created_at) VALUES(?,?,?)",
                       (user_id,"rec-favorite-sample",100))
        user_status, personalized = self.request_json("GET", "/api/recommendations?context=home")
        self.assertEqual(user_status, 200)
        self.assertEqual(personalized["method"], "hybrid-rule-based")
        self.assertEqual(personalized["items"][0]["id"], "rec-favorite-target")
        self.assertEqual(personalized["items"][0]["reason"], "Dựa trên mục yêu thích của bạn")

    def test_cart_recommendations_exclude_cart_products_and_ignore_demo_co_purchases(self):
        self.prepare_recommendation_catalog()
        self.add_recommendation_product("rec-cart-source",category="Nguồn",condition="Tốt")
        self.add_recommendation_product("rec-cart-product",category="Nguồn")
        self.add_recommendation_product("rec-real-together",category="Đã mua cùng")
        self.add_recommendation_product("rec-demo-together",category="Chỉ đơn demo")
        register_status, registration = self.register("cart-recommendation-buyer@example.test")
        self.assertEqual(register_status, 200)
        user_id = registration["user"]["id"]
        with app.connect() as db:
            for order_id, candidate_id, is_demo in (
                ("REC-REAL-ORDER","rec-real-together",0),
                ("REC-DEMO-ORDER","rec-demo-together",1),
            ):
                db.execute(
                    "INSERT INTO orders(id,user_id,total,payment,status,address,created_at,is_demo) VALUES(?,?,?,?,?,?,?,?)",
                    (order_id,user_id,200000,"COD","Đang xử lý","Test address",100,is_demo))
                db.executemany(
                    "INSERT INTO order_items(order_id,product_id,name,price,quantity) VALUES(?,?,?,?,?)",
                    ((order_id,"rec-cart-source","Nguồn",100000,1),
                     (order_id,candidate_id,candidate_id,100000,1)))

        status, result = self.request_json(
            "GET", "/api/recommendations?context=cart&cart=rec-cart-source,rec-cart-product,missing-id&limit=12")
        self.assertEqual(status, 200)
        ids = [item["id"] for item in result["items"]]
        self.assertNotIn("rec-cart-source", ids)
        self.assertNotIn("rec-cart-product", ids)
        self.assertEqual(next(item for item in result["items"] if item["id"] == "rec-real-together")["reason"],
                         "Thường được mua cùng")
        self.assertNotEqual(next(item for item in result["items"] if item["id"] == "rec-demo-together")["reason"],
                            "Thường được mua cùng")

    def test_catalog_search_and_pagination_return_expected_shape(self):
        status, data = self.request_json("GET", "/api/products?q=Canon&page=1&per_page=1")
        self.assertEqual(status, 200)
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["per_page"], 1)
        self.assertEqual(len(data["items"]), 1)
        self.assertIn("Canon", data["items"][0]["name"])

    def test_register_creates_customer_and_duplicate_is_rejected(self):
        status, result = self.register()
        self.assertEqual(status, 200)
        self.assertEqual(result["user"]["role"], "customer")
        duplicate_status, _ = self.register()
        self.assertEqual(duplicate_status, 409)

    def test_registration_rejects_weak_password(self):
        status, _ = self.request_json("POST", "/api/register", {
            "name": "Test Buyer", "email": "weak@example.test", "password": "short"
        })
        self.assertEqual(status, 400)

    def test_login_and_session_round_trip(self):
        self.assertEqual(self.register()[0], 200)
        self.cookie_jar.clear()
        status, _ = self.request_json("POST", "/api/login", {
            "email": "buyer@example.test", "password": "CorrectHorseBattery12!"
        })
        self.assertEqual(status, 200)
        self.assertTrue(any(cookie.name == app.COOKIE for cookie in self.cookie_jar))
        status, orders = self.request_json("GET", "/api/orders")
        self.assertEqual((status, orders), (200, []))

    def test_wrong_password_returns_generic_unauthorized(self):
        self.assertEqual(self.register()[0], 200)
        status, body = self.request_json("POST", "/api/login", {
            "email": "buyer@example.test", "password": "WrongPassword123!"
        })
        self.assertEqual(status, 401)
        self.assertIn("không đúng", body["error"].lower())

    def test_orders_require_login(self):
        status, body = self.request_json("GET", "/api/orders")
        self.assertEqual(status, 401)
        self.assertIn("đăng nhập", body["error"].lower())

    def test_customer_cannot_access_admin_users(self):
        self.assertEqual(self.register()[0], 200)
        status, _ = self.request_json("GET", "/api/admin/users")
        self.assertEqual(status, 403)

    def test_checkout_requires_login_and_valid_terms(self):
        product_id = self.request_json("GET", "/api/products")[1][0]["id"]
        payload = {"items": [{"id": product_id, "qty": 1}], "payment": "COD", "address": "12 Test Street",
                   "terms_accepted": True, "terms_version": app.POLICY_VERSION, "idempotency_key": "test-order-00000001"}
        status, _ = self.request_json("POST", "/api/orders", payload)
        self.assertEqual(status, 401)

    def test_cod_checkout_computes_total_and_idempotent_replay(self):
        self.assertEqual(self.register()[0], 200)
        product = self.request_json("GET", "/api/products")[1][0]
        payload = {"items": [{"id": product["id"], "qty": 1}], "payment": "COD", "address": "12 Test Street",
                   "terms_accepted": True, "terms_version": app.POLICY_VERSION, "idempotency_key": "test-order-00000002"}
        status, order = self.request_json("POST", "/api/orders", payload)
        self.assertEqual(status, 201)
        self.assertEqual(order["subtotal"], product["price"])
        self.assertEqual(order["total"], product["price"] + 30000)
        replay_status, replay = self.request_json("POST", "/api/orders", payload)
        self.assertEqual(replay_status, 200)
        self.assertEqual(replay["id"], order["id"])
        self.assertTrue(replay["idempotent_replay"])

    def test_checkout_rejects_reusing_idempotency_key_for_changed_payload(self):
        self.assertEqual(self.register()[0], 200)
        product = self.request_json("GET", "/api/products")[1][0]
        payload = {"items": [{"id": product["id"], "qty": 1}], "payment": "COD", "address": "12 Test Street",
                   "terms_accepted": True, "terms_version": app.POLICY_VERSION, "idempotency_key": "test-order-00000003"}
        self.assertEqual(self.request_json("POST", "/api/orders", payload)[0], 201)
        payload["items"][0]["qty"] = 2
        status, _ = self.request_json("POST", "/api/orders", payload)
        self.assertEqual(status, 409)

    def test_voucher_percentage_cap_minimum_and_expiry_validation(self):
        self.assertEqual(self.register()[0], 200)
        product = self.request_json("GET", "/api/products")[1][0]
        with app.connect() as db:
            db.execute("UPDATE products SET price=200000,weight_grams=500,stock=3 WHERE id=?",(product["id"],))
        self.add_voucher("CAP50",discount_type="percent",value=50,min_order=150000,max_discount=15000)
        status, result = self.request_json("POST", "/api/vouchers/validate", {
            "code":" cap50 ","items":[{"id":product["id"],"qty":1}]
        })
        self.assertEqual(status,200)
        self.assertEqual(result["discount"],15000)
        self.assertEqual(result["total"],215000)

        with app.connect() as db:
            db.execute("UPDATE vouchers SET min_order=250000 WHERE code='CAP50'")
        self.assertEqual(self.request_json("POST", "/api/vouchers/validate", {
            "code":"CAP50","items":[{"id":product["id"],"qty":1}]
        })[0],400)
        with app.connect() as db:
            db.execute("UPDATE vouchers SET min_order=0,ends_at=? WHERE code='CAP50'",(int(time.time())-1,))
        self.assertEqual(self.request_json("POST", "/api/vouchers/validate", {
            "code":"CAP50","items":[{"id":product["id"],"qty":1}]
        })[0],400)

    def test_checkout_voucher_redemption_limit_is_enforced(self):
        self.assertEqual(self.register()[0],200)
        product=self.request_json("GET","/api/products")[1][0]
        self.add_voucher("ONCE",value=10000,usage_limit=1,per_user_limit=1)
        payload={"items":[{"id":product["id"],"qty":1}],"payment":"COD","address":"12 Test Street",
                 "terms_accepted":True,"terms_version":app.POLICY_VERSION,"voucher_code":"ONCE",
                 "idempotency_key":"voucher-test-order-01"}
        status,order=self.request_json("POST","/api/orders",payload)
        self.assertEqual(status,201)
        self.assertEqual(order["discount"],10000)
        self.assertEqual(order["voucher_code"],"ONCE")
        self.assertEqual(self.request_json("POST","/api/vouchers/validate",{
            "code":"ONCE","items":[{"id":product["id"],"qty":1}]
        })[0],409)

    def test_checkout_rejects_aggregated_quantity_above_stock_without_mutation(self):
        self.assertEqual(self.register()[0],200)
        product=self.request_json("GET","/api/products")[1][0]
        with app.connect() as db: db.execute("UPDATE products SET stock=1 WHERE id=?",(product["id"],))
        payload={"items":[{"id":product["id"],"qty":1},{"id":product["id"],"qty":1}],
                 "payment":"COD","address":"12 Test Street","terms_accepted":True,
                 "terms_version":app.POLICY_VERSION,"idempotency_key":"stock-test-order-01"}
        self.assertEqual(self.request_json("POST","/api/orders",payload)[0],400)
        with app.connect() as db:
            self.assertEqual(db.execute("SELECT stock FROM products WHERE id=?",(product["id"],)).fetchone()[0],1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM orders").fetchone()[0],0)

    def test_rental_overlap_is_rejected_but_non_overlapping_date_is_allowed(self):
        self.assertEqual(self.register()[0],200)
        product=self.request_json("GET","/api/products")[1][0]
        with app.connect() as db:
            db.execute("UPDATE products SET rentable=1,rental_stock=1,rental_price_day=10000 WHERE id=?",(product["id"],))
        start=(date.today()+timedelta(days=7)).isoformat()
        payload={"id":product["id"],"days":2,"address":"12 Test Street","start":start,
                 "terms_accepted":True,"terms_version":app.POLICY_VERSION}
        status,first=self.request_json("POST","/api/rentals",payload)
        self.assertEqual(status,201)
        self.assertEqual(first["total"],20000)
        self.assertEqual(self.request_json("POST","/api/rentals",payload)[0],409)
        payload["start"]=(date.today()+timedelta(days=12)).isoformat()
        self.assertEqual(self.request_json("POST","/api/rentals",payload)[0],201)

    def test_admin_order_transition_rejects_invalid_state_change(self):
        self.assertEqual(self.register()[0],200)
        product=self.request_json("GET","/api/products")[1][0]
        payload={"items":[{"id":product["id"],"qty":1}],"payment":"COD","address":"12 Test Street",
                 "terms_accepted":True,"terms_version":app.POLICY_VERSION,"idempotency_key":"state-test-order-01"}
        status,order=self.request_json("POST","/api/orders",payload)
        self.assertEqual(status,201)
        self.assertEqual(self.make_admin_and_login()[0],200)
        path=f"/api/admin/orders/{order['id']}"
        self.assertEqual(self.request_json("PATCH",path,{"status":"Đang giao"})[0],200)
        self.assertEqual(self.request_json("PATCH",path,{"status":"Đang xử lý"})[0],409)
        with app.connect() as db:
            self.assertEqual(db.execute("SELECT status FROM orders WHERE id=?",(order["id"],)).fetchone()[0],"Đang giao")

    def test_vnpay_checkout_fails_closed_without_credentials(self):
        self.assertEqual(self.register()[0], 200)
        product = self.request_json("GET", "/api/products")[1][0]
        payload = {"items": [{"id": product["id"], "qty": 1}], "payment": "VNPAY", "address": "12 Test Street",
                   "terms_accepted": True, "terms_version": app.POLICY_VERSION, "idempotency_key": "test-order-00000004"}
        with patch.dict(os.environ, {}, clear=False):
            for key in ("RELOOP_VNPAY_TMN_CODE", "RELOOP_VNPAY_HASH_SECRET", "RELOOP_VNPAY_RETURN_URL", "RELOOP_VNPAY_IPN_URL"):
                os.environ.pop(key, None)
            status, _ = self.request_json("POST", "/api/orders", payload)
        self.assertEqual(status, 503)


if __name__ == "__main__":
    unittest.main()
