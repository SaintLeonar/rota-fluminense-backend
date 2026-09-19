import os
import subprocess
import sys
import textwrap
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from threading import Barrier, Event, Lock

from services import open_meteo_cache, open_meteo_transformer

CacheOpenMeteo = open_meteo_cache.CacheOpenMeteo
MAX_CACHE_ENTRIES = open_meteo_cache.MAX_CACHE_ENTRIES
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ControlledClock:
    def __init__(self):
        self.monotonic_value = 100.0
        self.utc_value = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)

    def monotonic(self):
        return self.monotonic_value

    def utc(self):
        return self.utc_value

    def advance(self, seconds):
        self.monotonic_value += seconds
        self.utc_value += timedelta(seconds=seconds)


def weather_result(marker=0.0):
    current = open_meteo_transformer.ClimaAtualOpenMeteo(
        observado_em=datetime(
            2026,
            9,
            17,
            9,
            tzinfo=timezone(timedelta(hours=-3)),
        ),
        temperatura_c=24.0 + marker,
        sensacao_termica_c=24.5 + marker,
        precipitacao_mm=0.0,
        velocidade_vento_kmh=10.0,
        codigo_meteorologico=1,
        descricao="Predominantemente limpo",
        icone="predominantemente_limpo",
    )
    forecast = tuple(
        open_meteo_transformer.PrevisaoDiariaOpenMeteo(
            data=date(2026, 9, 17 + index),
            temperatura_max_c=27.0 + marker + index,
            temperatura_min_c=19.0 + marker + index,
            probabilidade_precipitacao_max_pct=10.0 + index,
            codigo_meteorologico=1,
            descricao="Predominantemente limpo",
            icone="predominantemente_limpo",
        )
        for index in range(3)
    )
    return open_meteo_transformer.ResultadoOpenMeteo(
        timezone="America/Sao_Paulo",
        atual=current,
        previsao=forecast,
    )


