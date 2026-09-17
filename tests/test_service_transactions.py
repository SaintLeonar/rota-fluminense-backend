import os
import unittest
from collections.abc import Mapping
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from models.avaliacao import Avaliacao  # noqa: E402
from models.base import Base  # noqa: E402
from models.local_turistico import LocalTuristico  # noqa: E402
from scripts.seed import load_evaluation_seed_data  # noqa: E402
from scripts.seed import load_local_seed_data  # noqa: E402
from scripts.seed import seed_evaluations  # noqa: E402
from scripts.seed import seed_locations  # noqa: E402
from services import avaliacao_service, local_service  # noqa: E402
from services.session_manager import gerenciar_sessao  # noqa: E402
from utils.serializers import serializar_local  # noqa: E402


def build_local_data():
    return {
        "slug": "jardim-botanico",
        "nome": "Jardim Botânico",
        "categoria": "parques",
        "descricao": "Área verde histórica com coleções botânicas.",
        "cidade": "Rio de Janeiro",
        "bairro": "Jardim Botânico",
        "regiao": "Zona Sul",
        "imagem": "/imagens/locais/jardim-botanico.jpg",
        "destaque": False,
        "latitude": -22.9688,
        "longitude": -43.2245,
    }


def build_local_update():
    data = build_local_data()
    data.pop("slug")
    return data


class SessionManagerTestCase(unittest.TestCase):
    def test_success_closes_session_without_explicit_rollback(self):
        session = MagicMock()
        factory = MagicMock(return_value=session)

        with gerenciar_sessao(factory) as managed:
            self.assertIs(managed, session)

        factory.assert_called_once_with()
        session.rollback.assert_not_called()
        session.close.assert_called_once_with()

    def test_failure_rolls_back_closes_and_preserves_exception(self):
        session = MagicMock()
        factory = MagicMock(return_value=session)

        with self.assertRaisesRegex(RuntimeError, "falha controlada"):
            with gerenciar_sessao(factory):
                raise RuntimeError("falha controlada")

        session.rollback.assert_called_once_with()
        session.close.assert_called_once_with()


class ServiceTransactionTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

        with self.session_factory.begin() as session:
            seed_locations(session, load_local_seed_data())
            seed_evaluations(session, load_evaluation_seed_data())

    def tearDown(self):
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def arpoador_name(self):
        with self.session_factory() as session:
            return (
                session.query(LocalTuristico.nome)
                .filter(LocalTuristico.slug == "arpoador")
                .scalar()
            )

    def evaluation_count(self):
        with self.session_factory() as session:
            return session.query(Avaliacao).count()

    def test_local_creation_returns_materialized_mapping_after_close(self):
        session = self.session_factory()

        with (
            patch(
                "services.local_service.SessionLocal",
                return_value=session,
            ),
            patch.object(
                session,
                "close",
                wraps=session.close,
            ) as close,
        ):
            created = local_service.criar_local(build_local_data())

        close.assert_called_once_with()
        self.assertIsInstance(created, Mapping)
        self.assertEqual(created["slug"], "jardim-botanico")
        self.assertIsNone(created["nota_media"])
        self.assertEqual(created["total_avaliacoes"], 0)
        self.assertEqual(
            serializar_local(created)["slug"],
            "jardim-botanico",
        )

    def test_local_update_failure_rolls_back_and_preserves_record(self):
        session = self.session_factory()

        def fail_after_flush():
            session.flush()
            raise RuntimeError("falha controlada")

        with (
            patch(
                "services.local_service.SessionLocal",
                return_value=session,
            ),
            patch.object(
                session,
                "commit",
                side_effect=fail_after_flush,
            ),
            patch.object(
                session,
                "rollback",
                wraps=session.rollback,
            ) as rollback,
            patch.object(
                session,
                "close",
                wraps=session.close,
            ) as close,
            self.assertRaises(RuntimeError),
        ):
            local_service.atualizar_local(
                "arpoador",
                build_local_update(),
            )

        rollback.assert_called_once_with()
        close.assert_called_once_with()
        self.assertEqual(self.arpoador_name(), "Arpoador")

    def test_local_read_failure_rolls_back_and_closes_session(self):
        session = MagicMock()
        session.query.side_effect = RuntimeError("falha de leitura")

        with (
            patch(
                "services.local_service.SessionLocal",
                return_value=session,
            ),
            self.assertRaisesRegex(RuntimeError, "falha de leitura"),
        ):
            local_service.listar_locais()

        session.rollback.assert_called_once_with()
        session.close.assert_called_once_with()

    def test_evaluation_creation_failure_rolls_back_insert(self):
        session = self.session_factory()

        def fail_after_flush():
            session.flush()
            raise RuntimeError("falha controlada")

        with (
            patch(
                "services.avaliacao_service.SessionLocal",
                return_value=session,
            ),
            patch.object(
                session,
                "commit",
                side_effect=fail_after_flush,
            ),
            patch.object(
                session,
                "rollback",
                wraps=session.rollback,
            ) as rollback,
            patch.object(
                session,
                "close",
                wraps=session.close,
            ) as close,
            self.assertRaises(RuntimeError),
        ):
            avaliacao_service.criar_avaliacao(
                "arpoador",
                {
                    "autor": "Falha controlada",
                    "nota": 3,
                    "comentario": None,
                },
            )

        rollback.assert_called_once_with()
        close.assert_called_once_with()
        self.assertEqual(self.evaluation_count(), 6)


if __name__ == "__main__":
    unittest.main()
