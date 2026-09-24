import os
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:5173")

from app import app  # noqa: E402
from models.base import Base  # noqa: E402
from scripts.seed import load_evaluation_seed_data  # noqa: E402
from scripts.seed import load_local_seed_data  # noqa: E402
from scripts.seed import seed_evaluations  # noqa: E402
from scripts.seed import seed_locations  # noqa: E402


class LocalDetailTestCase(unittest.TestCase):
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

    def get(self, slug):
        with patch(
            "services.local_service.SessionLocal",
            self.session_factory,
        ):
            return app.test_client().get(f"/locais/{slug}")

    def test_detail_by_slug_returns_the_fourteen_canonical_fields(self):
        response = self.get("arpoador")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(
            set(payload),
            {
                "id",
                "slug",
                "nome",
                "categoria",
                "descricao",
                "cidade",
                "bairro",
                "regiao",
                "imagem",
                "destaque",
                "latitude",
                "longitude",
                "nota_media",
                "total_avaliacoes",
            },
        )
        self.assertEqual(payload["slug"], "arpoador")
        self.assertEqual(payload["nota_media"], 4.5)
        self.assertEqual(payload["total_avaliacoes"], 2)
        self.assertNotIn("locais", payload)
        self.assertNotIn("paginacao", payload)
        self.assertNotIn("avaliacoes", payload)

    def test_detail_without_evaluations_returns_null_average_and_zero_count(
        self,
    ):
        response = self.get("museu-de-arte-moderna")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get_json()["nota_media"])
        self.assertEqual(response.get_json()["total_avaliacoes"], 0)

    def test_malformed_slug_returns_canonical_bad_request(self):
        for slug in ("Arpoador", "arpoador--rio"):
            with self.subTest(slug=slug):
                response = self.get(slug)
                payload = response.get_json()

                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    payload["erro"]["codigo"],
                    "requisicao_invalida",
                )
                self.assertEqual(
                    payload["erro"]["detalhes"][0]["campo"],
                    "slug",
                )

    def test_unknown_canonical_slug_returns_correlated_not_found(self):
        response = self.get("local-inexistente")
        payload = response.get_json()

        self.assertEqual(response.status_code, 404)
        self.assertEqual(payload["erro"]["codigo"], "local_nao_encontrado")
        self.assertEqual(payload["erro"]["detalhes"], [])
        self.assertEqual(
            payload["erro"]["requisicao_id"],
            response.headers["X-Request-ID"],
        )

    def test_get_route_exposes_slug_and_not_the_legacy_id_parameter(self):
        get_rules = {
            rule.rule for rule in app.url_map.iter_rules() if "GET" in rule.methods
        }

        self.assertIn("/locais/<slug>", get_rules)
        self.assertNotIn("/locais/<int:local_id>", get_rules)

    def test_detail_uses_one_aggregate_select_without_loading_evaluations(
        self,
    ):
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
        self.assertEqual(len(selects), 1)


if __name__ == "__main__":
    unittest.main()