class OpenMeteoCacheTestCase(unittest.TestCase):
    def setUp(self):
        self.clock = ControlledClock()
        self.cache = CacheOpenMeteo(
            10,
            monotonic_clock=self.clock.monotonic,
            utc_clock=self.clock.utc,
        )

    def test_empty_fill_and_hit_preserve_metadata_and_flags(self):
        calls = 0

        def loader():
            nonlocal calls
            calls += 1
            return weather_result()

        self.assertIsNone(self.cache.obter("arpoador", -22.9, -43.2))

        fresh = self.cache.obter_ou_carregar(
            "arpoador",
            -22.9,
            -43.2,
            loader,
        )
        cached = self.cache.obter_ou_carregar(
            "arpoador",
            -22.9,
            -43.2,
            loader,
        )

        self.assertEqual(calls, 1)
        self.assertFalse(fresh.utilizado)
        self.assertTrue(cached.utilizado)
        self.assertEqual(fresh.dados, cached.dados)
        self.assertEqual(fresh.atualizado_em, self.clock.utc_value)
        self.assertEqual(
            fresh.expira_em,
            self.clock.utc_value + timedelta(seconds=10),
        )
        self.assertEqual(cached.atualizado_em, fresh.atualizado_em)
        self.assertEqual(cached.expira_em, fresh.expira_em)

    def test_entry_is_valid_only_before_monotonic_deadline(self):
        self.cache.armazenar("arpoador", -22.9, -43.2, weather_result())

        self.clock.advance(9.999)
        self.assertIsNotNone(self.cache.obter("arpoador", -22.9, -43.2))

        self.clock.advance(0.001)
        self.assertIsNone(self.cache.obter("arpoador", -22.9, -43.2))
        self.assertEqual(len(self.cache), 0)

    def test_expired_entry_is_renewed_with_new_timestamps(self):
        original = self.cache.armazenar(
            "arpoador",
            -22.9,
            -43.2,
            weather_result(),
        )
        self.clock.advance(10)

        renewed = self.cache.obter_ou_carregar(
            "arpoador",
            -22.9,
            -43.2,
            lambda: weather_result(1.0),
        )

        self.assertFalse(renewed.utilizado)
        self.assertEqual(renewed.dados.atual.temperatura_c, 25.0)
        self.assertGreater(renewed.atualizado_em, original.atualizado_em)
        self.assertGreater(renewed.expira_em, original.expira_em)

    def test_failure_after_expiration_never_returns_stale_or_negative_cache(
        self,
    ):
        self.cache.armazenar("arpoador", -22.9, -43.2, weather_result())
        self.clock.advance(10)

        def failing_loader():
            raise RuntimeError("provedor indisponível")

        with self.assertRaises(RuntimeError):
            self.cache.obter_ou_carregar(
                "arpoador",
                -22.9,
                -43.2,
                failing_loader,
            )

        self.assertIsNone(self.cache.obter("arpoador", -22.9, -43.2))
        recovered = self.cache.obter_ou_carregar(
            "arpoador",
            -22.9,
            -43.2,
            lambda: weather_result(2.0),
        )
        self.assertFalse(recovered.utilizado)
        self.assertEqual(recovered.dados.atual.temperatura_c, 26.0)

    def test_coordinates_are_canonicalized_to_six_decimal_places(self):
        self.cache.armazenar(
            "arpoador",
            Decimal("-22.9068004"),
            Decimal("-43.1729004"),
            weather_result(),
        )

        cached = self.cache.obter(
            "arpoador",
            Decimal("-22.906800"),
            Decimal("-43.172900"),
        )

        self.assertIsNotNone(cached)
        self.assertTrue(cached.utilizado)

    def test_new_coordinates_invalidate_previous_position_for_same_slug(self):
        self.cache.armazenar("arpoador", -22.9, -43.2, weather_result())
        self.cache.armazenar("arpoador", -23.0, -43.3, weather_result(1.0))

        self.assertIsNone(self.cache.obter("arpoador", -22.9, -43.2))
        current = self.cache.obter("arpoador", -23.0, -43.3)
        self.assertIsNotNone(current)
        self.assertEqual(current.dados.atual.temperatura_c, 25.0)

    def test_different_slugs_remain_isolated(self):
        self.cache.armazenar("arpoador", -22.9, -43.2, weather_result())
        self.cache.armazenar("parque-lage", -22.9, -43.2, weather_result(3.0))

        first = self.cache.obter("arpoador", -22.9, -43.2)
        second = self.cache.obter("parque-lage", -22.9, -43.2)

        self.assertEqual(first.dados.atual.temperatura_c, 24.0)
        self.assertEqual(second.dados.atual.temperatura_c, 27.0)

    def test_lru_limit_evicts_least_recently_used_valid_entry(self):
        for index in range(MAX_CACHE_ENTRIES):
            self.cache.armazenar(
                f"local-{index}",
                -22.0,
                -43.0,
                weather_result(float(index)),
            )

        self.assertIsNotNone(self.cache.obter("local-0", -22.0, -43.0))
        self.cache.armazenar(
            "local-novo",
            -22.0,
            -43.0,
            weather_result(999.0),
        )

        self.assertEqual(len(self.cache), MAX_CACHE_ENTRIES)
        self.assertIsNone(self.cache.obter("local-1", -22.0, -43.0))
        self.assertIsNotNone(self.cache.obter("local-0", -22.0, -43.0))
        self.assertIsNotNone(self.cache.obter("local-novo", -22.0, -43.0))

    def test_cache_uses_defensive_copies_on_write_and_read(self):
        source = weather_result()
        stored = self.cache.armazenar("arpoador", -22.9, -43.2, source)

        self.assertIsNot(stored.dados, source)
        self.assertIsNot(stored.dados.atual, source.atual)
        self.assertIsNot(stored.dados.previsao, source.previsao)

        object.__setattr__(source.atual, "temperatura_c", 99.0)
        object.__setattr__(stored.dados.atual, "temperatura_c", 88.0)
        cached = self.cache.obter("arpoador", -22.9, -43.2)

        self.assertEqual(cached.dados.atual.temperatura_c, 24.0)
        self.assertIsNot(cached.dados, stored.dados)

    def test_rejects_invalid_configuration_keys_clocks_and_content(self):
        for ttl in (0, -1, True, 1.5):
            with self.subTest(ttl=ttl):
                with self.assertRaises(ValueError):
                    CacheOpenMeteo(ttl)

        invalid_keys = (
            ("", -22.9, -43.2),
            (None, -22.9, -43.2),
            ("arpoador", True, -43.2),
            ("arpoador", float("nan"), -43.2),
            ("arpoador", -22.9, "-43.2"),
        )
        for slug, latitude, longitude in invalid_keys:
            with self.subTest(
                slug=slug,
                latitude=latitude,
                longitude=longitude,
            ):
                with self.assertRaises((TypeError, ValueError)):
                    self.cache.obter(slug, latitude, longitude)

        naive_cache = CacheOpenMeteo(
            10,
            monotonic_clock=self.clock.monotonic,
            utc_clock=lambda: datetime(2026, 9, 17, 12),
        )
        with self.assertRaises(ValueError):
            naive_cache.armazenar("arpoador", -22.9, -43.2, weather_result())

        with self.assertRaises(TypeError):
            self.cache.obter_ou_carregar(
                "arpoador",
                -22.9,
                -43.2,
                lambda: object(),
            )
        self.assertEqual(len(self.cache), 0)

    def test_same_key_uses_single_flight_and_double_check(self):
        worker_count = 8
        start = Barrier(worker_count)
        loader_started = Event()
        release_loader = Event()
        calls_lock = Lock()
        calls = 0

        def loader():
            nonlocal calls
            with calls_lock:
                calls += 1
            loader_started.set()
            if not release_loader.wait(5):
                raise TimeoutError("teste de single-flight excedeu o limite")
            return weather_result()

        def worker():
            start.wait(5)
            return self.cache.obter_ou_carregar(
                "arpoador",
                -22.9,
                -43.2,
                loader,
            )

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [executor.submit(worker) for _ in range(worker_count)]
            self.assertTrue(loader_started.wait(5))
            release_loader.set()
            results = [future.result(timeout=5) for future in futures]

        self.assertEqual(calls, 1)
        self.assertEqual(
            sum(not result.utilizado for result in results),
            1,
        )
        self.assertEqual(
            sum(result.utilizado for result in results),
            worker_count - 1,
        )

    def test_different_keys_can_load_in_parallel(self):
        loaders_meet = Barrier(2)

        def loader(marker):
            loaders_meet.wait(5)
            return weather_result(marker)

        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(
                self.cache.obter_ou_carregar,
                "arpoador",
                -22.9,
                -43.2,
                lambda: loader(1.0),
            )
            second = executor.submit(
                self.cache.obter_ou_carregar,
                "parque-lage",
                -22.96,
                -43.21,
                lambda: loader(2.0),
            )
            results = (first.result(timeout=5), second.result(timeout=5))

        self.assertTrue(all(not result.utilizado for result in results))
        self.assertEqual(
            {result.dados.atual.temperatura_c for result in results},
            {25.0, 26.0},
        )

    def test_application_exposes_process_shared_cache(self):
        environment = os.environ.copy()
        environment["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
        environment["OPEN_METEO_TIMEOUT_SECONDS"] = "5"
        environment["OPEN_METEO_CACHE_TTL_SECONDS"] = "1800"
        environment["PYTHONUTF8"] = "1"
        code = """
            from app import app
            from services.open_meteo_cache import OPEN_METEO_CACHE

            assert app.config["OPEN_METEO_CACHE"] is OPEN_METEO_CACHE
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
