import os
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:5173")

from models.avaliacao import Avaliacao  # noqa: E402
from models.base import Base  # noqa: E402
from models.local_turistico import LocalTuristico  # noqa: E402
from scripts import seed  # noqa: E402


class ControlledSeedFailure(RuntimeError):
    """Representa a falha injetada depois do flush transacional."""


class SeedTransactionTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

    def tearDown(self):
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    @staticmethod
    def normalize_value(value):
        """Normaliza tipos do banco para comparação determinística."""
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc).isoformat()
        return value

    def snapshot(self):
        """Captura contagens e conteúdo persistido em ordem estável."""
        with self.session_factory() as session:
            locations = session.execute(
                select(
                    LocalTuristico.id,
                    LocalTuristico.slug,
                    LocalTuristico.nome,
                    LocalTuristico.categoria,
                    LocalTuristico.descricao,
                    LocalTuristico.cidade,
                    LocalTuristico.bairro,
                    LocalTuristico.regiao,
                    LocalTuristico.imagem,
                    LocalTuristico.destaque,
                    LocalTuristico.latitude,
                    LocalTuristico.longitude,
                ).order_by(LocalTuristico.slug)
            ).all()
            evaluations = session.execute(
                select(
                    Avaliacao.id,
                    LocalTuristico.slug,
                    Avaliacao.autor,
                    Avaliacao.nota,
                    Avaliacao.comentario,
                    Avaliacao.criado_em,
                    Avaliacao.local_id,
                )
                .join(
                    LocalTuristico,
                    Avaliacao.local_id == LocalTuristico.id,
                )
                .order_by(
                    LocalTuristico.slug,
                    Avaliacao.autor,
                    Avaliacao.criado_em,
                )
            ).all()

        return {
            "contagens": {
                "locais": len(locations),
                "avaliacoes": len(evaluations),
            },
            "locais": tuple(
                tuple(self.normalize_value(value) for value in row) for row in locations
            ),
            "avaliacoes": tuple(
                tuple(self.normalize_value(value) for value in row)
                for row in evaluations
            ),
        }

    def test_second_run_preserves_counts_and_complete_content(self):
        with patch("scripts.seed.SessionLocal", self.session_factory):
            first_result = seed.run_seed()
            first_snapshot = self.snapshot()
            second_result = seed.run_seed()
            second_snapshot = self.snapshot()

        self.assertEqual(first_snapshot["contagens"], {"locais": 6, "avaliacoes": 6})
        self.assertEqual(first_snapshot, second_snapshot)
        self.assertEqual(
            seed.build_seed_report(first_result)["totais"],
            {
                "inseridos": 12,
                "atualizados": 0,
                "ignorados": 0,
                "rejeitados": 5,
            },
        )
        self.assertEqual(
            seed.build_seed_report(second_result)["totais"],
            {
                "inseridos": 0,
                "atualizados": 0,
                "ignorados": 12,
                "rejeitados": 5,
            },
        )

    def test_failure_after_flush_rolls_back_every_seed_change(self):
        existing = seed.load_local_seed_data()[0]
        with self.session_factory.begin() as session:
            session.add(
                LocalTuristico(
                    slug=existing.slug,
                    nome="Nome anterior",
                    categoria=existing.categoria,
                    descricao=existing.descricao,
                    cidade=existing.cidade,
                    bairro=existing.bairro,
                    regiao=existing.regiao,
                    imagem=existing.imagem,
                    destaque=False,
                    latitude=existing.latitude,
                    longitude=existing.longitude,
                )
            )
        before = self.snapshot()
        original_seed_evaluations = seed.seed_evaluations

        def fail_after_flush(session, records):
            original_seed_evaluations(session, records)
            session.flush()
            raise ControlledSeedFailure("falha_controlada_apos_flush")

        with patch("scripts.seed.SessionLocal", self.session_factory), patch(
            "scripts.seed.seed_evaluations",
            side_effect=fail_after_flush,
        ):
            with self.assertRaisesRegex(
                ControlledSeedFailure,
                "falha_controlada_apos_flush",
            ):
                seed.run_seed()

        after = self.snapshot()
        self.assertEqual(after, before)
        self.assertEqual(after["contagens"], {"locais": 1, "avaliacoes": 0})
        self.assertEqual(after["locais"][0][2], "Nome anterior")


if __name__ == "__main__":
    unittest.main()
