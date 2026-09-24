import unittest

from flask import Flask, jsonify

from services.cors_config import CorsSettings, configure_cors

ALLOWED_ORIGIN = "http://localhost:5173"
SECOND_ALLOWED_ORIGIN = "https://frontend.example.com"
DENIED_ORIGIN = "https://denied.example.com"


def build_app(*origins):
    app = Flask(__name__)

    @app.route("/locais", methods=["GET", "POST"])
    def locais():
        response = jsonify({"status": "ok"})
        response.headers["X-Request-ID"] = "req_test"
        return response

    @app.get("/locais/<slug>")
    def detalhe(slug):
        return jsonify({"slug": slug})

    @app.get("/openapi")
    def openapi():
        return jsonify({"status": "ok"})

    configure_cors(app, CorsSettings(allowed_origins=tuple(origins)))
    return app


class CorsFunctionalTestCase(unittest.TestCase):
    def setUp(self):
        self.app = build_app(ALLOWED_ORIGIN, SECOND_ALLOWED_ORIGIN)
        self.client = self.app.test_client()

    def test_each_explicit_origin_is_allowed_without_credentials(self):
        for origin in (ALLOWED_ORIGIN, SECOND_ALLOWED_ORIGIN):
            with self.subTest(origin=origin):
                response = self.client.get("/locais", headers={"Origin": origin})

                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.headers["Access-Control-Allow-Origin"],
                    origin,
                )
                self.assertNotIn(
                    "Access-Control-Allow-Credentials",
                    response.headers,
                )
                self.assertIn(
                    "X-Request-ID",
                    response.headers["Access-Control-Expose-Headers"],
                )

    def test_denied_and_originless_requests_receive_no_cors_authorization(self):
        denied = self.client.get(
            "/locais",
            headers={"Origin": DENIED_ORIGIN},
        )
        originless = self.client.get("/locais")

        self.assertEqual(denied.status_code, 200)
        self.assertEqual(originless.status_code, 200)
        for response in (denied, originless):
            self.assertNotIn("Access-Control-Allow-Origin", response.headers)
            self.assertNotIn(
                "Access-Control-Allow-Credentials",
                response.headers,
            )

    def test_allowed_preflight_restricts_methods_and_headers(self):
        response = self.client.options(
            "/locais",
            headers={
                "Origin": ALLOWED_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["Access-Control-Allow-Origin"],
            ALLOWED_ORIGIN,
        )
        methods = set(response.headers["Access-Control-Allow-Methods"].split(", "))
        self.assertEqual(methods, {"GET", "OPTIONS", "POST"})
        self.assertEqual(
            response.headers["Access-Control-Allow-Headers"],
            "Content-Type",
        )
        self.assertNotIn("Access-Control-Allow-Credentials", response.headers)

    def test_denied_origin_method_and_header_do_not_receive_permission(self):
        denied_origin = self.client.options(
            "/locais",
            headers={
                "Origin": DENIED_ORIGIN,
                "Access-Control-Request-Method": "POST",
            },
        )
        denied_method = self.client.options(
            "/locais",
            headers={
                "Origin": ALLOWED_ORIGIN,
                "Access-Control-Request-Method": "PATCH",
            },
        )
        denied_header = self.client.options(
            "/locais",
            headers={
                "Origin": ALLOWED_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Authorization",
            },
        )

        self.assertNotIn("Access-Control-Allow-Origin", denied_origin.headers)
        self.assertNotIn("Access-Control-Allow-Methods", denied_method.headers)
        self.assertNotIn("Access-Control-Allow-Headers", denied_header.headers)

    def test_non_public_documentation_resource_receives_no_cors_headers(self):
        response = self.client.get(
            "/openapi",
            headers={"Origin": ALLOWED_ORIGIN},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)


if __name__ == "__main__":
    unittest.main()
