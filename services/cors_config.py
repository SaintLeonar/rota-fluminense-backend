"""Configuração validada e restritiva de CORS da API pública."""

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

from flask_cors import CORS

CORS_ALLOWED_ORIGINS_ENV_VAR = "CORS_ALLOWED_ORIGINS"

_ORIGIN_PATTERN = re.compile(
    r"https?://(?:localhost|[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?|"
    r"\[[0-9a-f:]+\])(?::[1-9][0-9]{0,4})?",
    re.IGNORECASE,
)


class CorsConfigurationError(RuntimeError):
    """Indica configuração CORS ausente, vazia ou insegura."""


@dataclass(frozen=True, slots=True)
class CorsSettings:
    """Mantém a lista normalizada e imutável de origens permitidas."""

    allowed_origins: tuple[str, ...]


def _configuration_error() -> CorsConfigurationError:
    return CorsConfigurationError(
        f"A variável de ambiente {CORS_ALLOWED_ORIGINS_ENV_VAR} deve conter "
        "somente origens HTTP ou HTTPS explícitas, separadas por vírgula."
    )


def _normalize_origin(raw_origin: str) -> str:
    candidate = raw_origin.strip()
    if not candidate or not _ORIGIN_PATTERN.fullmatch(candidate):
        raise _configuration_error()

    parsed = urlsplit(candidate)
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise _configuration_error()

    try:
        port = parsed.port
    except ValueError:
        raise _configuration_error() from None

    if port is not None and not 1 <= port <= 65535:
        raise _configuration_error()

    scheme = parsed.scheme.lower()
    hostname = parsed.hostname.lower()
    if ":" in hostname:
        hostname = f"[{hostname}]"

    if port in {80 if scheme == "http" else 443, None}:
        return f"{scheme}://{hostname}"
    return f"{scheme}://{hostname}:{port}"


def load_cors_settings(
    environment: Mapping[str, str] | None = None,
) -> CorsSettings:
    """Lê, valida, normaliza e deduplica as origens CORS permitidas."""
    source = os.environ if environment is None else environment
    raw_value = source.get(CORS_ALLOWED_ORIGINS_ENV_VAR)
    if raw_value is None or not raw_value.strip():
        raise _configuration_error()

    raw_origins = raw_value.split(",")
    if any(not origin.strip() for origin in raw_origins):
        raise _configuration_error()

    normalized_origins = tuple(
        dict.fromkeys(_normalize_origin(origin) for origin in raw_origins)
    )
    return CorsSettings(allowed_origins=normalized_origins)


def configure_cors(app, settings: CorsSettings) -> None:
    """Aplica CORS somente aos recursos e métodos do contrato público."""
    origins = list(settings.allowed_origins)
    resources = {
        r"/locais$": {
            "origins": origins,
            "methods": ["GET", "POST", "OPTIONS"],
        },
        r"/locais/[^/]+$": {
            "origins": origins,
            "methods": ["GET", "PUT", "DELETE", "OPTIONS"],
        },
        r"/locais/[^/]+/avaliacoes$": {
            "origins": origins,
            "methods": ["GET", "POST", "OPTIONS"],
        },
        r"/locais/[^/]+/clima$": {
            "origins": origins,
            "methods": ["GET", "OPTIONS"],
        },
        r"/avaliacoes/[0-9]+$": {
            "origins": origins,
            "methods": ["PATCH", "DELETE", "OPTIONS"],
        },
    }
    CORS(
        app,
        resources=resources,
        allow_headers=["Content-Type"],
        expose_headers=["X-Request-ID"],
        supports_credentials=False,
        always_send=False,
        send_wildcard=False,
        vary_header=True,
    )
