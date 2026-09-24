import os
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, sentinel

import httpx

from services import open_meteo_client
from services.open_meteo_config import OpenMeteoSettings

CURRENT_VARIABLES = open_meteo_client.CURRENT_VARIABLES
DAILY_VARIABLES = open_meteo_client.DAILY_VARIABLES
FORECAST_DAYS = open_meteo_client.FORECAST_DAYS
KEEPALIVE_EXPIRY_SECONDS = open_meteo_client.KEEPALIVE_EXPIRY_SECONDS
MAX_CONNECTIONS = open_meteo_client.MAX_CONNECTIONS
MAX_KEEPALIVE_CONNECTIONS = open_meteo_client.MAX_KEEPALIVE_CONNECTIONS
OPEN_METEO_BASE_URL = open_meteo_client.OPEN_METEO_BASE_URL
OPEN_METEO_FORECAST_PATH = open_meteo_client.OPEN_METEO_FORECAST_PATH
OPEN_METEO_TIMEZONE = open_meteo_client.OPEN_METEO_TIMEZONE
OpenMeteoClient = open_meteo_client.OpenMeteoClient
ClimaIndisponivelError = open_meteo_client.ClimaIndisponivelError

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class OpenMeteoClientTestCase(unittest.TestCase):
    def setUp(self):
        self.settings = OpenMeteoSettings(
            timeout_seconds=2.5,
            cache_ttl_seconds=1800,
        )

    def test_contract_constants_are_exact_and_not_provider_defaults(self):
        self.assertEqual(OPEN_METEO_BASE_URL, "https://api.open-meteo.com")
        self.assertEqual(OPEN_METEO_FORECAST_PATH, "/v1/forecast")
        self.assertEqual(OPEN_METEO_TIMEZONE, "America/Sao_Paulo")
        self.assertEqual(FORECAST_DAYS, 3)
        self.assertEqual(
            CURRENT_VARIABLES,
            (
                "temperature_2m",
                "apparent_temperature",
                "precipitation",
                "weather_code",
                "wind_speed_10m",
            ),
        )
        self.assertEqual(
            DAILY_VARIABLES,
            (
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_probability_max",
                "weather_code",
            ),
        )

    def test_configures_shared_sync_http_client(self):
        configured_client = Mock(spec=httpx.Client)
        transport = Mock(spec=httpx.BaseTransport)

        with patch.object(
            open_meteo_client.httpx,
            "Client",
            return_value=configured_client,
        ) as client_factory:
            client = OpenMeteoClient(
                self.settings,
                transport=transport,
            )

        self.assertIs(client._client, configured_client)
        client_factory.assert_called_once()
        options = client_factory.call_args.kwargs
        self.assertEqual(options["base_url"], OPEN_METEO_BASE_URL)
        self.assertEqual(options["headers"]["Accept"], "application/json")
        self.assertEqual(
            options["headers"]["User-Agent"],
            "RotaFluminenseBackend/1.0",
        )
        self.assertIs(options["verify"], True)
        self.assertIs(options["trust_env"], False)
        self.assertIs(options["http1"], True)
        self.assertIs(options["http2"], False)
        self.assertIs(options["follow_redirects"], False)
        self.assertIs(options["transport"], transport)

        timeout = options["timeout"]
        self.assertEqual(timeout.connect, 2.5)
        self.assertEqual(timeout.read, 2.5)
        self.assertEqual(timeout.write, 2.5)
        self.assertEqual(timeout.pool, 2.5)

        limits = options["limits"]
        self.assertEqual(limits.max_connections, MAX_CONNECTIONS)
        self.assertEqual(
            limits.max_keepalive_connections,
            MAX_KEEPALIVE_CONNECTIONS,
        )
        self.assertEqual(
            limits.keepalive_expiry,
            KEEPALIVE_EXPIRY_SECONDS,
        )

    def test_requests_only_the_approved_forecast_contract(self):
        requests = []

        def handle_request(request):
            requests.append(request)
            return httpx.Response(200, json={"ok": True})

        client = OpenMeteoClient(
            self.settings,
            transport=httpx.MockTransport(handle_request),
        )
        self.addCleanup(client.close)

        with patch.object(
            open_meteo_client.open_meteo_transformer,
            "transformar_resposta_open_meteo",
            return_value=sentinel.resultado,
        ) as transformer:
            result = client.buscar_previsao(-22.9068, -43.1729)

        self.assertIs(result, sentinel.resultado)
        self.assertEqual(len(requests), 1)
        request = requests[0]
        transformer.assert_called_once()
        self.assertEqual(transformer.call_args.args[0].status_code, 200)
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.url.scheme, "https")
        self.assertEqual(request.url.host, "api.open-meteo.com")
        self.assertEqual(request.url.path, OPEN_METEO_FORECAST_PATH)
        self.assertEqual(request.headers["Accept"], "application/json")
        self.assertEqual(
            request.headers["User-Agent"],
            "RotaFluminenseBackend/1.0",
        )

        params = request.url.params
        self.assertEqual(params["latitude"], "-22.9068")
        self.assertEqual(params["longitude"], "-43.1729")
        self.assertEqual(params["current"], ",".join(CURRENT_VARIABLES))
        self.assertEqual(params["daily"], ",".join(DAILY_VARIABLES))
        self.assertEqual(params["timezone"], OPEN_METEO_TIMEZONE)
        self.assertEqual(params["forecast_days"], str(FORECAST_DAYS))
        self.assertEqual(params["temperature_unit"], "celsius")
        self.assertEqual(params["wind_speed_unit"], "kmh")
        self.assertEqual(params["precipitation_unit"], "mm")
        self.assertEqual(params["timeformat"], "iso8601")

    def test_configures_production_transport_without_retries(self):
        configured_client = Mock(spec=httpx.Client)
        configured_transport = Mock(spec=httpx.BaseTransport)

        with (
            patch.object(
                open_meteo_client.httpx,
                "HTTPTransport",
                return_value=configured_transport,
            ) as transport_factory,
            patch.object(
                open_meteo_client.httpx,
                "Client",
                return_value=configured_client,
            ) as client_factory,
        ):
            OpenMeteoClient(self.settings)

        transport_factory.assert_called_once()
        transport_options = transport_factory.call_args.kwargs
        self.assertIs(transport_options["verify"], True)
        self.assertIs(transport_options["trust_env"], False)
        self.assertIs(transport_options["http1"], True)
        self.assertIs(transport_options["http2"], False)
        self.assertEqual(transport_options["retries"], 0)

        limits = transport_options["limits"]
        self.assertEqual(limits.max_connections, MAX_CONNECTIONS)
        self.assertEqual(
            limits.max_keepalive_connections,
            MAX_KEEPALIVE_CONNECTIONS,
        )
        self.assertEqual(
            limits.keepalive_expiry,
            KEEPALIVE_EXPIRY_SECONDS,
        )
        self.assertIs(
            client_factory.call_args.kwargs["transport"],
            configured_transport,
        )

    def test_additional_ca_extends_default_certifi_trust(self):
        settings = OpenMeteoSettings(
            timeout_seconds=2.5,
            cache_ttl_seconds=1800,
            ca_file="/run/certs/local-proxy-ca.crt",
        )
        context = Mock()
        configured_transport = Mock(spec=httpx.BaseTransport)

        with (
            patch.object(
                open_meteo_client.certifi,
                "where",
                return_value="/certifi/cacert.pem",
            ),
            patch.object(
                open_meteo_client.ssl,
                "create_default_context",
                return_value=context,
            ) as context_factory,
            patch.object(
                open_meteo_client.httpx,
                "HTTPTransport",
                return_value=configured_transport,
            ) as transport_factory,
            patch.object(open_meteo_client.httpx, "Client") as client_factory,
        ):
            OpenMeteoClient(settings)

        context_factory.assert_called_once_with(cafile="/certifi/cacert.pem")
        context.load_verify_locations.assert_called_once_with(
            cafile="/run/certs/local-proxy-ca.crt"
        )
        self.assertIs(transport_factory.call_args.kwargs["verify"], context)
        self.assertIs(client_factory.call_args.kwargs["verify"], context)

    def test_invalid_additional_ca_fails_without_exposing_path(self):
        secret_path = "/segredo/certificado-invalido.crt"
        settings = OpenMeteoSettings(
            timeout_seconds=2.5,
            cache_ttl_seconds=1800,
            ca_file=secret_path,
        )

        with patch.object(
            open_meteo_client.ssl,
            "create_default_context",
            side_effect=OSError(secret_path),
        ):
            with self.assertRaises(
                open_meteo_client.OpenMeteoConfigurationError
            ) as caught:
                OpenMeteoClient(settings)

        self.assertIn("OPEN_METEO_CA_FILE", str(caught.exception))
        self.assertNotIn(secret_path, str(caught.exception))

    def test_does_not_follow_redirects(self):
        requests = []

        def handle_request(request):
            requests.append(request)
            return httpx.Response(
                302,
                headers={"Location": "https://example.invalid/redirect"},
            )

        client = OpenMeteoClient(
            self.settings,
            transport=httpx.MockTransport(handle_request),
        )
        self.addCleanup(client.close)

        with self.assertRaises(ClimaIndisponivelError) as caught:
            client.buscar_previsao(-22.9068, -43.1729)

        self.assertEqual(caught.exception.motivo, "resposta_http_invalida")
        self.assertEqual(len(requests), 1)

    def test_success_registers_safe_provider_result_and_duration(self):
        logger = Mock()
        clock = Mock(side_effect=(20.0, 20.125))
        request_id = f"req_{'a' * 32}"
        client = OpenMeteoClient(
            self.settings,
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"ok": True})
            ),
            monotonic_clock=clock,
            logger=logger,
        )
        self.addCleanup(client.close)

        with patch.object(
            open_meteo_client.open_meteo_transformer,
            "transformar_resposta_open_meteo",
            return_value=sentinel.resultado,
        ):
            result = client.buscar_previsao(
                -22.9068,
                -43.1729,
                requisicao_id=request_id,
            )

        self.assertIs(result, sentinel.resultado)
        logger.info.assert_called_once_with(
            "Consulta Open-Meteo requisicao_id=%s origem=provedor "
            "resultado=%s duracao_ms=%.3f",
            request_id,
            "sucesso",
            125.0,
        )
        logger.warning.assert_not_called()

    def test_timeout_is_converted_to_safe_application_error_and_logged(self):
        secret = "token-super-secreto"
        logger = Mock()
        clock = Mock(side_effect=(30.0, 30.25))

        def timeout(request):
            raise httpx.ReadTimeout(secret, request=request)

        client = OpenMeteoClient(
            self.settings,
            transport=httpx.MockTransport(timeout),
            monotonic_clock=clock,
            logger=logger,
        )
        self.addCleanup(client.close)

        with self.assertRaises(ClimaIndisponivelError) as caught:
            client.buscar_previsao(
                -22.9068,
                -43.1729,
                requisicao_id=f"req_{'b' * 32}",
            )

        error = caught.exception
        self.assertEqual(error.codigo, "clima_indisponivel")
        self.assertEqual(error.status_code, 503)
        self.assertEqual(error.detalhes, [])
        self.assertEqual(error.motivo, "timeout")
        self.assertNotIn(secret, str(error))
        log_text = str(logger.mock_calls)
        self.assertIn("timeout", log_text)
        self.assertIn("250.0", log_text)
        self.assertNotIn(secret, log_text)
        self.assertNotIn("-22.9068", log_text)
        self.assertNotIn("-43.1729", log_text)

    def test_connectivity_failure_is_converted_without_external_details(self):
        secret = "host-interno-sigiloso"
        logger = Mock()

        def connection_failure(request):
            raise httpx.ConnectError(secret, request=request)

        client = OpenMeteoClient(
            self.settings,
            transport=httpx.MockTransport(connection_failure),
            monotonic_clock=Mock(side_effect=(40.0, 40.01)),
            logger=logger,
        )
        self.addCleanup(client.close)

        with self.assertRaises(ClimaIndisponivelError) as caught:
            client.buscar_previsao(-22.9068, -43.1729)

        self.assertEqual(caught.exception.motivo, "conectividade")
        self.assertNotIn(secret, str(caught.exception))
        log_text = str(logger.mock_calls)
        self.assertIn("requisicao_id=%s", log_text)
        self.assertIn("ausente", log_text)
        self.assertIn("conectividade", log_text)
        self.assertNotIn(secret, log_text)

    def test_http_and_payload_failures_receive_safe_classifications(self):
        cases = (
            (
                httpx.Response(
                    503,
                    headers={"content-type": "text/plain"},
                    text="corpo-externo-sigiloso",
                ),
                "resposta_http_invalida",
                "corpo-externo-sigiloso",
            ),
            (
                httpx.Response(
                    429,
                    headers={"content-type": "application/json"},
                    json={"erro": "limite-externo-sigiloso"},
                ),
                "resposta_http_invalida",
                "limite-externo-sigiloso",
            ),
            (
                httpx.Response(
                    200,
                    headers={"content-type": "application/json"},
                    content=b"json-externo-invalido",
                ),
                "resposta_invalida",
                "json-externo-invalido",
            ),
            (
                httpx.Response(
                    200,
                    headers={"content-type": "application/json"},
                    json={
                        "timezone": "America/Sao_Paulo",
                        "segredo": True,
                    },
                ),
                "resposta_invalida",
                "segredo",
            ),
        )

        for response, expected_reason, secret in cases:
            with self.subTest(expected_reason=expected_reason):
                logger = Mock()
                client = OpenMeteoClient(
                    self.settings,
                    transport=httpx.MockTransport(
                        lambda request, current=response: current
                    ),
                    monotonic_clock=Mock(side_effect=(50.0, 50.02)),
                    logger=logger,
                )
                self.addCleanup(client.close)

                with self.assertRaises(ClimaIndisponivelError) as caught:
                    client.buscar_previsao(-22.9068, -43.1729)

                self.assertEqual(caught.exception.motivo, expected_reason)
                log_text = str(logger.mock_calls)
                self.assertIn(expected_reason, log_text)
                self.assertNotIn(secret, log_text)

    def test_climate_error_rejects_an_unsafe_internal_reason(self):
        with self.assertRaises(ValueError) as caught:
            ClimaIndisponivelError("segredo-do-provedor")

        self.assertNotIn("segredo-do-provedor", str(caught.exception))

    def test_close_releases_the_underlying_client(self):
        configured_client = Mock(spec=httpx.Client)
        with patch.object(
            open_meteo_client.httpx,
            "Client",
            return_value=configured_client,
        ):
            client = OpenMeteoClient(self.settings)

        client.close()

        configured_client.close.assert_called_once_with()

    def test_application_exposes_the_process_shared_client(self):
        environment = os.environ.copy()
        environment["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
        environment["OPEN_METEO_TIMEOUT_SECONDS"] = "5"
        environment["OPEN_METEO_CACHE_TTL_SECONDS"] = "1800"
        environment["PYTHONUTF8"] = "1"
        code = """
            from app import app
            from services.open_meteo_client import OPEN_METEO_CLIENT

            assert app.config["OPEN_METEO_CLIENT"] is OPEN_METEO_CLIENT
            """

        result = subprocess.run(
            [sys.executable, "-c", textwrap.dedent(code)],
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
