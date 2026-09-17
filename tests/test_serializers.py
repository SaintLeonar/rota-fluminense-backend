import json
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from utils import serializers


def build_local(**overrides):
    fields = {
        "id": 7,
        "slug": "pao-de-acucar",
        "nome": "Pão de Açúcar",
        "categoria": "mirantes",
        "descricao": "Complexo turístico com vista panorâmica.",
        "cidade": "Rio de Janeiro",
        "bairro": "Urca",
        "regiao": "Zona Sul",
        "imagem": "/imagens/locais/pao-de-acucar.jpg",
        "destaque": 1,
        "latitude": Decimal("-22.948600"),
        "longitude": Decimal("-43.156600"),
        "nota_media": Decimal("4.5"),
        "total_avaliacoes": 2,
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


def build_avaliacao(**overrides):
    fields = {
        "id": 11,
        "local_id": 7,
        "autor": "Marina Costa",
        "nota": 5,
        "comentario": "Ótimo lugar para acompanhar o pôr do sol.",
        "criado_em": datetime(
            2026,
            9,
            14,
            15,
            30,
            tzinfo=timezone(timedelta(hours=-3)),
        ),
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


class SerializerTestCase(unittest.TestCase):
    def test_local_serialization_normalizes_json_types_and_aggregates(self):
        payload = serializers.serializar_local(build_local())

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
        self.assertIs(payload["destaque"], True)
        self.assertIsInstance(payload["latitude"], float)
        self.assertIsInstance(payload["longitude"], float)
        self.assertEqual(payload["nota_media"], 4.5)
        self.assertEqual(payload["total_avaliacoes"], 2)
        json.dumps(payload)

    def test_local_without_aggregates_uses_contract_defaults(self):
        local = build_local()
        del local.nota_media
        del local.total_avaliacoes

        payload = serializers.serializar_local(local)

        self.assertIsNone(payload["nota_media"])
        self.assertEqual(payload["total_avaliacoes"], 0)

    def test_local_collection_includes_pagination_and_empty_result(self):
        payload = serializers.serializar_locais(
            [],
            pagina=3,
            por_pagina=12,
            total_itens=0,
            total_paginas=0,
        )

        self.assertEqual(payload["locais"], [])
        self.assertEqual(
            payload["paginacao"],
            {
                "pagina": 3,
                "por_pagina": 12,
                "total_itens": 0,
                "total_paginas": 0,
            },
        )

    def test_evaluation_serialization_uses_canonical_fields_and_utc_z(self):
        payload = serializers.serializar_avaliacao(build_avaliacao())

        self.assertEqual(
            payload,
            {
                "id": 11,
                "local_id": 7,
                "autor": "Marina Costa",
                "nota": 5,
                "comentario": ("Ótimo lugar para acompanhar o pôr do sol."),
                "criado_em": "2026-09-14T18:30:00Z",
            },
        )
        self.assertNotIn("nome_usuario", payload)
        json.dumps(payload)

    def test_naive_database_datetime_is_interpreted_as_utc(self):
        avaliacao = build_avaliacao(
            comentario=None,
            criado_em=datetime(2026, 9, 14, 18, 30),
        )

        payload = serializers.serializar_avaliacao(avaliacao)

        self.assertIsNone(payload["comentario"])
        self.assertEqual(payload["criado_em"], "2026-09-14T18:30:00Z")

    def test_evaluation_collection_has_only_canonical_envelope(self):
        payload = serializers.serializar_avaliacoes([build_avaliacao()])

        self.assertEqual(set(payload), {"avaliacoes"})
        self.assertEqual(len(payload["avaliacoes"]), 1)
        self.assertEqual(payload["avaliacoes"][0]["autor"], "Marina Costa")


if __name__ == "__main__":
    unittest.main()
