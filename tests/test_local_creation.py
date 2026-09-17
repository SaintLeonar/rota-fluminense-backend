import os
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from app import app  # noqa: E402
from models.base import Base  # noqa: E402
from models.local_turistico import LocalTuristico  # noqa: E402


def build_local_body(**overrides):
    body = {
        "slug": "museu-imperial",
        "nome": "Museu Imperial",
        "categoria": "museus",
        "descricao": "Acervo histórico da antiga residência imperial.",
        "cidade": "Petrópolis",
        "bairro": "Centro",
        "regiao": "Região Serrana",
        "imagem": "/imagens/locais/museu-imperial.jpg",
        "destaque": True,
        "latitude": -22.505,
        "longitude": -43.1758,
    }
    body.update(overrides)
    return body


class LocalCreationTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        app.config.update(TESTING=True)

    def tearDown(self):
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def post(self, body):
        with patch(
            "services.local_service.SessionLocal",
            self.session_factory,
        ):
            return app.test_client().post("/locais", json=body)

    def assert_database_is_empty(self):
        with self.session_factory() as session:
            self.assertEqual(session.query(LocalTuristico).count(), 0)

    def test_complete_creation_persists_every_field_and_returns_201(self):
        body = build_local_body()

        response = self.post(body)

        self.assertEqual(response.status_code, 201)
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
        for field, value in body.items():
            self.assertEqual(payload[field], value)
        self.assertIsInstance(payload["id"], int)
        self.assertIsNone(payload["nota_media"])
        self.assertEqual(payload["total_avaliacoes"], 0)

        with self.session_factory() as session:
            persisted = session.query(LocalTuristico).one()
            for field, value in body.items():
                persisted_value = getattr(persisted, field)
                if field in {"latitude", "longitude"}:
                    persisted_value = float(persisted_value)
                self.assertEqual(persisted_value, value)

    def test_optional_fields_use_defaults_and_values_are_normalized(self):
        body = build_local_body(
            nome="  Museu Imperial  ",
            categoria="  MUSEUS  ",
            cidade="  petropolis  ",
            bairro="  Centro  ",
            regiao="  Região Serrana  ",
        )
        body.pop("slug")
        body.pop("destaque")

        response = self.post(body)

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertEqual(payload["slug"], "museu-imperial")
        self.assertEqual(payload["nome"], "Museu Imperial")
        self.assertEqual(payload["categoria"], "museus")
        self.assertEqual(payload["cidade"], "Petrópolis")
        self.assertEqual(payload["bairro"], "Centro")
        self.assertEqual(payload["regiao"], "Região Serrana")
        self.assertFalse(payload["destaque"])

        with self.session_factory() as session:
            persisted = session.query(LocalTuristico).one()
            self.assertEqual(persisted.slug, "museu-imperial")
            self.assertEqual(persisted.cidade, "Petrópolis")
            self.assertFalse(persisted.destaque)

    def test_read_only_unknown_and_legacy_fields_are_rejected(self):
        for field, value in (
            ("id", 99),
            ("nota_media", 5.0),
            ("total_avaliacoes", 10),
            ("campo_desconhecido", "valor"),
            ("media_avaliacoes", 4.5),
        ):
            with self.subTest(field=field):
                response = self.post(build_local_body(**{field: value}))
                payload = response.get_json()

                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    payload["erro"]["codigo"],
                    "requisicao_invalida",
                )
                self.assertEqual(
                    payload["erro"]["detalhes"][0],
                    {
                        "campo": field,
                        "codigo": "campo_nao_permitido",
                        "mensagem": "O campo não é permitido.",
                    },
                )

        self.assert_database_is_empty()

    def test_each_required_field_is_rejected_when_missing(self):
        required_fields = {
            "nome",
            "categoria",
            "descricao",
            "cidade",
            "bairro",
            "regiao",
            "imagem",
            "latitude",
            "longitude",
        }

        for field in required_fields:
            with self.subTest(field=field):
                body = build_local_body()
                body.pop(field)
                response = self.post(body)
                detail = response.get_json()["erro"]["detalhes"][0]

                self.assertEqual(response.status_code, 400)
                self.assertEqual(detail["campo"], field)
                self.assertEqual(detail["codigo"], "obrigatorio")

        self.assert_database_is_empty()

    def test_invalid_domains_are_rejected_without_persistence(self):
        invalid_values = (
            ("categoria", "restaurantes"),
            ("cidade", "São Paulo"),
            ("imagem", "C:\\imagens\\local.jpg"),
            ("destaque", "true"),
            ("latitude", -91.0),
            ("longitude", 181.0),
        )

        for field, value in invalid_values:
            with self.subTest(field=field):
                response = self.post(build_local_body(**{field: value}))

                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.get_json()["erro"]["detalhes"][0]["campo"],
                    field,
                )

        self.assert_database_is_empty()

    def test_duplicate_slug_returns_conflict_and_preserves_first_record(self):
        first = self.post(build_local_body())
        duplicate = self.post(
            build_local_body(nome="Outro museu com o mesmo slug")
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(
            duplicate.get_json()["erro"]["codigo"],
            "slug_ja_existente",
        )
        with self.session_factory() as session:
            persisted = session.query(LocalTuristico).one()
            self.assertEqual(persisted.nome, "Museu Imperial")

    def test_openapi_documents_created_validation_and_conflict_responses(self):
        response = app.test_client().get("/openapi/openapi.json")

        self.assertEqual(response.status_code, 200)
        responses = response.get_json()["paths"]["/locais"]["post"][
            "responses"
        ]
        self.assertTrue({"201", "400", "409", "500"}.issubset(responses))


if __name__ == "__main__":
    unittest.main()
