import os
import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import OperationalError

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:5173")

from app import app  # noqa: E402
from schemas import clima_schema, openapi_examples  # noqa: E402
from schemas.error import ErrorSchema  # noqa: E402
from utils import exceptions  # noqa: E402


class ClimaRouteTestCase(unittest.TestCase):
    def setUp(self):
        self.original_service = app.config["OPEN_METEO_SERVICE"]
        self.service = MagicMock()
        self.service.consultar_clima.return_value = (
            clima_schema.ClimaResponseSchema.model_validate(
                openapi_examples.CLIMATE_RESPONSE_EXAMPLE
            )
        )
        app.config["OPEN_METEO_SERVICE"] = self.service
        self.client = app.test_client()

    def tearDown(self):
        app.config["OPEN_METEO_SERVICE"] = self.original_service

    def assert_canonical_error(self, response, status, code, message):
        self.assertEqual(response.status_code, status)
        self.assertEqual(response.content_type, "application/json")

        payload = response.get_json()
        ErrorSchema.model_validate(payload)
        self.assertEqual(set(payload), {"erro"})
        self.assertEqual(payload["erro"]["codigo"], code)
        self.assertEqual(payload["erro"]["mensagem"], message)
        self.assertEqual(payload["erro"]["detalhes"], [])
        self.assertEqual(
            payload["erro"]["requisicao_id"],
            response.headers["X-Request-ID"],
        )
        self.assertRegex(
            payload["erro"]["requisicao_id"],
            r"^req_[0-9a-f]{32}$",
        )
        return payload["erro"]

    def test_success_uses_shared_service_and_returns_public_schema(self):
        response = self.client.get("/locais/arpoador/clima")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            openapi_examples.CLIMATE_RESPONSE_EXAMPLE,
        )
        self.service.consultar_clima.assert_called_once()
        args, kwargs = self.service.consultar_clima.call_args
        self.assertEqual(args, ("arpoador",))
        self.assertEqual(
            kwargs["requisicao_id"],
            response.headers["X-Request-ID"],
        )
        self.assertRegex(kwargs["requisicao_id"], r"^req_[0-9a-f]{32}$")

    def test_malformed_slug_returns_bad_request_without_calling_service(self):
        response = self.client.get("/locais/Arpoador/clima")

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["erro"]["codigo"], "requisicao_invalida")
        self.assertEqual(payload["erro"]["detalhes"][0]["campo"], "slug")
        self.assertEqual(
            payload["erro"]["requisicao_id"],
            response.headers["X-Request-ID"],
        )
        self.service.consultar_clima.assert_not_called()

    def test_unknown_local_returns_correlated_not_found(self):
        self.service.consultar_clima.side_effect = exceptions.AppError(
            "local_nao_encontrado",
            "Local turístico não encontrado.",
            404,
        )

        with self.assertLogs(app.logger, level="WARNING"):
            response = self.client.get("/locais/local-inexistente/clima")

        self.assert_canonical_error(
            response,
            404,
            "local_nao_encontrado",
            "Local turístico não encontrado.",
        )

    def test_route_is_registered_with_slug_path(self):
        get_rules = {
            rule.rule for rule in app.url_map.iter_rules() if "GET" in rule.methods
        }

        self.assertIn("/locais/<slug>/clima", get_rules)

    def test_unavailable_coordinates_return_correlated_safe_503(self):
        self.service.consultar_clima.side_effect = (
            exceptions.CoordenadasIndisponiveisError()
        )

        with self.assertLogs(app.logger, level="WARNING") as logs:
            response = self.client.get("/locais/arpoador/clima")

        error = self.assert_canonical_error(
            response,
            503,
            "coordenadas_indisponiveis",
            (
                "As coordenadas deste local não estão disponíveis para "
                "consulta meteorológica."
            ),
        )
        self.assertTrue(any(error["requisicao_id"] in record for record in logs.output))

    def test_every_provider_failure_returns_same_safe_climate_envelope(self):
        for reason in (
            "timeout",
            "conectividade",
            "resposta_http_invalida",
            "resposta_invalida",
        ):
            with self.subTest(reason=reason):
                self.service.consultar_clima.side_effect = (
                    exceptions.ClimaIndisponivelError(reason)
                )
                response = self.client.get("/locais/arpoador/clima")

                self.assert_canonical_error(
                    response,
                    503,
                    "clima_indisponivel",
                    ("O serviço de clima está temporariamente " "indisponível."),
                )
                self.assertNotIn(reason, response.get_data(as_text=True))

    def test_database_failure_remains_distinct_from_climate_failure(self):
        self.service.consultar_clima.side_effect = OperationalError(
            "consulta confidencial",
            {"coordenadas": "não-vazar"},
            RuntimeError("servidor interno"),
        )

        with self.assertLogs(app.logger, level="ERROR"):
            response = self.client.get("/locais/arpoador/clima")

        self.assert_canonical_error(
            response,
            503,
            "banco_indisponivel",
            "O banco de dados está temporariamente indisponível.",
        )
        response_text = response.get_data(as_text=True)
        self.assertNotIn("consulta confidencial", response_text)
        self.assertNotIn("não-vazar", response_text)
        self.assertNotIn("servidor interno", response_text)

    def test_unexpected_failure_remains_safe_internal_error(self):
        self.service.consultar_clima.side_effect = RuntimeError(
            "detalhe técnico sigiloso"
        )

        with self.assertLogs(app.logger, level="ERROR") as logs:
            response = self.client.get("/locais/arpoador/clima")

        error = self.assert_canonical_error(
            response,
            500,
            "erro_interno",
            "Ocorreu um erro interno inesperado.",
        )
        self.assertNotIn(
            "detalhe técnico sigiloso",
            response.get_data(as_text=True),
        )
        self.assertTrue(any(error["requisicao_id"] in record for record in logs.output))

    def test_climate_failure_does_not_break_local_detail_route(self):
        self.service.consultar_clima.side_effect = exceptions.ClimaIndisponivelError(
            "timeout"
        )

        with (
            self.assertLogs(app.logger, level="WARNING"),
            patch(
                "routes.local_routes.local_service.buscar_local",
                return_value=object(),
            ) as find_local,
            patch(
                "routes.local_routes.serializar_local",
                return_value={"slug": "arpoador", "nome": "Arpoador"},
            ),
        ):
            climate_response = self.client.get("/locais/arpoador/clima")
            detail_response = self.client.get("/locais/arpoador")

        self.assertEqual(climate_response.status_code, 503)
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(
            detail_response.get_json(),
            {"slug": "arpoador", "nome": "Arpoador"},
        )
        find_local.assert_called_once_with("arpoador")


if __name__ == "__main__":
    unittest.main()
