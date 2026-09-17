import os
import unittest
from datetime import timezone
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


class AvaliacaoUpdateTestCase(unittest.TestCase):
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

    def patch_evaluation(self, evaluation_id, payload):
        with patch(
            "services.avaliacao_service.SessionLocal",
            self.session_factory,
        ):
            return app.test_client().patch(
                f"/avaliacoes/{evaluation_id}",
                json=payload,
            )

    def evaluation_snapshot(self, author="Marina Costa"):
        with self.session_factory() as session:
            evaluation = (
                session.query(Avaliacao)
                .filter(Avaliacao.autor == author)
                .one()
            )
            return {
                "id": evaluation.id,
                "local_id": evaluation.local_id,
                "autor": evaluation.autor,
                "nota": evaluation.nota,
                "comentario": evaluation.comentario,
                "criado_em": evaluation.criado_em,
            }

    def serialized_datetime(self, value):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.isoformat().replace("+00:00", "Z")

    def test_update_changes_mutable_fields_and_preserves_read_only_fields(
        self,
    ):
        before = self.evaluation_snapshot()

        response = self.patch_evaluation(
            before["id"],
            {
                "autor": "  Marina Atualizada  ",
                "nota": 3,
                "comentario": "  Comentário revisado.  ",
            },
        )

        self.assertEqual(response.status_code, 200)
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
        self.assertEqual(payload["id"], before["id"])
        self.assertEqual(payload["local_id"], before["local_id"])
        self.assertEqual(
            payload["criado_em"],
            self.serialized_datetime(before["criado_em"]),
        )
        self.assertEqual(payload["autor"], "Marina Atualizada")
        self.assertEqual(payload["nota"], 3)
        self.assertEqual(payload["comentario"], "Comentário revisado.")

        with self.session_factory() as session:
            persisted = session.get(Avaliacao, before["id"])
            self.assertEqual(persisted.autor, "Marina Atualizada")
            self.assertEqual(persisted.nota, 3)
            self.assertEqual(persisted.comentario, "Comentário revisado.")
            self.assertEqual(persisted.local_id, before["local_id"])
            self.assertEqual(persisted.criado_em, before["criado_em"])

    def test_update_only_changes_fields_present_in_request(self):
        before = self.evaluation_snapshot()

        response = self.patch_evaluation(before["id"], {"nota": 2})

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["nota"], 2)
        self.assertEqual(payload["autor"], before["autor"])
        self.assertEqual(payload["comentario"], before["comentario"])

        after = self.evaluation_snapshot()
        self.assertEqual(after["nota"], 2)
        self.assertEqual(after["autor"], before["autor"])
        self.assertEqual(after["comentario"], before["comentario"])

    def test_null_comment_removes_existing_comment(self):
        before = self.evaluation_snapshot()
        self.assertIsNotNone(before["comentario"])

        response = self.patch_evaluation(
            before["id"],
            {"comentario": None},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get_json()["comentario"])
        self.assertIsNone(self.evaluation_snapshot()["comentario"])

    def test_empty_body_is_rejected_without_writing(self):
        before = self.evaluation_snapshot()

        response = self.patch_evaluation(before["id"], {})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["erro"]["codigo"],
            "requisicao_invalida",
        )
        self.assertEqual(self.evaluation_snapshot(), before)

    def test_update_validates_only_mutable_field_domains(self):
        before = self.evaluation_snapshot()
        cases = (
            ({"autor": None}, "autor"),
            ({"autor": "   "}, "autor"),
            ({"nota": None}, "nota"),
            ({"nota": True}, "nota"),
            ({"nota": 0}, "nota"),
            ({"nota": 6}, "nota"),
            ({"comentario": "   "}, "comentario"),
            ({"comentario": "x" * 1001}, "comentario"),
        )

        for payload, field in cases:
            with self.subTest(payload=payload):
                response = self.patch_evaluation(before["id"], payload)

                self.assertEqual(response.status_code, 400)
                error = response.get_json()["erro"]
                self.assertEqual(error["codigo"], "requisicao_invalida")
                self.assertEqual(error["detalhes"][0]["campo"], field)
                self.assertEqual(self.evaluation_snapshot(), before)

    def test_update_rejects_read_only_legacy_and_unknown_fields(self):
        before = self.evaluation_snapshot()
        for field, value in (
            ("id", 99),
            ("local_id", 6),
            ("criado_em", "2026-09-15T12:00:00Z"),
            ("nome_usuario", "Nome legado"),
            ("campo_desconhecido", "valor"),
        ):
            with self.subTest(field=field):
                response = self.patch_evaluation(
                    before["id"],
                    {field: value},
                )

                self.assertEqual(response.status_code, 400)
                details = response.get_json()["erro"]["detalhes"]
                self.assertEqual(details[0]["campo"], field)
                self.assertEqual(
                    details[0]["codigo"],
                    "campo_nao_permitido",
                )
                self.assertEqual(self.evaluation_snapshot(), before)

    def test_invalid_and_unknown_ids_return_distinct_canonical_errors(self):
        before = self.evaluation_snapshot()

        invalid = self.patch_evaluation(0, {"nota": 4})
        unknown = self.patch_evaluation(9999, {"nota": 4})

        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(
            invalid.get_json()["erro"]["codigo"],
            "requisicao_invalida",
        )
        self.assertEqual(unknown.status_code, 404)
        self.assertEqual(
            unknown.get_json()["erro"]["codigo"],
            "avaliacao_nao_encontrada",
        )
        self.assertEqual(
            unknown.get_json()["erro"]["requisicao_id"],
            unknown.headers["X-Request-ID"],
        )
        self.assertEqual(self.evaluation_snapshot(), before)

    def test_patch_route_and_openapi_expose_the_canonical_contract(self):
        patch_rules = {
            rule.rule
            for rule in app.url_map.iter_rules()
            if "PATCH" in rule.methods
        }
        self.assertEqual(
            patch_rules,
            {"/avaliacoes/<int:avaliacao_id>"},
        )

        openapi = app.test_client().get("/openapi/openapi.json").get_json()
        operation = openapi["paths"]["/avaliacoes/{avaliacao_id}"]["patch"]
        self.assertTrue(
            {"200", "400", "404", "500"}.issubset(operation["responses"])
        )
        self.assertEqual(
            operation["parameters"][0]["name"],
            "avaliacao_id",
        )


if __name__ == "__main__":
    unittest.main()
