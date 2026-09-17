import os
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from app import app  # noqa: E402
from models.base import Base  # noqa: E402
from models.local_turistico import LocalTuristico  # noqa: E402
from scripts.seed import load_evaluation_seed_data  # noqa: E402
from scripts.seed import load_local_seed_data  # noqa: E402
from scripts.seed import seed_evaluations  # noqa: E402
from scripts.seed import seed_locations  # noqa: E402


def build_update_body(**overrides):
    body = {
        "nome": "Centro Cultural Atualizado",
        "categoria": "museus",
        "descricao": "Descrição integral do local após a atualização.",
        "cidade": "Niterói",
        "bairro": "Icaraí",
        "regiao": "Região Metropolitana",
        "imagem": "/imagens/locais/centro-cultural-atualizado.jpg",
        "destaque": False,
        "latitude": -22.9068,
        "longitude": -43.1729,
    }
    body.update(overrides)
    return body


class LocalUpdateTestCase(unittest.TestCase):
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

    def put(self, slug, body):
        with patch(
            "services.local_service.SessionLocal",
            self.session_factory,
        ):
            return app.test_client().put(f"/locais/{slug}", json=body)

    def persisted_arpoador(self):
        with self.session_factory() as session:
            local = (
                session.query(LocalTuristico)
                .filter(LocalTuristico.slug == "arpoador")
                .one()
            )
            return {
                column.name: getattr(local, column.name)
                for column in LocalTuristico.__table__.columns
            }

    def test_put_replaces_all_mutable_fields_and_preserves_derived_values(
        self,
    ):
        original = self.persisted_arpoador()
        body = build_update_body()

        response = self.put("arpoador", body)

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["id"], original["id"])
        self.assertEqual(payload["slug"], "arpoador")
        for field, value in body.items():
            self.assertEqual(payload[field], value)
        self.assertEqual(payload["nota_media"], 4.5)
        self.assertEqual(payload["total_avaliacoes"], 2)

        persisted = self.persisted_arpoador()
        self.assertEqual(persisted["id"], original["id"])
        self.assertEqual(persisted["slug"], "arpoador")
        for field, value in body.items():
            persisted_value = persisted[field]
            if field in {"latitude", "longitude"}:
                persisted_value = float(persisted_value)
            self.assertEqual(persisted_value, value)

    def test_put_normalizes_values_before_replacing_the_record(self):
        response = self.put(
            "arpoador",
            build_update_body(
                nome="  Centro Cultural Atualizado  ",
                categoria="  MUSEUS  ",
                cidade="  niteroi  ",
                bairro="  Icaraí  ",
                regiao="  Região Metropolitana  ",
            ),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["nome"], "Centro Cultural Atualizado")
        self.assertEqual(payload["categoria"], "museus")
        self.assertEqual(payload["cidade"], "Niterói")
        self.assertEqual(payload["bairro"], "Icaraí")
        self.assertEqual(payload["regiao"], "Região Metropolitana")

    def test_put_requires_every_mutable_field_without_partial_fallback(self):
        original = self.persisted_arpoador()

        for field in build_update_body():
            with self.subTest(field=field):
                body = build_update_body()
                body.pop(field)
                response = self.put("arpoador", body)
                detail = response.get_json()["erro"]["detalhes"][0]

                self.assertEqual(response.status_code, 400)
                self.assertEqual(detail["campo"], field)
                self.assertEqual(detail["codigo"], "obrigatorio")

        self.assertEqual(self.persisted_arpoador(), original)

    def test_put_rejects_immutable_unknown_and_legacy_fields(self):
        original = self.persisted_arpoador()

        for field, value in (
            ("id", 99),
            ("slug", "novo-slug"),
            ("nota_media", 5.0),
            ("total_avaliacoes", 20),
            ("campo_desconhecido", "valor"),
            ("media_avaliacoes", 4.5),
        ):
            with self.subTest(field=field):
                response = self.put(
                    "arpoador",
                    build_update_body(**{field: value}),
                )
                detail = response.get_json()["erro"]["detalhes"][0]

                self.assertEqual(response.status_code, 400)
                self.assertEqual(detail["campo"], field)
                self.assertEqual(detail["codigo"], "campo_nao_permitido")

        self.assertEqual(self.persisted_arpoador(), original)

    def test_put_distinguishes_malformed_and_unknown_slug(self):
        malformed = self.put("Arpoador", build_update_body())
        unknown = self.put("local-inexistente", build_update_body())

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

    def test_put_route_and_openapi_use_slug_without_legacy_id(self):
        put_rules = {
            rule.rule
            for rule in app.url_map.iter_rules()
            if "PUT" in rule.methods
        }
        self.assertIn("/locais/<slug>", put_rules)
        self.assertNotIn("/locais/<int:local_id>", put_rules)

        openapi = app.test_client().get("/openapi/openapi.json").get_json()
        operation = openapi["paths"]["/locais/{slug}"]["put"]
        self.assertTrue(
            {"200", "400", "404", "500"}.issubset(operation["responses"])
        )


if __name__ == "__main__":
    unittest.main()
