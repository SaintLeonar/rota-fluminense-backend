import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

TIMEOUT_ENV_VAR = "OPEN_METEO_TIMEOUT_SECONDS"
CACHE_TTL_ENV_VAR = "OPEN_METEO_CACHE_TTL_SECONDS"
CA_FILE_ENV_VAR = "OPEN_METEO_CA_FILE"

DEFAULT_TIMEOUT_SECONDS = 5.0
MIN_TIMEOUT_SECONDS = Decimal("0.1")
MAX_TIMEOUT_SECONDS = Decimal("30.0")

DEFAULT_CACHE_TTL_SECONDS = 1800
MIN_CACHE_TTL_SECONDS = 1
MAX_CACHE_TTL_SECONDS = 86400

_DECIMAL_PATTERN = re.compile(r"[0-9]+(?:\.[0-9]+)?")
_INTEGER_PATTERN = re.compile(r"[0-9]+")


class OpenMeteoConfigurationError(RuntimeError):
    """Indica configuração meteorológica ausente ou inválida."""


@dataclass(frozen=True, slots=True)
class OpenMeteoSettings:
    """Mantém a configuração validada e imutável do Open-Meteo."""

    timeout_seconds: float
    cache_ttl_seconds: int
    ca_file: str | None = None


def _timeout_error() -> OpenMeteoConfigurationError:
    return OpenMeteoConfigurationError(
        f"A variável de ambiente {TIMEOUT_ENV_VAR} deve conter um número "
        "finito entre 0.1 e 30.0 segundos."
    )


def _cache_ttl_error() -> OpenMeteoConfigurationError:
    return OpenMeteoConfigurationError(
        f"A variável de ambiente {CACHE_TTL_ENV_VAR} deve conter um inteiro "
        "entre 1 e 86400 segundos."
    )


def _ca_file_error() -> OpenMeteoConfigurationError:
    return OpenMeteoConfigurationError(
        f"A variável de ambiente {CA_FILE_ENV_VAR} deve indicar um arquivo "
        "PEM legível com uma autoridade certificadora adicional."
    )


def _load_timeout_seconds(environment: Mapping[str, str]) -> float:
    raw_value = environment.get(TIMEOUT_ENV_VAR)
    if raw_value is None:
        return DEFAULT_TIMEOUT_SECONDS

    value = raw_value.strip()
    if not _DECIMAL_PATTERN.fullmatch(value):
        raise _timeout_error()

    try:
        parsed = Decimal(value)
    except InvalidOperation:
        raise _timeout_error() from None

    if (
        not parsed.is_finite()
        or parsed < MIN_TIMEOUT_SECONDS
        or parsed > MAX_TIMEOUT_SECONDS
    ):
        raise _timeout_error()

    return float(parsed)


def _load_cache_ttl_seconds(environment: Mapping[str, str]) -> int:
    raw_value = environment.get(CACHE_TTL_ENV_VAR)
    if raw_value is None:
        return DEFAULT_CACHE_TTL_SECONDS

    value = raw_value.strip()
    if not _INTEGER_PATTERN.fullmatch(value):
        raise _cache_ttl_error()

    parsed = int(value)
    if not MIN_CACHE_TTL_SECONDS <= parsed <= MAX_CACHE_TTL_SECONDS:
        raise _cache_ttl_error()

    return parsed


def _load_ca_file(environment: Mapping[str, str]) -> str | None:
    raw_value = environment.get(CA_FILE_ENV_VAR)
    if raw_value is None:
        return None

    value = raw_value.strip()
    if not value or "\x00" in value:
        raise _ca_file_error()
    return value


def load_open_meteo_settings(
    environment: Mapping[str, str] | None = None,
) -> OpenMeteoSettings:
    """Obtém e valida as configurações do Open-Meteo."""
    source = os.environ if environment is None else environment
    return OpenMeteoSettings(
        timeout_seconds=_load_timeout_seconds(source),
        cache_ttl_seconds=_load_cache_ttl_seconds(source),
        ca_file=_load_ca_file(source),
    )


OPEN_METEO_SETTINGS = load_open_meteo_settings()
