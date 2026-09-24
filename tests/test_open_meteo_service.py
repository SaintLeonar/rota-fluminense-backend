import os
import subprocess
import sys
import textwrap
import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from threading import Event
from unittest.mock import Mock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:5173")

from models.avaliacao import Avaliacao  # noqa: E402,F401
from models.base import Base  # noqa: E402
from models.local_turistico import LocalTuristico  # noqa: E402
from schemas.clima_schema import ClimaResponseSchema  # noqa: E402
from services import open_meteo_service, open_meteo_transformer  # noqa: E402
from services.open_meteo_cache import CacheOpenMeteo  # noqa: E402
from services.open_meteo_client import OpenMeteoClient  # noqa: E402
from utils import exceptions  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ControlledClock:
    def __init__(self):
        self.monotonic_value = 100.0
        self.utc_value = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)

    def monotonic(self):
        return self.monotonic_value

    def utc(self):
        return self.utc_value


def weather_result():
    current = open_meteo_transformer.ClimaAtualOpenMeteo(
        observado_em=datetime(
            2026,
            9,
            17,
            9,
            tzinfo=timezone(timedelta(hours=-3)),
        ),
        temperatura_c=24.0,
        sensacao_termica_c=24.5,
        precipitacao_mm=0.0,
        velocidade_vento_kmh=10.0,
        codigo_meteorologico=1,
        descricao="Predominantemente limpo",
        icone="predominantemente_limpo",
    )
    forecast = tuple(
        open_meteo_transformer.PrevisaoDiariaOpenMeteo(
            data=date(2026, 9, 17 + index),
            temperatura_max_c=27.0 + index,
            temperatura_min_c=19.0 + index,
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


class OpenMeteoServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        with self.session_factory.begin() as session:
            session.add(
                LocalTuristico(
                    slug="arpoador",
                    nome="Arpoador",
                    categoria="praias",
                    descricao="Praia e mirante.",
                    cidade="Rio de Janeiro",
                    bairro="Ipanema",
                    regiao="Zona Sul",
                    imagem="/imagens/locais/arpoador.jpg",
                    destaque=True,
                    latitude=-22.906800,
                    longitude=-43.172900,
                )
            )
        self.clock = ControlledClock()
        self.cache = CacheOpenMeteo(
            1800,
            monotonic_clock=self.clock.monotonic,
            utc_clock=self.clock.utc,
        )
        self.client = Mock(spec=OpenMeteoClient)
        self.client.buscar_previsao.return_value = weather_result()
        self.logger = Mock()
        self.service = open_meteo_service.OpenMeteoService(
            session_factory=self.session_factory,
            client=self.client,
            cache=self.cache,
            monotonic_clock=self.clock.monotonic,
            logger=self.logger,
        )

    def tearDown(self):
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_provider_then_cache_compose_validated_public_contract(self):
        request_id = f"req_{'a' * 32}"

        fresh = self.service.consultar_clima(
            "arpoador",
            requisicao_id=request_id,
        )
        cached = self.service.consultar_clima(
            "arpoador",
            requisicao_id=request_id,
        )

        self.assertIsInstance(fresh, ClimaResponseSchema)
        self.assertFalse(fresh.cache.utilizado)
        self.assertTrue(cached.cache.utilizado)
        self.assertEqual(fresh.local.slug, "arpoador")
        self.assertEqual(fresh.local.nome, "Arpoador")
        self.assertEqual(len(fresh.previsao), 3)
        self.assertEqual(fresh.atualizado_em, cached.atualizado_em)
        self.assertEqual(fresh.cache.expira_em, cached.cache.expira_em)
        self.client.buscar_previsao.assert_called_once_with(
            -22.9068,
            -43.1729,
            requisicao_id=request_id,
        )
        origins = [call.args[2] for call in self.logger.info.call_args_list]
        self.assertEqual(origins, ["provedor", "cache"])
        self.assertNotIn("-22.9068", str(self.logger.mock_calls))
        self.assertNotIn("-43.1729", str(self.logger.mock_calls))

    def test_database_session_is_closed_before_external_loading(self):
        session = self.session_factory()
        closed = Event()
        original_close = session.close

        def close_session():
            original_close()
            closed.set()

        def load_weather(*args, **kwargs):
            self.assertTrue(closed.is_set())
            return weather_result()

        self.client.buscar_previsao.side_effect = load_weather
        service = open_meteo_service.OpenMeteoService(
            session_factory=lambda: session,
            client=self.client,
            cache=self.cache,
            monotonic_clock=self.clock.monotonic,
            logger=self.logger,
        )

        with patch.object(session, "close", side_effect=close_session) as close:
            service.consultar_clima("arpoador")

        close.assert_called_once_with()

    def test_unknown_local_stops_before_cache_and_provider(self):
        with self.assertRaises(exceptions.AppError) as caught:
            self.service.consultar_clima("local-inexistente")

        self.assertEqual(caught.exception.codigo, "local_nao_encontrado")
        self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(len(self.cache), 0)
        self.client.buscar_previsao.assert_not_called()

    def test_invalid_coordinates_stop_before_cache_and_provider(self):
        invalid_positions = (
            (None, -43.1729),
            (float("nan"), -43.1729),
            (90.000001, -43.1729),
            (-22.9068, -180.000001),
            (True, -43.1729),
        )

        for latitude, longitude in invalid_positions:
            with self.subTest(latitude=latitude, longitude=longitude):
                local = open_meteo_service._LocalClimatico(
                    slug="arpoador",
                    nome="Arpoador",
                    latitude=latitude,
                    longitude=longitude,
                )
                with (
                    patch.object(
                        self.service,
                        "_buscar_local",
                        return_value=local,
                    ),
                    self.assertRaises(
                        exceptions.CoordenadasIndisponiveisError
                    ) as caught,
                ):
                    self.service.consultar_clima("arpoador")

                self.assertEqual(
                    caught.exception.codigo,
                    "coordenadas_indisponiveis",
                )
                self.assertEqual(caught.exception.status_code, 503)
                self.assertEqual(caught.exception.detalhes, [])
                self.assertEqual(len(self.cache), 0)
                self.client.buscar_previsao.assert_not_called()

    def test_invalid_provider_result_is_not_cached_and_can_recover(self):
        valid = weather_result()
        invalid_day = replace(
            valid.previsao[0],
            probabilidade_precipitacao_max_pct=101.0,
        )
        invalid = replace(
            valid,
            previsao=(invalid_day, *valid.previsao[1:]),
        )
        self.client.buscar_previsao.side_effect = (invalid, valid)

        with self.assertRaises(exceptions.ClimaIndisponivelError) as caught:
            self.service.consultar_clima("arpoador")

        self.assertEqual(caught.exception.motivo, "resposta_invalida")
        self.assertEqual(len(self.cache), 0)
        recovered = self.service.consultar_clima("arpoador")
        self.assertFalse(recovered.cache.utilizado)
        self.assertEqual(self.client.buscar_previsao.call_count, 2)

    def test_application_exposes_process_shared_service(self):
        environment = os.environ.copy()
        environment["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
        environment["OPEN_METEO_TIMEOUT_SECONDS"] = "5"
        environment["OPEN_METEO_CACHE_TTL_SECONDS"] = "1800"
        environment["PYTHONUTF8"] = "1"
        code = """
            from app import app
            from services.open_meteo_service import OPEN_METEO_SERVICE

            assert app.config["OPEN_METEO_SERVICE"] is OPEN_METEO_SERVICE
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
