import unittest

from pydantic import ValidationError

from schemas import local_schema


def build_mutable_fields():
    return {
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


def build_response_fields():
    return {
        "id": 7,
        "slug": "pao-de-acucar",
        **build_mutable_fields(),
        "nota_media": 4.5,
        "total_avaliacoes": 2,
    }


class LocalSchemaTestCase(unittest.TestCase):
    def test_creation_accepts_optional_slug_and_defaults_featured_to_false(
        self,
    ):
        fields = build_mutable_fields()
        fields.pop("destaque")

        local = local_schema.LocalInputSchema(**fields)

        self.assertIsNone(local.slug)
        self.assertFalse(local.destaque)

        local_with_slug = local_schema.LocalInputSchema(
            **fields,
            slug="pao-de-acucar",
        )
        self.assertEqual(local_with_slug.slug, "pao-de-acucar")

    def test_creation_rejects_read_only_and_unknown_fields(self):
        for field, value in (
            ("id", 7),
            ("nota_media", 4.5),
            ("total_avaliacoes", 2),
            ("campo_desconhecido", "valor"),
        ):
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    local_schema.LocalInputSchema(
                        **build_mutable_fields(),
                        **{field: value},
                    )

    def test_full_update_requires_mutable_fields_and_rejects_slug(self):
        local = local_schema.LocalUpdateSchema(**build_mutable_fields())

        self.assertEqual(
            set(local.model_dump()),
            {
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
            },
        )

        missing_field = build_mutable_fields()
        missing_field.pop("destaque")
        with self.assertRaises(ValidationError):
            local_schema.LocalUpdateSchema(**missing_field)

        with self.assertRaises(ValidationError):
            local_schema.LocalUpdateSchema(
                **build_mutable_fields(),
                slug="novo-slug",
            )

    def test_response_and_detail_expose_only_the_fourteen_contract_fields(
        self,
    ):
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

        response = local_schema.LocalSchema(**build_response_fields())
        detail = local_schema.LocalDetalhadoSchema(**build_response_fields())

        self.assertEqual(set(response.model_dump()), expected_fields)
        self.assertEqual(set(detail.model_dump()), expected_fields)
        self.assertNotIn("avaliacoes", detail.model_dump())

    def test_list_query_pagination_and_path_follow_the_canonical_contract(
        self,
    ):
        payload = local_schema.LocalListSchema(
            locais=[build_response_fields()],
            paginacao={
                "pagina": 1,
                "por_pagina": 12,
                "total_itens": 1,
                "total_paginas": 1,
            },
        )
        query = local_schema.LocalQuerySchema()
        path = local_schema.LocalPathSchema(slug="pao-de-acucar")

        self.assertEqual(len(payload.locais), 1)
        self.assertEqual(payload.paginacao.total_itens, 1)
        self.assertIsNone(query.cidade)
        self.assertIsNone(query.categoria)
        self.assertIsNone(query.destaque)
        self.assertEqual(query.pagina, 1)
        self.assertEqual(query.por_pagina, 12)
        self.assertEqual(query.ordenar_por, "nome_asc")
        self.assertEqual(path.slug, "pao-de-acucar")

        with self.assertRaises(ValidationError):
            local_schema.LocalQuerySchema(parametro_legado="valor")

        with self.assertRaises(ValidationError):
            local_schema.LocalPathSchema(local_id=7)


if __name__ == "__main__":
    unittest.main()
