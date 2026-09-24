import json
import unittest
from dataclasses import FrozenInstanceError
from datetime import date, timedelta

import httpx

from services import open_meteo_transformer

EXPECTED_FORECAST_DAYS = open_meteo_transformer.EXPECTED_FORECAST_DAYS
MAX_RESPONSE_BYTES = open_meteo_transformer.MAX_RESPONSE_BYTES
OpenMeteoResponseError = open_meteo_transformer.OpenMeteoResponseError
transformar_resposta_open_meteo = open_meteo_transformer.transformar_resposta_open_meteo
MISSING = object()


def valid_payload():
    return {
        "latitude": -22.9,
        "longitude": -43.2,
        "generationtime_ms": 0.2,
        "utc_offset_seconds": -10800,
        "timezone": "America/Sao_Paulo",
        "timezone_abbreviation": "GMT-3",
        "elevation": 5.0,
        "current_units": {
            "time": "iso8601",
            "interval": "seconds",
            "temperature_2m": "°C",
            "apparent_temperature": "°C",
            "precipitation": "mm",
            "weather_code": "wmo code",
            "wind_speed_10m": "km/h",
        },
        "current": {
            "time": "2026-09-17T00:15",
            "interval": 900,
            "temperature_2m": 24.3,
            "apparent_temperature": 24.8,
            "precipitation": 0,
            "weather_code": 1,
            "wind_speed_10m": 18.2,
        },
        "daily_units": {
            "time": "iso8601",
            "temperature_2m_max": "°C",
            "temperature_2m_min": "°C",
            "precipitation_probability_max": "%",
            "weather_code": "wmo code",
        },
        "daily": {
            "time": ["2026-09-17", "2026-09-18", "2026-09-19"],
            "temperature_2m_max": [27.1, 26.5, 25.8],
            "temperature_2m_min": [19.4, 20.1, 19.8],
            "precipitation_probability_max": [10, 35, 45],
            "weather_code": [1, 2, 61],
        },
    }


def make_response(
    payload=MISSING,
    *,
    status_code=200,
    content_type="application/json; charset=utf-8",
    content=None,
):
    if content is None:
        content = json.dumps(
            valid_payload() if payload is MISSING else payload,
            ensure_ascii=False,
        ).encode("utf-8")
    headers = {}
    if content_type is not None:
        headers["Content-Type"] = content_type
    return httpx.Response(status_code, headers=headers, content=content)


def remove_path(payload, path):
    target = payload
    for key in path[:-1]:
        target = target[key]
    del target[path[-1]]


