import atexit
import logging
import re
import time
from collections.abc import Callable

import httpx

from services import open_meteo_transformer
from services.open_meteo_config import OPEN_METEO_SETTINGS, OpenMeteoSettings
from utils.exceptions import ClimaIndisponivelError

OPEN_METEO_BASE_URL = "https://api.open-meteo.com"
OPEN_METEO_FORECAST_PATH = "/v1/forecast"
OPEN_METEO_TIMEZONE = open_meteo_transformer.OPEN_METEO_TIMEZONE

CURRENT_VARIABLES = (
    "temperature_2m",
    "apparent_temperature",
    "precipitation",
    "weather_code",
    "wind_speed_10m",
)
DAILY_VARIABLES = (
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_probability_max",
    "weather_code",
)

FORECAST_DAYS = 3
MAX_CONNECTIONS = 20
MAX_KEEPALIVE_CONNECTIONS = 10
KEEPALIVE_EXPIRY_SECONDS = 30.0

_DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "RotaFluminenseBackend/1.0",
}

_LOGGER = logging.getLogger(__name__)
_REQUEST_ID_PATTERN = re.compile(r"req_[0-9a-f]{32}")


def _safe_request_id(value: str | None) -> str:
    if isinstance(value, str) and _REQUEST_ID_PATTERN.fullmatch(value):
        return value
    return "ausente"


class OpenMeteoClient:
    """Encapsula o cliente HTTP síncrono dedicado ao Open-Meteo."""

    def __init__(
        self,
        settings: OpenMeteoSettings,
        *,
        transport: httpx.BaseTransport | None = None,
        monotonic_clock: Callable[[], float] = time.monotonic,
        logger: logging.Logger = _LOGGER,
    ) -> None:
        """Configura transporte, timeout e pool do cliente compartilhável."""
        timeout = httpx.Timeout(settings.timeout_seconds)
        limits = httpx.Limits(
            max_connections=MAX_CONNECTIONS,
            max_keepalive_connections=MAX_KEEPALIVE_CONNECTIONS,
            keepalive_expiry=KEEPALIVE_EXPIRY_SECONDS,
        )
        if transport is None:
            transport = httpx.HTTPTransport(
                verify=True,
                trust_env=False,
                http1=True,
                http2=False,
                limits=limits,
                retries=0,
            )
        self._client = httpx.Client(
            base_url=OPEN_METEO_BASE_URL,
            headers=_DEFAULT_HEADERS,
            verify=True,
            trust_env=False,
            http1=True,
            http2=False,
            timeout=timeout,
            follow_redirects=False,
            limits=limits,
            transport=transport,
        )
        self._monotonic_clock = monotonic_clock
        self._logger = logger

    def _registrar_tentativa(
        self,
        requisicao_id: str | None,
        resultado: str,
        duracao_ms: float,
    ) -> None:
        log = (
            self._logger.info
            if resultado == "sucesso"
            else self._logger.warning
        )
        log(
            "Consulta Open-Meteo requisicao_id=%s origem=provedor "
            "resultado=%s duracao_ms=%.3f",
            _safe_request_id(requisicao_id),
            resultado,
            max(0.0, duracao_ms),
        )

    def buscar_previsao(
        self,
        latitude: float,
        longitude: float,
        *,
        requisicao_id: str | None = None,
    ) -> open_meteo_transformer.ResultadoOpenMeteo:
        """Obtém e normaliza a previsão para coordenadas persistidas."""
        started_at = self._monotonic_clock()
        resultado = "falha_interna"
        try:
            response = self._client.get(
                OPEN_METEO_FORECAST_PATH,
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "current": ",".join(CURRENT_VARIABLES),
                    "daily": ",".join(DAILY_VARIABLES),
                    "timezone": OPEN_METEO_TIMEZONE,
                    "forecast_days": FORECAST_DAYS,
                    "temperature_unit": "celsius",
                    "wind_speed_unit": "kmh",
                    "precipitation_unit": "mm",
                    "timeformat": "iso8601",
                },
            )
            transformed = (
                open_meteo_transformer.transformar_resposta_open_meteo(
                    response
                )
            )
            resultado = "sucesso"
            return transformed
        except httpx.TimeoutException:
            resultado = "timeout"
            raise ClimaIndisponivelError(resultado) from None
        except httpx.RequestError:
            resultado = "conectividade"
            raise ClimaIndisponivelError(resultado) from None
        except open_meteo_transformer.OpenMeteoResponseError as error:
            if error.motivo == "status_http_invalido":
                resultado = "resposta_http_invalida"
            else:
                resultado = "resposta_invalida"
            raise ClimaIndisponivelError(resultado) from None
        finally:
            duration = (self._monotonic_clock() - started_at) * 1000
            self._registrar_tentativa(requisicao_id, resultado, duration)

    def close(self) -> None:
        """Libera o pool de conexões mantido pelo cliente compartilhado."""
        self._client.close()


OPEN_METEO_CLIENT = OpenMeteoClient(OPEN_METEO_SETTINGS)


def close_open_meteo_client() -> None:
    """Fecha o cliente compartilhado no encerramento normal do processo."""
    OPEN_METEO_CLIENT.close()


atexit.register(close_open_meteo_client)
