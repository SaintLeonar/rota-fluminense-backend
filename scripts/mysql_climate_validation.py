"""Valida clima em MySQL usando exclusivamente transporte HTTP simulado."""

from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from sqlalchemy import select

from models.base import SessionLocal
from models.local_turistico import LocalTuristico
from services.open_meteo_cache import CacheOpenMeteo
from services.open_meteo_client import OpenMeteoClient
from services.open_meteo_config import OpenMeteoSettings
from services.open_meteo_service import OpenMeteoService

TARGET_SLUG = "arpoador"
INVALID_COORDINATE_SLUG = "validacao-mysql-b7-coordenada"


class _FixedClock:
    def __init__(self):
        self.monotonic_value = 1000.0
        self.utc_value = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)

    def monotonic(self):
        return self.monotonic_value

    def utc_now(self):
        return self.utc_value


def _assert_status(response, expected_status):
    if response.status_code != expected_status:
        raise AssertionError(
            f"Status esperado {expected_status}, recebido "
            f"{response.status_code}: {response.get_data(as_text=True)}"
        )
    return response.get_json(silent=True)


def _assert_error(response, expected_code):
    payload = _assert_status(response, 503)
    error = payload["erro"]
    if error["codigo"] != expected_code or error["detalhes"] != []:
        raise AssertionError("O erro climático não é seguro.")
    if error["requisicao_id"] != response.headers.get("X-Request-ID"):
        raise AssertionError("O erro climático perdeu a correlação.")
    return error


def _valid_provider_payload():
    return {
        "latitude": -23.0,
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
            "time": "2026-09-22T09:00",
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
            "time": ["2026-09-22", "2026-09-23", "2026-09-24"],
            "temperature_2m_max": [27.1, 26.5, 25.8],
            "temperature_2m_min": [19.4, 20.1, 19.8],
            "precipitation_probability_max": [10, 35, 45],
            "weather_code": [1, 2, 61],
        },
    }


@contextmanager
def _configured_service(app, handler):
    calls = []

    def counted_handler(request):
        calls.append(request)
        return handler(request)

    clock = _FixedClock()
    settings = OpenMeteoSettings(timeout_seconds=1.0, cache_ttl_seconds=30)
    provider_client = OpenMeteoClient(
        settings,
        transport=httpx.MockTransport(counted_handler),
        monotonic_clock=clock.monotonic,
    )
    cache = CacheOpenMeteo(
        settings.cache_ttl_seconds,
        monotonic_clock=clock.monotonic,
        utc_clock=clock.utc_now,
    )
    service = OpenMeteoService(
        session_factory=SessionLocal,
        client=provider_client,
        cache=cache,
        monotonic_clock=clock.monotonic,
    )
    original_service = app.config["OPEN_METEO_SERVICE"]
    app.config["OPEN_METEO_SERVICE"] = service
    try:
        yield calls, service
    finally:
        app.config["OPEN_METEO_SERVICE"] = original_service
        provider_client.close()


def _persisted_target():
    with SessionLocal() as session:
        return session.execute(
            select(
                LocalTuristico.nome,
                LocalTuristico.latitude,
                LocalTuristico.longitude,
            ).where(LocalTuristico.slug == TARGET_SLUG)
        ).one()


def _validate_success_and_cache(app, client):
    local_name, latitude, longitude = _persisted_target()

    def success_handler(request):
        if request.url.host != "api.open-meteo.com":
            raise AssertionError("O transporte recebeu um host inesperado.")
        if float(request.url.params["latitude"]) != float(latitude):
            raise AssertionError("A latitude não veio do MySQL.")
        if float(request.url.params["longitude"]) != float(longitude):
            raise AssertionError("A longitude não veio do MySQL.")
        return httpx.Response(200, json=_valid_provider_payload())

    with _configured_service(app, success_handler) as (calls, _):
        first = _assert_status(client.get(f"/locais/{TARGET_SLUG}/clima"), 200)
        second = _assert_status(
            client.get(f"/locais/{TARGET_SLUG}/clima"),
            200,
        )

    if len(calls) != 1:
        raise AssertionError("O cache não evitou a segunda chamada.")
    if first["local"] != {"slug": TARGET_SLUG, "nome": local_name}:
        raise AssertionError("O clima não identificou o local persistido.")
    if len(first["previsao"]) != 3:
        raise AssertionError("A previsão não contém exatamente três dias.")
    if first["cache"]["utilizado"] is not False:
        raise AssertionError("A primeira consulta deveria vir do provedor.")
    if second["cache"]["utilizado"] is not True:
        raise AssertionError("A segunda consulta deveria vir do cache.")
    if first["atualizado_em"] != second["atualizado_em"]:
        raise AssertionError("O cache alterou o instante da previsão.")


def _validate_provider_failures(app, client):
    def timeout_handler(request):
        raise httpx.ReadTimeout("timeout controlado B7", request=request)

    with _configured_service(app, timeout_handler) as (timeout_calls, _):
        timeout_response = client.get(f"/locais/{TARGET_SLUG}/clima")
        _assert_error(timeout_response, "clima_indisponivel")
        detail = _assert_status(client.get(f"/locais/{TARGET_SLUG}"), 200)
    if len(timeout_calls) != 1:
        raise AssertionError("O timeout não executou uma tentativa simulada.")
    if detail["slug"] != TARGET_SLUG:
        raise AssertionError("A falha climática afetou o detalhe do local.")
    if "timeout controlado B7" in timeout_response.get_data(as_text=True):
        raise AssertionError("O detalhe do timeout vazou na resposta pública.")

    def invalid_handler(request):
        return httpx.Response(200, json={"timezone": "America/Sao_Paulo"})

    with _configured_service(app, invalid_handler) as (invalid_calls, _):
        invalid_response = client.get(f"/locais/{TARGET_SLUG}/clima")
        _assert_error(invalid_response, "clima_indisponivel")
    if len(invalid_calls) != 1:
        raise AssertionError("A resposta inválida não foi transformada.")


def _validate_invalid_coordinates(app, client):
    local_name, _, longitude = _persisted_target()

    def unexpected_handler(request):
        raise AssertionError("Coordenada ausente chamou o provedor.")

    missing_coordinate = SimpleNamespace(
        slug=TARGET_SLUG,
        nome=local_name,
        latitude=None,
        longitude=longitude,
    )
    with _configured_service(app, unexpected_handler) as (calls, service):
        with patch.object(
            service,
            "_buscar_local",
            return_value=missing_coordinate,
        ):
            response = client.get(f"/locais/{TARGET_SLUG}/clima")
            _assert_error(response, "coordenadas_indisponiveis")
    if calls:
        raise AssertionError("O provedor recebeu coordenada ausente.")


def validate_climate(app, client):
    """Valida sucesso, cache, falhas e coordenadas usando MySQL real."""
    _validate_success_and_cache(app, client)
    _validate_provider_failures(app, client)
    _validate_invalid_coordinates(app, client)
