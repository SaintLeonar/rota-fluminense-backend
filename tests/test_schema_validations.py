import unittest

from pydantic import ValidationError

from schemas import avaliacao_schema, local_schema
from utils.constants import CIDADES_RJ


def build_local_fields(**overrides):
    fields = {
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
    fields.update(overrides)
    return fields


class SchemaValidationTestCase(unittest.TestCase):
    def assert_field_error(self, context, field):
        errors = context.exception.errors()
        self.assertTrue(
            any(error["loc"] == (field,) for error in errors),
            errors,
        )

    def test_local_text_category_and_city_are_normalized(self):
        local = local_schema.LocalInputSchema(
            **build_local_fields(
                nome="  Pão de Açúcar  ",
                categoria="  MIRANTES  ",
                cidade="  rio de janeiro  ",
                bairro="  Urca  ",
            )
        )
        query = local_schema.LocalQuerySchema(cidade="teresopolis")

        self.assertEqual(local.nome, "Pão de Açúcar")
        self.assertEqual(local.categoria, "mirantes")
        self.assertEqual(local.cidade, "Rio de Janeiro")
        self.assertEqual(local.bairro, "Urca")
        self.assertEqual(query.cidade, "Teresópolis")

    def test_city_domain_contains_the_92_official_rio_municipalities(self):
        self.assertEqual(len(CIDADES_RJ), 92)
        self.assertEqual(len(set(CIDADES_RJ)), 92)
        self.assertIn("Armação dos Búzios", CIDADES_RJ)
        self.assertIn("Rio de Janeiro", CIDADES_RJ)

    def test_all_local_text_fields_reject_blank_and_excess_length(self):
        limits = {
            "nome": 120,
            "categoria": 80,
            "descricao": 2000,
            "cidade": 120,
            "bairro": 120,
            "regiao": 80,
            "imagem": 500,
        }
        for field, limit in limits.items():
            with self.subTest(field=field, reason="blank"):
                with self.assertRaises(ValidationError) as context:
                    local_schema.LocalInputSchema(
                        **build_local_fields(**{field: "   "})
                    )
                self.assert_field_error(context, field)

            with self.subTest(field=field, reason="length"):
                with self.assertRaises(ValidationError) as context:
                    local_schema.LocalInputSchema(
                        **build_local_fields(**{field: "x" * (limit + 1)})
                    )
                self.assert_field_error(context, field)

    def test_local_domain_rejects_unknown_category_and_city(self):
        for field, value in (
            ("categoria", "restaurantes"),
            ("cidade", "São Paulo"),
        ):
            with self.subTest(field=field):
                with self.assertRaises(ValidationError) as context:
                    local_schema.LocalInputSchema(
                        **build_local_fields(**{field: value})
                    )
                self.assert_field_error(context, field)

    def test_image_accepts_public_references_and_rejects_local_paths(self):
        for image in (
            "/imagens/locais/arpoador.jpg",
            "https://cdn.example.com/arpoador.jpg",
        ):
            with self.subTest(image=image):
                local = local_schema.LocalInputSchema(
                    **build_local_fields(imagem=image)
                )
                self.assertEqual(local.imagem, image)

        for image in (
            "C:\\imagens\\arpoador.jpg",
            "file:///tmp/arpoador.jpg",
            "/../segredo.jpg",
            "http://localhost/arpoador.jpg",
            "http://127.0.0.1/arpoador.jpg",
        ):
            with self.subTest(image=image):
                with self.assertRaises(ValidationError) as context:
                    local_schema.LocalInputSchema(**build_local_fields(imagem=image))
                self.assert_field_error(context, "imagem")

    def test_coordinates_and_featured_require_json_domain_types(self):
        local = local_schema.LocalInputSchema(
            **build_local_fields(latitude=-90, longitude=180)
        )
        self.assertEqual(local.latitude, -90)
        self.assertEqual(local.longitude, 180)

        for field, value in (
            ("latitude", -90.000001),
            ("latitude", "22.9"),
            ("latitude", float("inf")),
            ("longitude", 180.000001),
            ("longitude", True),
            ("destaque", 1),
            ("destaque", "true"),
        ):
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValidationError) as context:
                    local_schema.LocalInputSchema(
                        **build_local_fields(**{field: value})
                    )
                self.assert_field_error(context, field)

    def test_slug_is_canonical_in_creation_and_paths(self):
        local = local_schema.LocalInputSchema(
            **build_local_fields(),
            slug="pao-de-acucar",
        )
        self.assertEqual(local.slug, "pao-de-acucar")

        for slug in (
            "Pao-de-Acucar",
            "pão-de-açúcar",
            " pao-de-acucar ",
            "pao--de-acucar",
            "x" * 121,
        ):
            with self.subTest(slug=slug):
                with self.assertRaises(ValidationError) as context:
                    local_schema.LocalPathSchema(slug=slug)
                self.assert_field_error(context, "slug")

    def test_query_validates_boolean_pagination_and_ordering(self):
        query = local_schema.LocalQuerySchema(
            destaque="false",
            pagina="2",
            por_pagina="100",
            ordenar_por="nota_media_desc",
        )
        self.assertFalse(query.destaque)
        self.assertEqual(query.pagina, 2)
        self.assertEqual(query.por_pagina, 100)

        for field, value in (
            ("destaque", "1"),
            ("destaque", "True"),
            ("pagina", 0),
            ("pagina", "1.5"),
            ("por_pagina", 101),
            ("ordenar_por", "mais_recentes"),
        ):
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValidationError) as context:
                    local_schema.LocalQuerySchema(**{field: value})
                self.assert_field_error(context, field)

    def test_evaluation_validates_text_note_and_nullable_comment(self):
        avaliacao = avaliacao_schema.AvaliacaoInputSchema(
            autor="  Marina Costa  ",
            nota=5,
        )
        self.assertEqual(avaliacao.autor, "Marina Costa")
        self.assertIsNone(avaliacao.comentario)

        for field, value in (
            ("autor", "   "),
            ("autor", "x" * 121),
            ("nota", 0),
            ("nota", 6),
            ("nota", True),
            ("nota", "5"),
            ("comentario", "   "),
            ("comentario", "x" * 1001),
        ):
            with self.subTest(field=field, value=value):
                fields = {
                    "autor": "Marina Costa",
                    "nota": 5,
                    field: value,
                }
                with self.assertRaises(ValidationError) as context:
                    avaliacao_schema.AvaliacaoInputSchema(**fields)
                self.assert_field_error(context, field)

    def test_partial_evaluation_requires_a_mutable_present_field(self):
        with self.assertRaises(ValidationError):
            avaliacao_schema.AvaliacaoUpdateSchema()

        update = avaliacao_schema.AvaliacaoUpdateSchema(comentario=None)
        self.assertEqual(update.model_fields_set, {"comentario"})
        self.assertIsNone(update.comentario)

        for field in ("autor", "nota"):
            with self.subTest(field=field):
                with self.assertRaises(ValidationError) as context:
                    avaliacao_schema.AvaliacaoUpdateSchema(**{field: None})
                self.assert_field_error(context, field)

    def test_positive_identifiers_and_derived_values_are_validated(self):
        with self.assertRaises(ValidationError) as context:
            avaliacao_schema.AvaliacaoPathSchema(avaliacao_id=0)
        self.assert_field_error(context, "avaliacao_id")

        response = build_local_fields()
        response.update(
            id=7,
            slug="pao-de-acucar",
            nota_media=None,
            total_avaliacoes=0,
        )
        local_schema.LocalSchema(**response)

        for field, value in (
            ("nota_media", 5.1),
            ("total_avaliacoes", -1),
        ):
            with self.subTest(field=field):
                invalid = {**response, field: value}
                with self.assertRaises(ValidationError) as context:
                    local_schema.LocalSchema(**invalid)
                self.assert_field_error(context, field)


if __name__ == "__main__":
    unittest.main()
