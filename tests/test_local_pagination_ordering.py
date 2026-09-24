import os
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:5173")

from app import app  # noqa: E402
from models.base import Base  # noqa: E402
from models.local_turistico import LocalTuristico  # noqa: E402
from scripts.seed import load_evaluation_seed_data  # noqa: E402
from scripts.seed import load_local_seed_data  # noqa: E402
from scripts.seed import seed_evaluations  # noqa: E402
from scripts.seed import seed_locations  # noqa: E402


class LocalPaginationOrderingTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

        with self.session_factory.begin() as session:
            seed_locations(session, load_local_seed_data())
            seed_evaluations(session, load_evaluation_seed_data())
            session.query(LocalTuristico).filter(LocalTuristico.id.in_((2, 4))).update(
                {LocalTuristico.destaque: False},
                synchronize_session=False,
            )

    def tearDown(self):
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def get(self, query_string=None):
        with patch(
            "services.local_service.SessionLocal",
            self.session_factory,
        ):
            return app.test_client().get(
                "/locais",
                query_string=query_string,
            )

    def test_default_page_includes_sql_aggregates_and_metadata(self):
        response = self.get()

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(
            payload["paginacao"],
            {
                "pagina": 1,
                "por_pagina": 12,
                "total_itens": 6,
                "total_paginas": 1,
            },
        )
        by_slug = {local["slug"]: local for local in payload["locais"]}
        self.assertEqual(by_slug["arpoador"]["nota_media"], 4.5)
        self.assertEqual(by_slug["arpoador"]["total_avaliacoes"], 2)
        self.assertIsNone(by_slug["museu-de-arte-moderna"]["nota_media"])
        self.assertEqual(
            by_slug["museu-de-arte-moderna"]["total_avaliacoes"],
            0,
        )

    def test_count_is_calculated_after_filters_and_before_pagination(self):
        response = self.get(
            {
                "categoria": "praias",
                "pagina": "2",
                "por_pagina": "1",
            }
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(
            [local["slug"] for local in payload["locais"]],
            ["praia-de-sao-conrado"],
        )
        self.assertEqual(
            payload["paginacao"],
            {
                "pagina": 2,
                "por_pagina": 1,
                "total_itens": 2,
                "total_paginas": 2,
            },
        )

    def test_page_beyond_last_returns_empty_with_coherent_metadata(self):
        response = self.get({"pagina": "3", "por_pagina": "4"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["locais"], [])
        self.assertEqual(
            response.get_json()["paginacao"],
            {
                "pagina": 3,
                "por_pagina": 4,
                "total_itens": 6,
                "total_paginas": 2,
            },
        )

    def test_empty_filtered_result_has_zero_totals(self):
        response = self.get({"cidade": "Teresópolis"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {
                "locais": [],
                "paginacao": {
                    "pagina": 1,
                    "por_pagina": 12,
                    "total_itens": 0,
                    "total_paginas": 0,
                },
            },
        )

    def test_all_five_orderings_are_stable(self):
        expected = {
            "nome_asc": [1, 6, 3, 2, 5, 4],
            "nome_desc": [4, 5, 2, 3, 6, 1],
            "nota_media_desc": [2, 4, 1, 3, 5, 6],
            "total_avaliacoes_desc": [1, 2, 3, 4, 5, 6],
            "destaque_desc": [1, 3, 5, 6, 2, 4],
        }

        for ordenar_por, expected_ids in expected.items():
            with self.subTest(ordenar_por=ordenar_por):
                response = self.get({"ordenar_por": ordenar_por})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    [local["id"] for local in response.get_json()["locais"]],
                    expected_ids,
                )

    def test_identifier_is_the_tiebreaker_for_equal_names(self):
        with self.session_factory.begin() as session:
            session.query(LocalTuristico).filter(LocalTuristico.id.in_((1, 5))).update(
                {LocalTuristico.nome: "Mesmo nome"},
                synchronize_session=False,
            )

        response = self.get({"categoria": "praias", "ordenar_por": "nome_desc"})

        self.assertEqual(
            [local["id"] for local in response.get_json()["locais"]],
            [1, 5],
        )

    def test_listing_executes_two_selects_without_query_per_local(self):
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
            response = self.get({"por_pagina": "2"})
        finally:
            event.remove(
                self.engine,
                "before_cursor_execute",
                register_select,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()["locais"]), 2)
        self.assertEqual(len(selects), 2)


if __name__ == "__main__":
    unittest.main()
