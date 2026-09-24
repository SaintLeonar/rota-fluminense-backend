import os
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:5173")

from app import app  # noqa: E402
from schemas.error import ErrorSchema  # noqa: E402

PUBLIC_VALIDATION_MATRIX = {
    ("GET", "/locais"): {"consulta"},
    ("POST", "/locais"): {"corpo"},
    ("GET", "/locais/{slug}"): {"caminho"},
    ("GET", "/locais/{slug}/clima"): {"caminho"},
    ("PUT", "/locais/{slug}"): {"caminho", "corpo"},
    ("DELETE", "/locais/{slug}"): {"caminho"},
    ("GET", "/locais/{slug}/avaliacoes"): {"caminho"},
    ("POST", "/locais/{slug}/avaliacoes"): {"caminho", "corpo"},
    ("PATCH", "/avaliacoes/{avaliacao_id}"): {"caminho", "corpo"},
    ("DELETE", "/avaliacoes/{avaliacao_id}"): {"caminho"},
}

BODY_OPERATIONS = (
    ("POST", "/locais"),
    ("PUT", "/locais/arpoador"),
    ("POST", "/locais/arpoador/avaliacoes"),
    ("PATCH", "/avaliacoes/1"),
)


class PublicValidationMatrixTestCase(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def assert_invalid_request(self, response):
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content_type, "application/json")
        payload = response.get_json()
        ErrorSchema.model_validate(payload)
        self.assertEqual(set(payload), {"erro"})
        self.assertEqual(payload["erro"]["codigo"], "requisicao_invalida")
        self.assertEqual(
            payload["erro"]["requisicao_id"],
            response.headers["X-Request-ID"],
        )

    def test_matrix_matches_the_ten_canonical_openapi_operations(self):
        specification = self.client.get("/openapi/openapi.json").get_json()
        methods = {"get", "post", "put", "patch", "delete"}
        operations = {
            (method.upper(), path)
            for path, path_item in specification["paths"].items()
            if path != "/"
            for method in path_item
            if method in methods
        }

        self.assertEqual(set(PUBLIC_VALIDATION_MATRIX), operations)
        self.assertEqual(
            {
                dimension
                for values in PUBLIC_VALIDATION_MATRIX.values()
                for dimension in values
            },
            {"caminho", "consulta", "corpo"},
        )

    def test_unknown_query_parameter_is_rejected_by_listing(self):
        response = self.client.get("/locais?parametro_legado=valor")

        self.assert_invalid_request(response)
        self.assertEqual(
            response.get_json()["erro"]["detalhes"][0],
            {
                "campo": "parametro_legado",
                "codigo": "campo_nao_permitido",
                "mensagem": "O campo não é permitido.",
            },
        )

    def test_body_operations_reject_absent_malformed_and_non_object_json(self):
        invalid_payloads = (
            (b"", "application/json"),
            (b"{", "application/json"),
            (b"[]", "application/json"),
        )

        for method, path in BODY_OPERATIONS:
            for data, content_type in invalid_payloads:
                with self.subTest(method=method, path=path, data=data):
                    response = self.client.open(
                        path,
                        method=method,
                        data=data,
                        content_type=content_type,
                    )

                    self.assert_invalid_request(response)
                    response_text = response.get_data(as_text=True).lower()
                    for internal_term in (
                        "traceback",
                        "sqlalchemy",
                        "pymysql",
                        "database_url",
                    ):
                        self.assertNotIn(internal_term, response_text)


if __name__ == "__main__":
    unittest.main()
