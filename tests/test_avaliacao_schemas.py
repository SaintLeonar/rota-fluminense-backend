import unittest
from datetime import datetime, timezone

from pydantic import ValidationError

from schemas import avaliacao_schema


def build_response_fields():
    return {
        "id": 11,
        "local_id": 7,
        "autor": "Marina Costa",
        "nota": 5,
        "comentario": "Ótimo lugar para acompanhar o pôr do sol.",
        "criado_em": "2026-09-14T18:30:00Z",
    }


class AvaliacaoSchemaTestCase(unittest.TestCase):
    def test_creation_uses_author_and_defaults_comment_to_none(self):
        avaliacao = avaliacao_schema.AvaliacaoInputSchema(
            autor="Marina Costa",
            nota=5,
        )

        self.assertEqual(avaliacao.autor, "Marina Costa")
        self.assertEqual(avaliacao.nota, 5)
        self.assertIsNone(avaliacao.comentario)

    def test_creation_rejects_legacy_read_only_and_unknown_fields(self):
        for field, value in (
            ("nome_usuario", "Nome legado"),
            ("id", 11),
            ("local_id", 7),
            ("criado_em", "2026-09-14T18:30:00Z"),
            ("campo_desconhecido", "valor"),
        ):
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    avaliacao_schema.AvaliacaoInputSchema(
                        autor="Marina Costa",
                        nota=5,
                        **{field: value},
                    )

    def test_partial_update_exposes_only_mutable_fields(self):
        update = avaliacao_schema.AvaliacaoUpdateSchema(nota=4)

        self.assertEqual(update.nota, 4)
        self.assertEqual(update.model_fields_set, {"nota"})

        with self.assertRaises(ValidationError):
            avaliacao_schema.AvaliacaoUpdateSchema()

        for field, value in (
            ("nome_usuario", "Nome legado"),
            ("id", 11),
            ("local_id", 7),
            ("criado_em", "2026-09-14T18:30:00Z"),
        ):
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    avaliacao_schema.AvaliacaoUpdateSchema(
                        **{field: value},
                    )

    def test_response_and_list_follow_the_canonical_contract(self):
        avaliacao = avaliacao_schema.AvaliacaoSchema(**build_response_fields())
        payload = avaliacao_schema.AvaliacaoListSchema(
            avaliacoes=[build_response_fields()]
        )

        self.assertEqual(
            set(avaliacao.model_dump()),
            {
                "id",
                "local_id",
                "autor",
                "nota",
                "comentario",
                "criado_em",
            },
        )
        self.assertIsInstance(avaliacao.criado_em, datetime)
        self.assertEqual(avaliacao.criado_em.tzinfo, timezone.utc)
        self.assertEqual(len(payload.avaliacoes), 1)
        self.assertEqual(payload.avaliacoes[0].autor, "Marina Costa")

    def test_paths_separate_public_slug_from_evaluation_identifier(self):
        local_path = avaliacao_schema.AvaliacaoLocalPathSchema(slug="arpoador")
        evaluation_path = avaliacao_schema.AvaliacaoPathSchema(avaliacao_id=11)

        self.assertEqual(local_path.slug, "arpoador")
        self.assertEqual(evaluation_path.avaliacao_id, 11)

        with self.assertRaises(ValidationError):
            avaliacao_schema.AvaliacaoLocalPathSchema(local_id=7)

        with self.assertRaises(ValidationError):
            avaliacao_schema.AvaliacaoPathSchema(slug="avaliacao-legada")


if __name__ == "__main__":
    unittest.main()
