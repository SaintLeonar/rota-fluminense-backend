import time
from collections import OrderedDict
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from threading import Lock, RLock

from services import open_meteo_transformer
from services.open_meteo_config import OPEN_METEO_SETTINGS

MAX_CACHE_ENTRIES = 256
_COORDINATE_QUANTUM = Decimal("0.000001")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class ResultadoCacheOpenMeteo:
    """Representa dados meteorológicos e metadados transitórios do cache."""

    dados: open_meteo_transformer.ResultadoOpenMeteo
    atualizado_em: datetime
    expira_em: datetime
    utilizado: bool


@dataclass(frozen=True, slots=True)
class _CacheKey:
    slug: str
    latitude: str
    longitude: str


@dataclass(frozen=True, slots=True)
class _CacheEntry:
    dados: open_meteo_transformer.ResultadoOpenMeteo
    atualizado_em: datetime
    expira_em: datetime
    limite_monotonico: float


@dataclass(slots=True)
class _RefreshState:
    lock: Lock = field(default_factory=Lock)
    users: int = 0


def _canonical_coordinate(value: Decimal | float | int) -> str:
    if isinstance(value, bool) or not isinstance(value, (Decimal, float, int)):
        raise TypeError("A coordenada do cache deve ser numérica.")
    try:
        decimal_value = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("A coordenada do cache deve ser finita.") from None
    if not decimal_value.is_finite():
        raise ValueError("A coordenada do cache deve ser finita.")
    try:
        canonical = decimal_value.quantize(
            _COORDINATE_QUANTUM,
            rounding=ROUND_HALF_EVEN,
        )
    except InvalidOperation:
        raise ValueError("A coordenada do cache não pode ser normalizada.") from None
    if canonical == 0:
        canonical = abs(canonical)
    return format(canonical, ".6f")


def _cache_key(
    slug: str,
    latitude: Decimal | float | int,
    longitude: Decimal | float | int,
) -> _CacheKey:
    if not isinstance(slug, str) or not slug:
        raise TypeError("O slug do cache deve ser uma string não vazia.")
    return _CacheKey(
        slug=slug,
        latitude=_canonical_coordinate(latitude),
        longitude=_canonical_coordinate(longitude),
    )


class CacheOpenMeteo:
    """Mantém previsões validadas em cache LRU local e concorrente."""

    def __init__(
        self,
        ttl_seconds: int,
        *,
        monotonic_clock: Callable[[], float] = time.monotonic,
        utc_clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        """Inicializa o cache com TTL e relógios explícitos."""
        if type(ttl_seconds) is not int or ttl_seconds <= 0:
            raise ValueError("O TTL do cache deve ser um inteiro positivo.")
        self._ttl_seconds = ttl_seconds
        self._monotonic_clock = monotonic_clock
        self._utc_clock = utc_clock
        self._entries: OrderedDict[_CacheKey, _CacheEntry] = OrderedDict()
        self._refresh_states: dict[_CacheKey, _RefreshState] = {}
        self._lock = RLock()

    def __len__(self) -> int:
        """Retorna a quantidade física de entradas mantidas no processo."""
        with self._lock:
            return len(self._entries)

    def _remove_expired_locked(self, now_monotonic: float) -> None:
        expired_keys = tuple(
            key
            for key, entry in self._entries.items()
            if now_monotonic >= entry.limite_monotonico
        )
        for key in expired_keys:
            self._entries.pop(key, None)

    def _result_from_entry(
        self,
        entry: _CacheEntry,
        *,
        used: bool,
    ) -> ResultadoCacheOpenMeteo:
        return ResultadoCacheOpenMeteo(
            dados=deepcopy(entry.dados),
            atualizado_em=entry.atualizado_em,
            expira_em=entry.expira_em,
            utilizado=used,
        )

    def _get_by_key(self, key: _CacheKey) -> ResultadoCacheOpenMeteo | None:
        with self._lock:
            now_monotonic = self._monotonic_clock()
            self._remove_expired_locked(now_monotonic)
            entry = self._entries.get(key)
            if entry is None:
                return None
            self._entries.move_to_end(key)
            return self._result_from_entry(entry, used=True)

    def obter(
        self,
        slug: str,
        latitude: Decimal | float | int,
        longitude: Decimal | float | int,
    ) -> ResultadoCacheOpenMeteo | None:
        """Obtém uma cópia válida e atualiza sua recência no LRU."""
        return self._get_by_key(_cache_key(slug, latitude, longitude))

    def _store_by_key(
        self,
        key: _CacheKey,
        data: open_meteo_transformer.ResultadoOpenMeteo,
    ) -> ResultadoCacheOpenMeteo:
        if not isinstance(data, open_meteo_transformer.ResultadoOpenMeteo):
            raise TypeError("O cache aceita somente resultado meteorológico validado.")

        updated_at = self._utc_clock()
        if updated_at.tzinfo is None or updated_at.utcoffset() is None:
            raise ValueError("O relógio UTC do cache deve possuir timezone.")
        updated_at = updated_at.astimezone(timezone.utc)
        expires_at = updated_at + timedelta(seconds=self._ttl_seconds)
        now_monotonic = self._monotonic_clock()
        entry = _CacheEntry(
            dados=deepcopy(data),
            atualizado_em=updated_at,
            expira_em=expires_at,
            limite_monotonico=now_monotonic + self._ttl_seconds,
        )

        with self._lock:
            self._remove_expired_locked(now_monotonic)
            previous_positions = tuple(
                existing_key
                for existing_key in self._entries
                if existing_key.slug == key.slug and existing_key != key
            )
            for previous_key in previous_positions:
                self._entries.pop(previous_key, None)
            self._entries[key] = entry
            self._entries.move_to_end(key)
            while len(self._entries) > MAX_CACHE_ENTRIES:
                self._entries.popitem(last=False)
            return self._result_from_entry(entry, used=False)

    def armazenar(
        self,
        slug: str,
        latitude: Decimal | float | int,
        longitude: Decimal | float | int,
        data: open_meteo_transformer.ResultadoOpenMeteo,
    ) -> ResultadoCacheOpenMeteo:
        """Armazena uma cópia validada e invalida outra posição do slug."""
        return self._store_by_key(
            _cache_key(slug, latitude, longitude),
            data,
        )

    def _enter_refresh(self, key: _CacheKey) -> _RefreshState:
        with self._lock:
            state = self._refresh_states.get(key)
            if state is None:
                state = _RefreshState()
                self._refresh_states[key] = state
            state.users += 1
        state.lock.acquire()
        return state

    def _leave_refresh(self, key: _CacheKey, state: _RefreshState) -> None:
        state.lock.release()
        with self._lock:
            state.users -= 1
            if state.users == 0 and self._refresh_states.get(key) is state:
                self._refresh_states.pop(key, None)

    def obter_ou_carregar(
        self,
        slug: str,
        latitude: Decimal | float | int,
        longitude: Decimal | float | int,
        loader: Callable[[], open_meteo_transformer.ResultadoOpenMeteo],
    ) -> ResultadoCacheOpenMeteo:
        """Obtém entrada válida ou executa uma única renovação por chave."""
        key = _cache_key(slug, latitude, longitude)
        cached = self._get_by_key(key)
        if cached is not None:
            return cached

        state = self._enter_refresh(key)
        try:
            cached = self._get_by_key(key)
            if cached is not None:
                return cached
            return self._store_by_key(key, loader())
        finally:
            self._leave_refresh(key, state)


OPEN_METEO_CACHE = CacheOpenMeteo(OPEN_METEO_SETTINGS.cache_ttl_seconds)
