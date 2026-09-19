"""Orquestra local, cache e provedor para compor a resposta climática."""

import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from pydantic import ValidationError

from models.base import SessionLocal
from models.local_turistico import LocalTuristico
from schemas import clima_schema
from services import open_meteo_transformer
from services.open_meteo_cache import OPEN_METEO_CACHE, CacheOpenMeteo
from services.open_meteo_client import OPEN_METEO_CLIENT, OpenMeteoClient
from services.session_manager import gerenciar_sessao
from utils import exceptions

_LOGGER = logging.getLogger(__name__)
_REQUEST_ID_PATTERN = re.compile(r"req_[0-9a-f]{32}")


@dataclass(frozen=True, slots=True)
class _LocalClimatico:
    slug: str
    nome: str
    latitude: object
    longitude: object


def _safe_request_id(value: str | None) -> str:
    if isinstance(value, str) and _REQUEST_ID_PATTERN.fullmatch(value):
        return value
    return "ausente"


def _normalizar_coordenada(
    value: object,
    *,
    minimum: Decimal,
    maximum: Decimal,
) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise exceptions.CoordenadasIndisponiveisError()
    try:
        coordinate = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise exceptions.CoordenadasIndisponiveisError() from None
    if not coordinate.is_finite() or not minimum <= coordinate <= maximum:
        raise exceptions.CoordenadasIndisponiveisError()
    return coordinate


def _current_payload(
    data: open_meteo_transformer.ResultadoOpenMeteo,
) -> dict[str, object]:
    current = data.atual
    return {
        "observado_em": current.observado_em,
        "temperatura_c": current.temperatura_c,
        "sensacao_termica_c": current.sensacao_termica_c,
        "precipitacao_mm": current.precipitacao_mm,
        "velocidade_vento_kmh": current.velocidade_vento_kmh,
        "codigo_meteorologico": current.codigo_meteorologico,
        "descricao": current.descricao,
        "icone": current.icone,
    }


def _daily_payload(
    item: open_meteo_transformer.PrevisaoDiariaOpenMeteo,
) -> dict[str, object]:
    return {
        "data": item.data,
        "temperatura_max_c": item.temperatura_max_c,
        "temperatura_min_c": item.temperatura_min_c,
        "probabilidade_precipitacao_max_pct": (
            item.probabilidade_precipitacao_max_pct
        ),
        "codigo_meteorologico": item.codigo_meteorologico,
        "descricao": item.descricao,
        "icone": item.icone,
    }


def _validate_provider_data(
    data: open_meteo_transformer.ResultadoOpenMeteo,
) -> None:
    try:
        if not isinstance(data, open_meteo_transformer.ResultadoOpenMeteo):
            raise TypeError("Resultado externo inválido.")
        if data.timezone != clima_schema.OPEN_METEO_TIMEZONE:
            raise ValueError("Timezone externo inválido.")
        daily_payloads = [_daily_payload(item) for item in data.previsao]
        dates = tuple(item["data"] for item in daily_payloads)
        if (
            len(dates) != 3
            or dates != tuple(sorted(dates))
            or len(set(dates)) != len(dates)
        ):
            raise ValueError("Previsão externa inválida.")
        clima_schema.ClimaAtualSchema.model_validate(_current_payload(data))
        for payload in daily_payloads:
            clima_schema.ClimaPrevisaoDiariaSchema.model_validate(payload)
    except (AttributeError, TypeError, ValueError, ValidationError):
        raise exceptions.ClimaIndisponivelError("resposta_invalida") from None


class OpenMeteoService:
    """Coordena persistência, cache e cliente sem sobrepor seus ciclos."""

    def __init__(
        self,
        *,
        session_factory: Callable = SessionLocal,
        client: OpenMeteoClient = OPEN_METEO_CLIENT,
        cache: CacheOpenMeteo = OPEN_METEO_CACHE,
        monotonic_clock: Callable[[], float] = time.monotonic,
        logger: logging.Logger = _LOGGER,
    ) -> None:
        """Inicializa o serviço com dependências substituíveis em testes."""
        self._session_factory = session_factory
        self._client = client
        self._cache = cache
        self._monotonic_clock = monotonic_clock
        self._logger = logger

    def _buscar_local(self, slug: str) -> _LocalClimatico:
        with gerenciar_sessao(self._session_factory) as session:
            row = (
                session.query(
                    LocalTuristico.slug,
                    LocalTuristico.nome,
                    LocalTuristico.latitude,
                    LocalTuristico.longitude,
                )
                .filter(LocalTuristico.slug == slug)
                .one_or_none()
            )
            if row is None:
                raise exceptions.AppError(
                    "local_nao_encontrado",
                    "Local turístico não encontrado.",
                    404,
                )
            return _LocalClimatico(
                slug=row.slug,
                nome=row.nome,
                latitude=row.latitude,
                longitude=row.longitude,
            )

    def consultar_clima(
        self,
        slug: str,
        *,
        requisicao_id: str | None = None,
    ) -> clima_schema.ClimaResponseSchema:
        """Obtém clima validado sem manter sessão durante espera externa."""
        started_at = self._monotonic_clock()
        local = self._buscar_local(slug)
        latitude = _normalizar_coordenada(
            local.latitude,
            minimum=Decimal("-90"),
            maximum=Decimal("90"),
        )
        longitude = _normalizar_coordenada(
            local.longitude,
            minimum=Decimal("-180"),
            maximum=Decimal("180"),
        )

        def load() -> open_meteo_transformer.ResultadoOpenMeteo:
            data = self._client.buscar_previsao(
                float(latitude),
                float(longitude),
                requisicao_id=requisicao_id,
            )
            _validate_provider_data(data)
            return data

        cached = self._cache.obter_ou_carregar(
            local.slug,
            latitude,
            longitude,
            load,
        )
        data = cached.dados
        response = clima_schema.ClimaResponseSchema.model_validate(
            {
                "local": {"slug": local.slug, "nome": local.nome},
                "timezone": data.timezone,
                "atual": _current_payload(data),
                "previsao": [_daily_payload(item) for item in data.previsao],
                "atualizado_em": cached.atualizado_em,
                "cache": {
                    "utilizado": cached.utilizado,
                    "expira_em": cached.expira_em,
                },
            }
        )
        duration = max(0.0, (self._monotonic_clock() - started_at) * 1000)
        origin = "cache" if cached.utilizado else "provedor"
        self._logger.info(
            "Consulta climática requisicao_id=%s origem=%s "
            "resultado=sucesso duracao_ms=%.3f",
            _safe_request_id(requisicao_id),
            origin,
            duration,
        )
        return response


OPEN_METEO_SERVICE = OpenMeteoService()
