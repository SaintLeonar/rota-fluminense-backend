import os
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:5173")

from app import app  # noqa: E402
from models.avaliacao import Avaliacao  # noqa: E402
from models.base import Base  # noqa: E402
from models.local_turistico import LocalTuristico  # noqa: E402
from scripts.seed import load_evaluation_seed_data  # noqa: E402
from scripts.seed import load_local_seed_data  # noqa: E402
from scripts.seed import seed_evaluations  # noqa: E402
from scripts.seed import seed_locations  # noqa: E402
from services import avaliacao_service  # noqa: E402


class AvaliacaoDeletionTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        app.config.update(TESTING=True)

        with self.session_factory.begin() as session:
            seed_locations(session, load_local_seed_data())
            seed_evaluations(session, load_evaluation_seed_data())

    def tearDown(self):
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def delete(self, evaluation_id):
        with patch(
            "services.avaliacao_service.SessionLocal",
            self.session_factory,
        ):
            return app.test_client().delete(
                f"/avaliacoes/{evaluation_id}",
            )

    def evaluation_id(self):
        with self.session_factory() as session:
            return (
                session.query(Avaliacao.id)
                .filter(Avaliacao.autor == "Marina Costa")
                .scalar()
            )

    def database_counts(self):
        with self.session_factory() as session:
            return (
                session.query(LocalTuristico).count(),
                session.query(Avaliacao).count(),
            )

    def test_delete_returns_204_without_body_and_removes_only_evaluation(self):
        evaluation_id = self.evaluation_id()

        response = self.delete(evaluation_id)

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.data, b"")
        self.assertEqual(self.database_counts(), (6, 5))
        with self.session_factory() as session:
            self.assertIsNone(session.get(Avaliacao, evaluation_id))

    def test_unknown_evaluation_returns_correlated_not_found(self):
        response = self.delete(9999)

        self.assertEqual(response.status_code, 404)
        error = response.get_json()["erro"]
        self.assertEqual(error["codigo"], "avaliacao_nao_encontrada")
        self.assertEqual(error["detalhes"], [])
        self.assertEqual(
            error["requisicao_id"],
            response.headers["X-Request-ID"],
        )
        self.assertEqual(self.database_counts(), (6, 6))

    def test_invalid_identifier_returns_bad_request_without_writing(self):
        response = self.delete(0)

        self.assertEqual(response.status_code, 400)
        error = response.get_json()["erro"]
        self.assertEqual(error["codigo"], "requisicao_invalida")
        self.assertEqual(error["detalhes"][0]["campo"], "avaliacao_id")
        self.assertEqual(self.database_counts(), (6, 6))

    def test_failed_commit_rolls_back_and_closes_session(self):
        evaluation_id = self.evaluation_id()
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
            avaliacao_service.deletar_avaliacao(evaluation_id)

        rollback.assert_called_once_with()
        close.assert_called_once_with()
        self.assertEqual(self.database_counts(), (6, 6))

    def test_delete_route_and_openapi_expose_the_canonical_contract(self):
        delete_rules = {
            rule.rule
            for rule in app.url_map.iter_rules()
            if "DELETE" in rule.methods and rule.rule.startswith("/avaliacoes/")
        }
        self.assertEqual(
            delete_rules,
            {"/avaliacoes/<int:avaliacao_id>"},
        )

        openapi = app.test_client().get("/openapi/openapi.json").get_json()
        operation = openapi["paths"]["/avaliacoes/{avaliacao_id}"]["delete"]
        self.assertTrue({"204", "400", "404", "500"}.issubset(operation["responses"]))
        self.assertEqual(
            operation["parameters"][0]["name"],
            "avaliacao_id",
        )


if __name__ == "__main__":
    unittest.main()
