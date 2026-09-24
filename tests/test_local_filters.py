import os
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:5173")

from app import app  # noqa: E402
from models.base import Base  # noqa: E402
from models.local_turistico import LocalTuristico  # noqa: E402
from scripts.seed import load_local_seed_data  # noqa: E402
from scripts.seed import seed_locations  # noqa: E402
from services import local_service  # noqa: E402


class LocalFiltersTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

        with self.session_factory.begin() as session:
            seed_locations(session, load_local_seed_data())
            local = (
                session.query(LocalTuristico)
                .filter(LocalTuristico.slug == "museu-de-arte-moderna")
                .one()
            )
            local.destaque = False

    def tearDown(self):
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def get(self, query_string):
        with patch(
            "services.local_service.SessionLocal",
            self.session_factory,
        ):
            return app.test_client().get(
                "/locais",
                query_string=query_string,
            )

    def test_city_and_category_are_normalized_and_combined_with_and(self):
        response = self.get(
            {
                "cidade": "rio de janeiro",
                "categoria": "PRAIAS",
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {local["slug"] for local in response.get_json()["locais"]},
            {"arpoador", "praia-de-sao-conrado"},
        )

    def test_city_category_and_featured_filters_work_individually(self):
        cases = (
            ({"cidade": "rio de janeiro"}, 6),
            ({"categoria": "PRAIAS"}, 2),
            ({"destaque": "true"}, 5),
        )

        for query, expected_count in cases:
            with self.subTest(query=query):
                response = self.get(query)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    len(response.get_json()["locais"]),
                    expected_count,
                )

    def test_featured_false_is_applied_instead_of_ignored(self):
        response = self.get({"destaque": "false"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [local["slug"] for local in response.get_json()["locais"]],
            ["museu-de-arte-moderna"],
        )

    def test_all_filters_are_combined_with_and(self):
        response = self.get(
            {
                "cidade": "RIO DE JANEIRO",
                "categoria": "museus",
                "destaque": "false",
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [local["slug"] for local in response.get_json()["locais"]],
            ["museu-de-arte-moderna"],
        )

    def test_valid_filter_without_match_returns_empty_collection(self):
        response = self.get({"cidade": "Teresópolis"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["locais"], [])

    def test_invalid_query_parameters_return_canonical_bad_request(self):
        cases = (
            ({"campo_extra": "valor"}, "campo_extra"),
            ({"destaque": "1"}, "destaque"),
            ({"pagina": "texto"}, "pagina"),
            ({"pagina": "0"}, "pagina"),
            ({"por_pagina": "101"}, "por_pagina"),
            ({"ordenar_por": "recentes"}, "ordenar_por"),
        )

        for query, expected_field in cases:
            with self.subTest(query=query):
                response = self.get(query)

                self.assertEqual(response.status_code, 400)
                error = response.get_json()["erro"]
                self.assertEqual(error["codigo"], "requisicao_invalida")
                self.assertTrue(
                    any(
                        detail["campo"] == expected_field
                        for detail in error["detalhes"]
                    ),
                    error["detalhes"],
                )

    def test_service_uses_exact_comparisons_without_partial_search(self):
        with patch(
            "services.local_service.SessionLocal",
            self.session_factory,
        ):
            by_city, _, _ = local_service.listar_locais(cidade="Rio")
            by_category, _, _ = local_service.listar_locais(categoria="praia")

        self.assertEqual(by_city, [])
        self.assertEqual(by_category, [])


if __name__ == "__main__":
    unittest.main()
