import os
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from app import app  # noqa: E402
from models.base import Base  # noqa: E402
from scripts.seed import load_evaluation_seed_data  # noqa: E402
from scripts.seed import load_local_seed_data  # noqa: E402
from scripts.seed import seed_evaluations  # noqa: E402
from scripts.seed import seed_locations  # noqa: E402


class LocalListingTestCase(unittest.TestCase):
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

    def test_get_locais_returns_complete_persisted_data_without_files(self):
        expected_fields = {
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
        }

        with (
            patch("services.local_service.SessionLocal", self.session_factory),
            patch(
                "scripts.seed.load_local_seed_data",
                side_effect=AssertionError("A listagem não deve ler mocks."),
            ),
            patch(
                "scripts.seed.load_evaluation_seed_data",
                side_effect=AssertionError("A listagem não deve ler mocks."),
            ),
        ):
            response = app.test_client().get("/locais")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(len(payload["locais"]), 6)
        self.assertEqual(
            {local["slug"] for local in payload["locais"]},
            {
                "arpoador",
                "parque-lage",
                "museu-do-amanha",
                "vista-chinesa",
                "praia-de-sao-conrado",
                "museu-de-arte-moderna",
            },
        )
        for local in payload["locais"]:
            self.assertEqual(set(local), expected_fields)
            self.assertIsInstance(local["latitude"], float)
            self.assertIsInstance(local["longitude"], float)

        arpoador = next(
            local for local in payload["locais"] if local["slug"] == "arpoador"
        )
        self.assertEqual(arpoador["nota_media"], 4.5)
        self.assertEqual(arpoador["total_avaliacoes"], 2)

        mam = next(
            local
            for local in payload["locais"]
            if local["slug"] == "museu-de-arte-moderna"
        )
        self.assertIsNone(mam["nota_media"])
        self.assertEqual(mam["total_avaliacoes"], 0)


if __name__ == "__main__":
    unittest.main()
