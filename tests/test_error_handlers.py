import os
import re
import unittest
from unittest.mock import patch

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, OperationalError

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from app import app  # noqa: E402
from schemas.error import ErrorSchema  # noqa: E402
from schemas.local_schema import LocalQuerySchema  # noqa: E402
from utils.error_handlers import construir_envelope_erro  # noqa: E402
from utils.error_handlers import normalizar_erros_validacao  # noqa: E402
from utils.exceptions import AppError  # noqa: E402


class DuplicateKeyError(Exception):
    errno = 1062


class ErrorHandlerTestCase(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def assert_canonical_error(self, response, status, code):
        self.assertEqual(response.status_code, status)
        self.assertEqual(response.content_type, "application/json")

        payload = response.get_json()
        ErrorSchema.model_validate(payload)
        self.assertEqual(set(payload), {"erro"})
        self.assertEqual(payload["erro"]["codigo"], code)
        self.assertEqual(
            payload["erro"]["requisicao_id"],
            response.headers["X-Request-ID"],
        )
        self.assertRegex(
            payload["erro"]["requisicao_id"],
            r"^req_[0-9a-f]{32}$",
        )
        return payload["erro"]

    def test_envelope_builder_returns_schema_validated_safe_structure(self):
        request_id = f"req_{'a' * 32}"
        details = [
            {
                "campo": "nota",
                "codigo": "fora_do_limite",
                "mensagem": "O valor está fora dos limites permitidos.",
            }
        ]

        payload = construir_envelope_erro(
            "requisicao_invalida",
            "A requisição contém valores inválidos.",
            details,
            request_id,
        )

        validated = ErrorSchema.model_validate(payload)
        self.assertEqual(validated.model_dump(), payload)
        self.assertEqual(payload["erro"]["requisicao_id"], request_id)
        self.assertEqual(payload["erro"]["detalhes"], details)
        self.assertNotIn("input", payload["erro"])
        self.assertNotIn("contexto", payload["erro"])

    def test_validation_error_returns_400_with_safe_field_details(self):
        response = self.client.get("/locais?pagina=0&campo_extra=valor")

        error = self.assert_canonical_error(
            response,
            400,
            "requisicao_invalida",
        )
        details = {detail["campo"]: detail for detail in error["detalhes"]}
        self.assertEqual(details["pagina"]["codigo"], "fora_do_limite")
        self.assertEqual(
            details["campo_extra"]["codigo"],
            "campo_nao_permitido",
        )
        self.assertNotIn("input", response.get_data(as_text=True))
        self.assertNotIn("ctx", response.get_data(as_text=True))

    def test_missing_body_fields_use_required_detail_code(self):
        response = self.client.post("/locais", json={})

        error = self.assert_canonical_error(
            response,
            400,
            "requisicao_invalida",
        )
        details = {detail["campo"]: detail for detail in error["detalhes"]}
        self.assertEqual(details["nome"]["codigo"], "obrigatorio")
        self.assertEqual(details["latitude"]["codigo"], "obrigatorio")

    def test_app_error_uses_explicit_public_contract(self):
        expected = AppError(
            "local_nao_encontrado",
            "Local turístico não encontrado.",
            404,
        )

        with patch(
            "routes.local_routes.local_service.listar_locais",
            side_effect=expected,
        ):
            response = self.client.get("/locais")

        error = self.assert_canonical_error(
            response,
            404,
            "local_nao_encontrado",
        )
        self.assertEqual(error["detalhes"], [])

    def test_duplicate_key_is_mapped_to_slug_conflict_without_driver_text(
        self,
    ):
        exception = IntegrityError(
            "SQL técnico que não pode vazar",
            {"slug": "segredo"},
            DuplicateKeyError("mensagem específica do driver"),
        )

        with patch(
            "routes.local_routes.local_service.listar_locais",
            side_effect=exception,
        ):
            response = self.client.get("/locais")

        error = self.assert_canonical_error(
            response,
            409,
            "slug_ja_existente",
        )
        self.assertEqual(error["detalhes"][0]["campo"], "slug")
        text = response.get_data(as_text=True)
        self.assertNotIn("SQL técnico", text)
        self.assertNotIn("segredo", text)
        self.assertNotIn("driver", text)

    def test_database_unavailability_returns_safe_503(self):
        exception = OperationalError(
            "consulta confidencial",
            {"senha": "não-vazar"},
            RuntimeError("servidor interno"),
        )

        with patch(
            "routes.local_routes.local_service.listar_locais",
            side_effect=exception,
        ):
            response = self.client.get("/locais")

        self.assert_canonical_error(
            response,
            503,
            "banco_indisponivel",
        )
        text = response.get_data(as_text=True)
        self.assertNotIn("consulta confidencial", text)
        self.assertNotIn("não-vazar", text)
        self.assertNotIn("servidor interno", text)

    def test_unexpected_failure_returns_safe_500_and_correlated_log(self):
        with (
            self.assertLogs(app.logger, level="ERROR") as logs,
            patch(
                "routes.local_routes.local_service.listar_locais",
                side_effect=RuntimeError("detalhe técnico sigiloso"),
            ),
        ):
            response = self.client.get("/locais")

        error = self.assert_canonical_error(response, 500, "erro_interno")
        self.assertNotIn(
            "detalhe técnico sigiloso",
            response.get_data(as_text=True),
        )
        self.assertTrue(
            any(error["requisicao_id"] in record for record in logs.output)
        )

    def test_http_errors_follow_envelope(self):
        response = self.client.get("/rota-que-nao-existe")
        self.assert_canonical_error(response, 404, "rota_nao_encontrada")

        response = self.client.post("/")
        self.assert_canonical_error(response, 405, "metodo_nao_permitido")

    def test_every_request_receives_a_new_correlation_identifier(self):
        first = self.client.get("/")
        second = self.client.get("/")

        first_id = first.headers["X-Request-ID"]
        second_id = second.headers["X-Request-ID"]
        self.assertRegex(first_id, re.compile(r"^req_[0-9a-f]{32}$"))
        self.assertNotEqual(first_id, second_id)

    def test_validation_normalization_does_not_copy_input_or_context(self):
        try:
            LocalQuerySchema(pagina=0)
        except ValidationError as exception:
            details = normalizar_erros_validacao(exception)
        else:
            self.fail("A consulta inválida deveria falhar.")

        self.assertEqual(
            details,
            [
                {
                    "campo": "pagina",
                    "codigo": "fora_do_limite",
                    "mensagem": ("O valor está fora dos limites permitidos."),
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
