import os
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, event
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
from services import local_service  # noqa: E402


class LocalDeletionTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        app.config.update(TESTING=True)

        with self.session_factory.begin() as session:
            seed_locations(session, load_local_seed_data())
            seed_evaluations(session, load_evaluation_seed_data())

    def tearDown(self):
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def delete(self, slug):
        with patch(
            "services.local_service.SessionLocal",
            self.session_factory,
        ):
            return app.test_client().delete(f"/locais/{slug}")

    def database_counts(self):
        with self.session_factory() as session:
            return (
                session.query(LocalTuristico).count(),
                session.query(Avaliacao).count(),
            )

    def test_delete_returns_204_and_database_cascades_without_child_delete(
        self,
    ):
        delete_statements = []

        def register_delete(
            connection,
            cursor,
            statement,
            parameters,
            context,
            executemany,
        ):
            if statement.lstrip().upper().startswith("DELETE"):
                delete_statements.append(statement)

        event.listen(self.engine, "before_cursor_execute", register_delete)
        try:
            response = self.delete("arpoador")
        finally:
            event.remove(
                self.engine,
                "before_cursor_execute",
                register_delete,
            )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.data, b"")
        self.assertEqual(len(delete_statements), 1)
        self.assertIn("DELETE FROM locais_turisticos", delete_statements[0])
        self.assertNotIn("DELETE FROM avaliacoes", delete_statements[0])
        self.assertEqual(self.database_counts(), (5, 4))

    def test_delete_distinguishes_malformed_and_unknown_slug(self):
        malformed = self.delete("Arpoador")
        unknown = self.delete("local-inexistente")

        self.assertEqual(malformed.status_code, 400)
        self.assertEqual(
            malformed.get_json()["erro"]["codigo"],
            "requisicao_invalida",
        )
        self.assertEqual(unknown.status_code, 404)
        self.assertEqual(
            unknown.get_json()["erro"]["codigo"],
            "local_nao_encontrado",
        )
        self.assertEqual(self.database_counts(), (6, 6))

    def test_failed_commit_rolls_back_local_and_cascaded_evaluations(self):
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
            local_service.deletar_local("arpoador")

        rollback.assert_called_once_with()
        close.assert_called_once_with()
        self.assertEqual(self.database_counts(), (6, 6))

    def test_delete_route_and_openapi_use_slug_without_legacy_id(self):
        delete_rules = {
            rule.rule
            for rule in app.url_map.iter_rules()
            if "DELETE" in rule.methods and rule.rule.startswith("/locais/")
        }
        self.assertIn("/locais/<slug>", delete_rules)
        self.assertNotIn("/locais/<int:local_id>", delete_rules)

        openapi = app.test_client().get("/openapi/openapi.json").get_json()
        operation = openapi["paths"]["/locais/{slug}"]["delete"]
        self.assertTrue({"204", "400", "404", "500"}.issubset(operation["responses"]))


if __name__ == "__main__":
    unittest.main()
