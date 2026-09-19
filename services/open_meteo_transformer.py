import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from services import open_meteo_wmo

OPEN_METEO_TIMEZONE = "America/Sao_Paulo"
MAX_RESPONSE_BYTES = 1024 * 1024
EXPECTED_FORECAST_DAYS = 3

_DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_DATETIME_PATTERN = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}"
    r"(?::[0-9]{2}(?:\.[0-9]+)?)?(?:Z|[+-][0-9]{2}:[0-9]{2})?"
)

_EXPECTED_CURRENT_UNITS = {
    "time": "iso8601",
    "temperature_2m": "°C",
    "apparent_temperature": "°C",
    "precipitation": "mm",
    "weather_code": "wmo code",
    "wind_speed_10m": "km/h",
}
_EXPECTED_DAILY_UNITS = {
    "time": "iso8601",
    "temperature_2m_max": "°C",
    "temperature_2m_min": "°C",
    "precipitation_probability_max": "%",
    "weather_code": "wmo code",
}

_ERROR_MESSAGES = {
    "status_http_invalido": (
        "O Open-Meteo respondeu com status HTTP inesperado."
    ),
    "resposta_muito_grande": (
        "A resposta do Open-Meteo excede o limite permitido."
    ),
    "tipo_conteudo_invalido": (
        "A resposta do Open-Meteo não possui conteúdo JSON compatível."
    ),
    "json_invalido": "A resposta do Open-Meteo contém JSON inválido.",
    "estrutura_invalida": (
        "A resposta do Open-Meteo não segue a estrutura esperada."
    ),
}


class OpenMeteoResponseError(ValueError):
    """Indica uma resposta externa que não pode ser usada com segurança."""

    def __init__(self, motivo: str) -> None:
        """Inicializa o erro com motivo interno e mensagem sem payload."""
        self.motivo = motivo
        super().__init__(_ERROR_MESSAGES[motivo])


@dataclass(frozen=True, slots=True)
class ClimaAtualOpenMeteo:
    """Representa a observação atual já validada e normalizada."""

    observado_em: datetime
    temperatura_c: float
    sensacao_termica_c: float
    precipitacao_mm: float
    velocidade_vento_kmh: float
    codigo_meteorologico: int
    descricao: str
    icone: str


@dataclass(frozen=True, slots=True)
class PrevisaoDiariaOpenMeteo:
    """Representa um dia de previsão já validado e normalizado."""

    data: date
    temperatura_max_c: float
    temperatura_min_c: float
    probabilidade_precipitacao_max_pct: float
    codigo_meteorologico: int
    descricao: str
    icone: str


@dataclass(frozen=True, slots=True)
class ResultadoOpenMeteo:
    """Agrupa os dados meteorológicos normalizados antes do cache."""

    timezone: str
    atual: ClimaAtualOpenMeteo
    previsao: tuple[PrevisaoDiariaOpenMeteo, ...]


def _invalid_structure() -> None:
    raise OpenMeteoResponseError("estrutura_invalida")


def _required(mapping: dict[str, Any], key: str) -> Any:
    if key not in mapping:
        _invalid_structure()
    return mapping[key]


def _required_object(mapping: dict[str, Any], key: str) -> dict[str, Any]:
    value = _required(mapping, key)
    if not isinstance(value, dict):
        _invalid_structure()
    return value


def _required_list(mapping: dict[str, Any], key: str) -> list[Any]:
    value = _required(mapping, key)
    if not isinstance(value, list):
        _invalid_structure()
    return value


def _required_text(mapping: dict[str, Any], key: str) -> str:
    value = _required(mapping, key)
    if not isinstance(value, str) or not value:
        _invalid_structure()
    return value


def _finite_number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _invalid_structure()
    try:
        normalized = float(value)
    except (OverflowError, ValueError):
        _invalid_structure()
    if not math.isfinite(normalized):
        _invalid_structure()
    return normalized


def _integer(value: Any) -> int:
    if type(value) is not int:
        _invalid_structure()
    return value


def _parse_datetime(value: Any) -> datetime:
    if not isinstance(value, str) or not _DATETIME_PATTERN.fullmatch(value):
        _invalid_structure()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _invalid_structure()

    timezone_sp = ZoneInfo(OPEN_METEO_TIMEZONE)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone_sp)
    return parsed.astimezone(timezone_sp)


def _parse_date(value: Any) -> date:
    if not isinstance(value, str) or not _DATE_PATTERN.fullmatch(value):
        _invalid_structure()
    try:
        return date.fromisoformat(value)
    except ValueError:
        _invalid_structure()


