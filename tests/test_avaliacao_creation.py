import os
import unittest
from datetime import datetime, timezone
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


class AvaliacaoCreationTestCase(unittest.TestCase):
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

    def post(self, slug, payload):
        with patch(
            "services.avaliacao_service.SessionLocal",
            self.session_factory,
        ):
            return app.test_client().post(
                f"/locais/{slug}/avaliacoes",
                json=payload,
            )

    def evaluation_count(self):
        with self.session_factory() as session:
            return session.query(Avaliacao).count()

    def valid_payload(self):
        return {
            "autor": "Marina Nova",
            "nota": 5,
            "comentario": "Excelente passeio.",
        }

    def test_creation_returns_canonical_fields_and_persists_route_link(self):
        before = datetime.now(timezone.utc)
        response = self.post(
            "parque-lage",
            {
                "autor": "  Marina Nova  ",
                "nota": 5,
                "comentario": "  Excelente passeio.  ",
            },
        )
        after = datetime.now(timezone.utc)

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertEqual(
            set(payload),
            {
                "id",
                "local_id",
                "autor",
                "nota",
                "comentario",
                "criado_em",
            },
        )
        self.assertEqual(payload["autor"], "Marina Nova")
        self.assertEqual(payload["nota"], 5)
        self.assertEqual(payload["comentario"], "Excelente passeio.")
        self.assertTrue(payload["criado_em"].endswith("Z"))

        created_at = datetime.fromisoformat(payload["criado_em"].replace("Z", "+00:00"))
        self.assertLessEqual(before, created_at)
        self.assertLessEqual(created_at, after)

        with self.session_factory() as session:
            avaliacao = session.get(Avaliacao, payload["id"])
            local = session.get(LocalTuristico, payload["local_id"])

            self.assertIsNotNone(avaliacao)
            self.assertEqual(local.slug, "parque-lage")
            self.assertEqual(avaliacao.autor, "Marina Nova")
            self.assertEqual(avaliacao.nota, 5)
            self.assertEqual(avaliacao.comentario, "Excelente passeio.")

    def test_omitted_comment_is_returned_and_persisted_as_null(self):
        response = self.post(
            "museu-de-arte-moderna",
            {
                "autor": "Rita Alves",
                "nota": 4,
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertIsNone(payload["comentario"])

        with self.session_factory() as session:
            avaliacao = session.get(Avaliacao, payload["id"])
            self.assertIsNone(avaliacao.comentario)

    def test_creation_accepts_both_note_boundaries(self):
        for note in (1, 5):
            with self.subTest(note=note):
                response = self.post(
                    "museu-de-arte-moderna",
                    {
                        "autor": f"Visitante nota {note}",
                        "nota": note,
                    },
                )

                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.get_json()["nota"], note)

        self.assertEqual(self.evaluation_count(), 8)

    def test_creation_validates_required_fields_and_domain_limits(self):
        cases = (
            ({"nota": 5}, "autor"),
            ({"autor": "   ", "nota": 5}, "autor"),
            ({"autor": "Marina Nova"}, "nota"),
            ({"autor": "Marina Nova", "nota": True}, "nota"),
            ({"autor": "Marina Nova", "nota": 4.5}, "nota"),
            ({"autor": "Marina Nova", "nota": "5"}, "nota"),
            ({"autor": "Marina Nova", "nota": 0}, "nota"),
            ({"autor": "Marina Nova", "nota": 6}, "nota"),
            (
                {
                    "autor": "Marina Nova",
                    "nota": 5,
                    "comentario": "   ",
                },
                "comentario",
            ),
            (
                {
                    "autor": "Marina Nova",
                    "nota": 5,
                    "comentario": "x" * 1001,
                },
                "comentario",
            ),
        )

        for payload, field in cases:
            with self.subTest(payload=payload):
                response = self.post("arpoador", payload)

                self.assertEqual(response.status_code, 400)
                error = response.get_json()["erro"]
                self.assertEqual(error["codigo"], "requisicao_invalida")
                self.assertEqual(error["detalhes"][0]["campo"], field)
                self.assertEqual(self.evaluation_count(), 6)

    def test_creation_rejects_read_only_legacy_and_unknown_fields(self):
        for field, value in (
            ("id", 99),
            ("local_id", 6),
            ("criado_em", "2026-09-15T12:00:00Z"),
            ("nome_usuario", "Nome legado"),
            ("campo_desconhecido", "valor"),
        ):
            with self.subTest(field=field):
                payload = self.valid_payload()
                payload[field] = value
                response = self.post("arpoador", payload)

                self.assertEqual(response.status_code, 400)
                details = response.get_json()["erro"]["detalhes"]
                self.assertEqual(details[0]["campo"], field)
                self.assertEqual(
                    details[0]["codigo"],
                    "campo_nao_permitido",
                )
                self.assertEqual(self.evaluation_count(), 6)

    def test_malformed_and_unknown_slugs_do_not_create_evaluations(self):
        malformed = self.post("Arpoador", self.valid_payload())
        unknown = self.post("local-inexistente", self.valid_payload())

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
        self.assertEqual(
            unknown.get_json()["erro"]["requisicao_id"],
            unknown.headers["X-Request-ID"],
        )
        self.assertEqual(self.evaluation_count(), 6)

    def test_post_route_and_openapi_use_slug_without_legacy_id(self):
        post_rules = {
            rule.rule
            for rule in app.url_map.iter_rules()
            if "POST" in rule.methods and rule.rule.endswith("/avaliacoes")
        }
        self.assertIn("/locais/<slug>/avaliacoes", post_rules)
        self.assertNotIn("/locais/<int:local_id>/avaliacoes", post_rules)

        openapi = app.test_client().get("/openapi/openapi.json").get_json()
        operation = openapi["paths"]["/locais/{slug}/avaliacoes"]["post"]
        self.assertTrue({"201", "400", "404", "500"}.issubset(operation["responses"]))
        self.assertEqual(operation["parameters"][0]["name"], "slug")


if __name__ == "__main__":
    unittest.main()
