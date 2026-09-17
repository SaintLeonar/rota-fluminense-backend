import os
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from app import app  # noqa: E402
from models.avaliacao import Avaliacao  # noqa: E402
from models.base import Base  # noqa: E402
from scripts.seed import load_evaluation_seed_data  # noqa: E402
from scripts.seed import load_local_seed_data  # noqa: E402
from scripts.seed import seed_evaluations  # noqa: E402
from scripts.seed import seed_locations  # noqa: E402


class AvaliacaoAggregatesTestCase(unittest.TestCase):
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

    def get_local(self, slug):
        with patch(
            "services.local_service.SessionLocal",
            self.session_factory,
        ):
            return app.test_client().get(f"/locais/{slug}")

    def get_locations(self):
        with patch(
            "services.local_service.SessionLocal",
            self.session_factory,
        ):
            return app.test_client().get("/locais")

    def post_evaluation(self, slug, payload):
        with patch(
            "services.avaliacao_service.SessionLocal",
            self.session_factory,
        ):
            return app.test_client().post(
                f"/locais/{slug}/avaliacoes",
                json=payload,
            )

    def patch_evaluation(self, evaluation_id, payload):
        with patch(
            "services.avaliacao_service.SessionLocal",
            self.session_factory,
        ):
            return app.test_client().patch(
                f"/avaliacoes/{evaluation_id}",
                json=payload,
            )

    def delete_evaluation(self, evaluation_id):
        with patch(
            "services.avaliacao_service.SessionLocal",
            self.session_factory,
        ):
            return app.test_client().delete(
                f"/avaliacoes/{evaluation_id}",
            )

    def evaluation_id(self, author):
        with self.session_factory() as session:
            return (
                session.query(Avaliacao.id)
                .filter(Avaliacao.autor == author)
                .scalar()
            )

    def test_creation_transitions_aggregates_from_zero_to_one(self):
        slug = "museu-de-arte-moderna"
        before = self.get_local(slug).get_json()
        self.assertIsNone(before["nota_media"])
        self.assertEqual(before["total_avaliacoes"], 0)

        created = self.post_evaluation(
            slug,
            {
                "autor": "Nova visitante",
                "nota": 4,
                "comentario": None,
            },
        )
        after = self.get_local(slug).get_json()

        self.assertEqual(created.status_code, 201)
        self.assertEqual(after["nota_media"], 4.0)
        self.assertEqual(after["total_avaliacoes"], 1)

    def test_update_recalculates_average_without_changing_count(self):
        before = self.get_local("arpoador").get_json()
        self.assertEqual(before["nota_media"], 4.5)
        self.assertEqual(before["total_avaliacoes"], 2)

        updated = self.patch_evaluation(
            self.evaluation_id("Marina Costa"),
            {"nota": 1},
        )
        after = self.get_local("arpoador").get_json()

        self.assertEqual(updated.status_code, 200)
        self.assertEqual(after["nota_media"], 2.5)
        self.assertEqual(after["total_avaliacoes"], 2)

    def test_deletion_transitions_aggregates_from_one_to_zero(self):
        before = self.get_local("parque-lage").get_json()
        self.assertEqual(before["nota_media"], 5.0)
        self.assertEqual(before["total_avaliacoes"], 1)

        deleted = self.delete_evaluation(self.evaluation_id("Camila Freitas"))
        after = self.get_local("parque-lage").get_json()

        self.assertEqual(deleted.status_code, 204)
        self.assertIsNone(after["nota_media"])
        self.assertEqual(after["total_avaliacoes"], 0)

    def test_listing_and_detail_reflect_same_rounded_aggregate(self):
        created = self.post_evaluation(
            "arpoador",
            {
                "autor": "Visitante adicional",
                "nota": 1,
                "comentario": "Avaliação para validar a média.",
            },
        )
        detail = self.get_local("arpoador").get_json()
        listing = self.get_locations().get_json()["locais"]
        listed = next(
            local for local in listing if local["slug"] == "arpoador"
        )

        self.assertEqual(created.status_code, 201)
        self.assertEqual(detail["nota_media"], 3.3)
        self.assertEqual(detail["total_avaliacoes"], 3)
        self.assertEqual(listed["nota_media"], 3.3)
        self.assertEqual(listed["total_avaliacoes"], 3)


if __name__ == "__main__":
    unittest.main()