def _validate_units(
    payload: dict[str, Any],
    block_name: str,
    expected: dict[str, str],
) -> None:
    units = _required_object(payload, block_name)
    for key, expected_unit in expected.items():
        if _required(units, key) != expected_unit:
            _invalid_structure()


def _transform_current(
    payload: dict[str, Any],
    utc_offset_seconds: int,
) -> ClimaAtualOpenMeteo:
    current = _required_object(payload, "current")
    observed_at = _parse_datetime(_required(current, "time"))
    observed_offset = observed_at.utcoffset()
    if (
        observed_offset is None
        or int(observed_offset.total_seconds()) != utc_offset_seconds
    ):
        _invalid_structure()
    condition = open_meteo_wmo.traduzir_codigo_wmo(
        _integer(_required(current, "weather_code"))
    )

    return ClimaAtualOpenMeteo(
        observado_em=observed_at,
        temperatura_c=_finite_number(_required(current, "temperature_2m")),
        sensacao_termica_c=_finite_number(
            _required(current, "apparent_temperature")
        ),
        precipitacao_mm=_finite_number(_required(current, "precipitation")),
        velocidade_vento_kmh=_finite_number(
            _required(current, "wind_speed_10m")
        ),
        codigo_meteorologico=condition.codigo_meteorologico,
        descricao=condition.descricao,
        icone=condition.icone,
    )


def _transform_daily(
    payload: dict[str, Any],
) -> tuple[PrevisaoDiariaOpenMeteo, ...]:
    daily = _required_object(payload, "daily")
    fields = {
        "time": _required_list(daily, "time"),
        "temperature_2m_max": _required_list(
            daily,
            "temperature_2m_max",
        ),
        "temperature_2m_min": _required_list(
            daily,
            "temperature_2m_min",
        ),
        "precipitation_probability_max": _required_list(
            daily,
            "precipitation_probability_max",
        ),
        "weather_code": _required_list(daily, "weather_code"),
    }
    if any(
        len(values) != EXPECTED_FORECAST_DAYS for values in fields.values()
    ):
        _invalid_structure()

    dates = tuple(_parse_date(value) for value in fields["time"])
    if dates != tuple(sorted(dates)) or len(set(dates)) != len(dates):
        _invalid_structure()

    forecast = []
    for index in range(EXPECTED_FORECAST_DAYS):
        condition = open_meteo_wmo.traduzir_codigo_wmo(
            _integer(fields["weather_code"][index])
        )
        forecast.append(
            PrevisaoDiariaOpenMeteo(
                data=dates[index],
                temperatura_max_c=_finite_number(
                    fields["temperature_2m_max"][index]
                ),
                temperatura_min_c=_finite_number(
                    fields["temperature_2m_min"][index]
                ),
                probabilidade_precipitacao_max_pct=_finite_number(
                    fields["precipitation_probability_max"][index]
                ),
                codigo_meteorologico=condition.codigo_meteorologico,
                descricao=condition.descricao,
                icone=condition.icone,
            )
        )
    return tuple(forecast)


def _is_json_content_type(value: str) -> bool:
    media_type = value.partition(";")[0].strip().lower()
    return media_type == "application/json" or media_type.endswith("+json")


def transformar_resposta_open_meteo(
    response: httpx.Response,
) -> ResultadoOpenMeteo:
    """Valida e normaliza uma resposta da Weather Forecast API."""
    if response.status_code != 200:
        raise OpenMeteoResponseError("status_http_invalido")
    if len(response.content) > MAX_RESPONSE_BYTES:
        raise OpenMeteoResponseError("resposta_muito_grande")
    if not _is_json_content_type(response.headers.get("content-type", "")):
        raise OpenMeteoResponseError("tipo_conteudo_invalido")

    try:
        payload = response.json()
    except ValueError:
        raise OpenMeteoResponseError("json_invalido") from None
    if not isinstance(payload, dict):
        _invalid_structure()

    timezone_name = _required_text(payload, "timezone")
    if timezone_name != OPEN_METEO_TIMEZONE:
        _invalid_structure()
    utc_offset_seconds = _integer(_required(payload, "utc_offset_seconds"))

    _validate_units(payload, "current_units", _EXPECTED_CURRENT_UNITS)
    _validate_units(payload, "daily_units", _EXPECTED_DAILY_UNITS)

    return ResultadoOpenMeteo(
        timezone=timezone_name,
        atual=_transform_current(payload, utc_offset_seconds),
        previsao=_transform_daily(payload),
    )
