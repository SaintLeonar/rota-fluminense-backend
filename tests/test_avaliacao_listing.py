import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from app import app  # noqa: E402
from models.avaliacao import Avaliacao  # noqa: E402
from models.base import Base  # noqa: E402
from models.local_turistico import LocalTuristico  # noqa: E402
from scripts.seed import load_evaluation_seed_data  # noqa: E402
from scripts.seed import load_local_seed_data  # noqa: E402
from scripts.seed import seed_evaluations  # noqa: E402
from scripts.seed import seed_locations  # noqa: E402


class AvaliacaoListingTestCase(unittest.TestCase):
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

    def get(self, slug):
        with patch(
            "services.avaliacao_service.SessionLocal",
            self.session_factory,
        ):
            return app.test_client().get(f"/locais/{slug}/avaliacoes")

    def test_listing_returns_canonical_fields_in_contract_order(self):
        response = self.get("arpoador")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(set(payload), {"avaliacoes"})
        self.assertEqual(
            [avaliacao["autor"] for avaliacao in payload["avaliacoes"]],
            ["Marina Costa", "Thiago Ramos"],
        )

        for avaliacao in payload["avaliacoes"]:
            self.assertEqual(
                set(avaliacao),
                {
                    "id",
                    "local_id",
                    "autor",
                    "nota",
                    "comentario",
                    "criado_em",
                },
            )
            self.assertTrue(avaliacao["criado_em"].endswith("Z"))
            self.assertNotIn("nome_usuario", avaliacao)

    def test_listing_uses_descending_id_to_break_datetime_ties(self):
        tied_datetime = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
        with self.session_factory.begin() as session:
            local_id = (
                session.query(LocalTuristico.id)
                .filter(LocalTuristico.slug == "arpoador")
                .scalar()
            )
            session.add_all(
                [
                    Avaliacao(
                        autor="Primeira no empate",
                        nota=4,
                        comentario=None,
                        criado_em=tied_datetime,
                        local_id=local_id,
                    ),
                    Avaliacao(
                        autor="Segunda no empate",
                        nota=5,
                        comentario=None,
                        criado_em=tied_datetime,
                        local_id=local_id,
                    ),
                ]
            )

        response = self.get("arpoador")

        self.assertEqual(response.status_code, 200)
        avaliacoes = response.get_json()["avaliacoes"]
        self.assertEqual(
            [avaliacao["autor"] for avaliacao in avaliacoes[:2]],
            ["Segunda no empate", "Primeira no empate"],
        )
        self.assertGreater(avaliacoes[0]["id"], avaliacoes[1]["id"])

    def test_existing_local_without_evaluations_returns_empty_collection(self):
        response = self.get("museu-de-arte-moderna")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"avaliacoes": []})

    def test_malformed_and_unknown_slugs_have_distinct_canonical_errors(self):
        malformed = self.get("Arpoador")
        unknown = self.get("local-inexistente")

        self.assertEqual(malformed.status_code, 400)
        self.assertEqual(
            malformed.get_json()["erro"]["codigo"],
            "requisicao_invalida",
        )
        self.assertEqual(
            malformed.get_json()["erro"]["detalhes"][0]["campo"],
            "slug",
        )
        self.assertEqual(unknown.status_code, 404)
        self.assertEqual(
            unknown.get_json()["erro"]["codigo"],
            "local_nao_encontrado",
        )
        self.assertEqual(
            unknown.get_json()["erro"]["requisicao_id"],
            unknown.headers["X-Request-ID"],
        )

    def test_listing_executes_two_selects_without_loading_relationship(self):
        selects = []

        def register_select(
            connection,
            cursor,
            statement,
            parameters,
            context,
            executemany,
        ):
            if statement.lstrip().upper().startswith("SELECT"):
                selects.append(statement)

        event.listen(self.engine, "before_cursor_execute", register_select)
        try:
            response = self.get("arpoador")
        finally:
            event.remove(
                self.engine,
                "before_cursor_execute",
                register_select,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(selects), 2)
        self.assertIn("FROM avaliacoes", selects[1])

    def test_get_route_and_openapi_use_slug_without_legacy_id(self):
        get_rules = {
            rule.rule
            for rule in app.url_map.iter_rules()
            if "GET" in rule.methods and rule.rule.endswith("/avaliacoes")
        }
        self.assertIn("/locais/<slug>/avaliacoes", get_rules)
        self.assertNotIn("/locais/<int:local_id>/avaliacoes", get_rules)

        openapi = app.test_client().get("/openapi/openapi.json").get_json()
        operation = openapi["paths"]["/locais/{slug}/avaliacoes"]["get"]
        self.assertTrue(
            {"200", "400", "404", "500"}.issubset(operation["responses"])
        )


if __name__ == "__main__":
    unittest.main()