class OpenMeteoTransformerTestCase(unittest.TestCase):
    def assert_invalid(self, response, motivo="estrutura_invalida"):
        with self.assertRaises(OpenMeteoResponseError) as context:
            transformar_resposta_open_meteo(response)
        self.assertEqual(context.exception.motivo, motivo)
        return context.exception

    def test_transforms_valid_payload_into_immutable_normalized_model(self):
        result = transformar_resposta_open_meteo(make_response())

        self.assertEqual(result.timezone, "America/Sao_Paulo")
        self.assertEqual(
            result.atual.observado_em.isoformat(),
            "2026-09-17T00:15:00-03:00",
        )
        self.assertEqual(
            result.atual.observado_em.utcoffset(),
            timedelta(hours=-3),
        )
        self.assertEqual(result.atual.temperatura_c, 24.3)
        self.assertEqual(result.atual.sensacao_termica_c, 24.8)
        self.assertEqual(result.atual.precipitacao_mm, 0.0)
        self.assertEqual(result.atual.velocidade_vento_kmh, 18.2)
        self.assertEqual(result.atual.codigo_meteorologico, 1)
        self.assertEqual(result.atual.descricao, "Predominantemente limpo")
        self.assertEqual(result.atual.icone, "predominantemente_limpo")
        self.assertIsInstance(result.previsao, tuple)
        self.assertEqual(len(result.previsao), EXPECTED_FORECAST_DAYS)
        self.assertEqual(result.previsao[0].data, date(2026, 9, 17))
        self.assertEqual(result.previsao[0].temperatura_max_c, 27.1)
        self.assertEqual(result.previsao[0].temperatura_min_c, 19.4)
        self.assertEqual(
            result.previsao[0].probabilidade_precipitacao_max_pct,
            10.0,
        )
        self.assertEqual(result.previsao[2].codigo_meteorologico, 61)
        self.assertEqual(result.previsao[2].descricao, "Chuva fraca")
        self.assertEqual(result.previsao[2].icone, "chuva_fraca")

        with self.assertRaises(FrozenInstanceError):
            result.timezone = "UTC"

    def test_accepts_json_compatible_media_type(self):
        result = transformar_resposta_open_meteo(
            make_response(content_type="application/weather+json")
        )

        self.assertEqual(result.timezone, "America/Sao_Paulo")

    def test_enriches_unknown_integer_weather_codes_with_fallback(self):
        payload = valid_payload()
        payload["current"]["weather_code"] = 123
        payload["daily"]["weather_code"] = [-1, 4, 100]

        result = transformar_resposta_open_meteo(make_response(payload))

        self.assertEqual(result.atual.codigo_meteorologico, 123)
        self.assertEqual(
            result.atual.descricao,
            "Condição meteorológica desconhecida",
        )
        self.assertEqual(result.atual.icone, "condicao_desconhecida")
        self.assertEqual(
            [item.codigo_meteorologico for item in result.previsao],
            [-1, 4, 100],
        )
        self.assertTrue(
            all(
                item.descricao == "Condição meteorológica desconhecida"
                and item.icone == "condicao_desconhecida"
                for item in result.previsao
            )
        )

    def test_rejects_every_non_200_status(self):
        for status_code in (199, 201, 302, 400, 503):
            with self.subTest(status_code=status_code):
                self.assert_invalid(
                    make_response(status_code=status_code),
                    "status_http_invalido",
                )

    def test_rejects_response_larger_than_one_mebibyte(self):
        response = make_response(content=b"x" * (MAX_RESPONSE_BYTES + 1))

        self.assert_invalid(response, "resposta_muito_grande")

    def test_rejects_missing_or_incompatible_content_type(self):
        for content_type in (None, "", "text/plain", "application/xml"):
            with self.subTest(content_type=content_type):
                self.assert_invalid(
                    make_response(content_type=content_type),
                    "tipo_conteudo_invalido",
                )

    def test_rejects_invalid_json_and_non_object_root(self):
        self.assert_invalid(
            make_response(content=b'{"segredo":'),
            "json_invalido",
        )
        for payload in ([], "texto", 1, None):
            with self.subTest(payload=payload):
                self.assert_invalid(make_response(payload))

    def test_rejects_missing_required_fields(self):
        paths = (
            ("timezone",),
            ("utc_offset_seconds",),
            ("current_units",),
            ("daily_units",),
            ("current",),
            ("daily",),
            ("current", "time"),
            ("current", "temperature_2m"),
            ("current", "apparent_temperature"),
            ("current", "precipitation"),
            ("current", "weather_code"),
            ("current", "wind_speed_10m"),
            ("daily", "time"),
            ("daily", "temperature_2m_max"),
            ("daily", "temperature_2m_min"),
            ("daily", "precipitation_probability_max"),
            ("daily", "weather_code"),
        )
        for path in paths:
            with self.subTest(path=path):
                payload = valid_payload()
                remove_path(payload, path)
                self.assert_invalid(make_response(payload))

    def test_rejects_invalid_object_and_daily_series_types(self):
        cases = (
            (("current",), []),
            (("daily",), "invalido"),
            (("current_units",), []),
            (("daily_units",), None),
            (("daily", "time"), "2026-09-17"),
            (("daily", "weather_code"), {"0": 1, "1": 2, "2": 3}),
        )
        for path, value in cases:
            with self.subTest(path=path, value=value):
                payload = valid_payload()
                target = payload
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                self.assert_invalid(make_response(payload))

    def test_rejects_invalid_current_numbers_and_weather_code(self):
        cases = (
            ("temperature_2m", "24.3"),
            ("apparent_temperature", True),
            ("precipitation", None),
            ("wind_speed_10m", []),
            ("weather_code", 1.0),
            ("weather_code", False),
        )
        for field, value in cases:
            with self.subTest(field=field, value=value):
                payload = valid_payload()
                payload["current"][field] = value
                self.assert_invalid(make_response(payload))

    def test_rejects_invalid_or_non_finite_daily_values(self):
        cases = (
            ("temperature_2m_max", "27.1"),
            ("temperature_2m_min", True),
            ("precipitation_probability_max", None),
            ("weather_code", 1.0),
            ("weather_code", False),
            ("temperature_2m_max", float("nan")),
            ("temperature_2m_min", float("inf")),
            ("precipitation_probability_max", float("-inf")),
        )
        for field, value in cases:
            with self.subTest(field=field, value=value):
                payload = valid_payload()
                payload["daily"][field][1] = value
                self.assert_invalid(make_response(payload))

    def test_rejects_non_finite_current_values(self):
        fields = (
            "temperature_2m",
            "apparent_temperature",
            "precipitation",
            "wind_speed_10m",
        )
        for field in fields:
            for value in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(field=field, value=value):
                    payload = valid_payload()
                    payload["current"][field] = value
                    self.assert_invalid(make_response(payload))

    def test_rejects_daily_vectors_with_length_other_than_three(self):
        fields = (
            "time",
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_probability_max",
            "weather_code",
        )
        for field in fields:
            for length in (0, 2, 4):
                with self.subTest(field=field, length=length):
                    payload = valid_payload()
                    original = payload["daily"][field]
                    payload["daily"][field] = (original * 2)[:length]
                    self.assert_invalid(make_response(payload))

    def test_rejects_invalid_times_and_unordered_or_duplicate_dates(self):
        current_times = (
            "",
            "2026-09-17",
            "17/09/2026 00:15",
            "2026-13-17T00:15",
        )
        for current_time in current_times:
            with self.subTest(current_time=current_time):
                payload = valid_payload()
                payload["current"]["time"] = current_time
                self.assert_invalid(make_response(payload))

        daily_dates = (
            ["2026-09-17", "2026-09-19", "2026-09-18"],
            ["2026-09-17", "2026-09-17", "2026-09-19"],
            ["2026-09-17", "17/09/2026", "2026-09-19"],
            ["2026-09-17", "2026-02-30", "2026-09-19"],
        )
        for dates in daily_dates:
            with self.subTest(dates=dates):
                payload = valid_payload()
                payload["daily"]["time"] = dates
                self.assert_invalid(make_response(payload))

    def test_rejects_wrong_timezone_offset_or_units(self):
        cases = (
            (("timezone",), "UTC"),
            (("utc_offset_seconds",), 0),
            (("utc_offset_seconds",), True),
            (("current_units", "temperature_2m"), "°F"),
            (("current_units", "weather_code"), "code"),
            (("daily_units", "temperature_2m_max"), "°F"),
            (("daily_units", "precipitation_probability_max"), "ratio"),
        )
        for path, value in cases:
            with self.subTest(path=path, value=value):
                payload = valid_payload()
                target = payload
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                self.assert_invalid(make_response(payload))

    def test_errors_do_not_expose_external_payload(self):
        secret = "conteudo-externo-nao-deve-vazar"
        error = self.assert_invalid(
            make_response(content=f'{{"{secret}":'.encode()),
            "json_invalido",
        )

        self.assertNotIn(secret, str(error))


if __name__ == "__main__":
    unittest.main()
