import os
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from app import app  # noqa: E402
from models.base import Base  # noqa: E402
from models.local_turistico import LocalTuristico  # noqa: E402
from services import local_service  # noqa: E402
from utils.exceptions import AppError  # noqa: E402
from utils.slug import gerar_slug, resolver_slug, validar_slug  # noqa: E402


def build_local_data(**overrides):
    data = {
        "nome": "Pão de Açúcar",
        "categoria": "mirantes",
        "descricao": "Complexo turístico com vista panorâmica.",
        "cidade": "Rio de Janeiro",
        "bairro": "Urca",
        "regiao": "Zona Sul",
        "imagem": "/imagens/locais/pao-de-acucar.jpg",
        "destaque": True,
        "latitude": -22.9486,
        "longitude": -43.1566,
    }
    data.update(overrides)
    return data


class SlugStrategyTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        app.config.update(TESTING=True)

    def tearDown(self):
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def create_local(self, **overrides):
        with patch(
            "services.local_service.SessionLocal",
            self.session_factory,
        ):
            return local_service.criar_local(build_local_data(**overrides))

    def test_generated_slug_normalizes_unicode_and_separators(self):
        self.assertEqual(
            gerar_slug("  Museu do Amanhã: Ação & Arte!  "),
            "museu-do-amanha-acao-arte",
        )
        self.assertEqual(gerar_slug("Pão---de___Açúcar"), "pao-de-acucar")

    def test_explicit_slug_is_preserved_without_silent_correction(self):
        self.assertEqual(
            resolver_slug("Nome diferente", "slug-publicado"),
            "slug-publicado",
        )

        for slug in (" Slug ", "slug--invalido", "ação", ""):
            with self.subTest(slug=slug):
                with self.assertRaises(ValueError):
                    validar_slug(slug)

    def test_slug_validation_enforces_type_and_exact_length_boundary(self):
        maximum_slug = "a" * 120
        self.assertEqual(validar_slug(maximum_slug), maximum_slug)

        for slug in (None, 7, True, "a" * 121):
            with self.subTest(slug=slug):
                with self.assertRaises(ValueError):
                    validar_slug(slug)

    def test_generation_rejects_empty_or_oversized_result(self):
        for name in ("東京", "a" * 121):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    gerar_slug(name)

    def test_service_generates_and_persists_slug_with_complete_record(self):
        local = self.create_local()

        self.assertEqual(local["slug"], "pao-de-acucar")
        self.assertIsNotNone(local["id"])
        self.assertIsNone(local["nota_media"])
        self.assertEqual(local["total_avaliacoes"], 0)
        with self.session_factory() as session:
            persisted = session.query(LocalTuristico).one()
            self.assertEqual(persisted.slug, "pao-de-acucar")
            self.assertEqual(persisted.bairro, "Urca")
            self.assertTrue(persisted.destaque)

    def test_precheck_rejects_explicit_and_generated_duplicates(self):
        self.create_local(slug="pao-de-acucar")

        for data in (
            {"slug": "pao-de-acucar"},
            {},
        ):
            with self.subTest(data=data):
                with self.assertRaises(AppError) as context:
                    self.create_local(**data)
                self.assertEqual(context.exception.status_code, 409)
                self.assertEqual(
                    context.exception.codigo,
                    "slug_ja_existente",
                )
                self.assertEqual(
                    context.exception.detalhes[0]["campo"],
                    "slug",
                )

        with self.session_factory() as session:
            self.assertEqual(session.query(LocalTuristico).count(), 1)

    def test_service_maps_invalid_generated_slug_to_public_error(self):
        with self.assertRaises(AppError) as context:
            self.create_local(nome="東京")

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.codigo, "requisicao_invalida")
        self.assertEqual(context.exception.detalhes[0]["campo"], "slug")

    def test_unique_index_protects_race_and_failed_write_is_rolled_back(self):
        self.create_local(slug="pao-de-acucar")

        with (
            patch(
                "services.local_service.SessionLocal",
                self.session_factory,
            ),
            patch("services.local_service._slug_em_uso", return_value=False),
            self.assertRaises(IntegrityError),
        ):
            local_service.criar_local(build_local_data(slug="pao-de-acucar"))

        with self.session_factory() as session:
            self.assertEqual(session.query(LocalTuristico).count(), 1)

    def test_post_returns_created_slug_and_conflict_has_no_suffix(self):
        client = app.test_client()
        body = build_local_data()

        with patch(
            "services.local_service.SessionLocal",
            self.session_factory,
        ):
            created = client.post("/locais", json=body)
            conflict = client.post("/locais", json=body)

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.get_json()["slug"], "pao-de-acucar")
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(
            conflict.get_json()["erro"]["codigo"],
            "slug_ja_existente",
        )
        with self.session_factory() as session:
            self.assertEqual(session.query(LocalTuristico).count(), 1)


if __name__ == "__main__":
    unittest.main()
