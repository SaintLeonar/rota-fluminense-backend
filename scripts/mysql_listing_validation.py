"""Valida filtros, paginação e ordenações da listagem no MySQL."""

from contextlib import contextmanager

from sqlalchemy import delete, select

from models.avaliacao import Avaliacao
from models.base import SessionLocal
from models.local_turistico import LocalTuristico

VALIDATION_SLUGS = (
    "validacao-b5-alfa",
    "validacao-b5-beta",
    "validacao-b5-mesmo-a",
    "validacao-b5-mesmo-b",
)


def _assert_status(response, expected_status):
    if response.status_code != expected_status:
        raise AssertionError(
            f"Status esperado {expected_status}, recebido "
            f"{response.status_code}: {response.get_data(as_text=True)}"
        )
    return response.get_json(silent=True)


def _local_payload(slug, nome, categoria, destaque):
    return {
        "slug": slug,
        "nome": nome,
        "categoria": categoria,
        "descricao": "Fixture temporária da validação MySQL da fase B5.",
        "cidade": "Niterói",
        "bairro": "Centro",
        "regiao": "Metropolitana",
        "imagem": f"/imagens/locais/{slug}.jpg",
        "destaque": destaque,
        "latitude": -22.8832,
        "longitude": -43.1034,
    }


def _cleanup_fixtures():
    with SessionLocal.begin() as session:
        slug_filter = LocalTuristico.slug.in_(VALIDATION_SLUGS)
        local_query = select(LocalTuristico.id).where(slug_filter)
        local_ids = session.scalars(local_query).all()
        if local_ids:
            evaluation_filter = Avaliacao.local_id.in_(local_ids)
            session.execute(delete(Avaliacao).where(evaluation_filter))
        session.execute(delete(LocalTuristico).where(slug_filter))


def _create_evaluation(client, slug, suffix, note):
    _assert_status(
        client.post(
            f"/locais/{slug}/avaliacoes",
            json={
                "autor": f"Validação MySQL B5 {suffix}",
                "nota": note,
                "comentario": None,
            },
        ),
        201,
    )


@contextmanager
def _listing_fixtures(client):
    _cleanup_fixtures()
    definitions = (
        (VALIDATION_SLUGS[0], "B5 Alfa", "praias", True),
        (VALIDATION_SLUGS[1], "B5 Beta", "museus", False),
        (VALIDATION_SLUGS[2], "B5 Mesmo", "mirantes", True),
        (VALIDATION_SLUGS[3], "B5 Mesmo", "parques", False),
    )
    created = []
    try:
        for definition in definitions:
            created.append(
                _assert_status(
                    client.post(
                        "/locais",
                        json=_local_payload(*definition),
                    ),
                    201,
                )
            )

        _create_evaluation(client, VALIDATION_SLUGS[0], "alfa-1", 5)
        _create_evaluation(client, VALIDATION_SLUGS[0], "alfa-2", 5)
        _create_evaluation(client, VALIDATION_SLUGS[1], "beta", 4)
        _create_evaluation(client, VALIDATION_SLUGS[2], "mesmo", 4)
        yield created
    finally:
        _cleanup_fixtures()


def _get_listing(client, query=None):
    return _assert_status(
        client.get("/locais", query_string=query or {}),
        200,
    )


def _slugs(payload):
    return [local["slug"] for local in payload["locais"]]


def _assert_invalid_query(client, query, field):
    payload = _assert_status(
        client.get("/locais", query_string=query),
        400,
    )
    error = payload["erro"]
    if error["codigo"] != "requisicao_invalida":
        raise AssertionError("A consulta inválida exige o código canônico.")
    if not any(detail["campo"] == field for detail in error["detalhes"]):
        raise AssertionError(f"A consulta inválida deveria apontar {field}.")


def validate_filters_and_pagination(client):
    """Valida filtros isolados/combinados e fronteiras de paginação."""
    with _listing_fixtures(client):
        all_locations = _get_listing(client, {"por_pagina": "100"})["locais"]
        filter_cases = (
            (
                {"cidade": "niterói", "por_pagina": "100"},
                set(VALIDATION_SLUGS),
            ),
            (
                {"categoria": "PARQUES", "por_pagina": "100"},
                {
                    local["slug"]
                    for local in all_locations
                    if local["categoria"] == "parques"
                },
            ),
            (
                {"destaque": "false", "por_pagina": "100"},
                {
                    local["slug"]
                    for local in all_locations
                    if local["destaque"] is False
                },
            ),
            (
                {
                    "cidade": "NITERÓI",
                    "categoria": "MIRANTES",
                    "destaque": "true",
                    "por_pagina": "100",
                },
                {VALIDATION_SLUGS[2]},
            ),
        )
        for query, expected_slugs in filter_cases:
            payload = _get_listing(client, query)
            if set(_slugs(payload)) != expected_slugs:
                raise AssertionError(f"Filtro MySQL incorreto para {query}.")
            if payload["paginacao"]["total_itens"] != len(expected_slugs):
                raise AssertionError("O total filtrado está incorreto.")

        empty = _get_listing(client, {"cidade": "Teresópolis"})
        if empty["locais"] != [] or empty["paginacao"] != {
            "pagina": 1,
            "por_pagina": 12,
            "total_itens": 0,
            "total_paginas": 0,
        }:
            raise AssertionError("O resultado vazio não é canônico.")

        expected_pages = (
            (1, list(VALIDATION_SLUGS[:2])),
            (2, list(VALIDATION_SLUGS[2:])),
            (3, []),
        )
        for page, expected_slugs in expected_pages:
            payload = _get_listing(
                client,
                {
                    "cidade": "Niterói",
                    "ordenar_por": "nome_asc",
                    "pagina": str(page),
                    "por_pagina": "2",
                },
            )
            if _slugs(payload) != expected_slugs:
                raise AssertionError(f"Página MySQL {page} incorreta.")
            if payload["paginacao"] != {
                "pagina": page,
                "por_pagina": 2,
                "total_itens": 4,
                "total_paginas": 2,
            }:
                raise AssertionError("Metadados de paginação incorretos.")

        minimum = _get_listing(
            client,
            {"cidade": "Niterói", "por_pagina": "1"},
        )
        maximum = _get_listing(
            client,
            {"cidade": "Niterói", "por_pagina": "100"},
        )
        if len(minimum["locais"]) != 1 or len(maximum["locais"]) != 4:
            raise AssertionError("Os limites válidos de por_pagina falharam.")

        _assert_invalid_query(client, {"por_pagina": "0"}, "por_pagina")
        _assert_invalid_query(client, {"por_pagina": "101"}, "por_pagina")


def validate_orderings(client):
    """Valida as cinco ordenações, valores nulos e desempates por id."""
    with _listing_fixtures(client) as created:
        ids = {local["slug"]: local["id"] for local in created}
        expected = {
            "nome_asc": list(VALIDATION_SLUGS),
            "nome_desc": [
                VALIDATION_SLUGS[2],
                VALIDATION_SLUGS[3],
                VALIDATION_SLUGS[1],
                VALIDATION_SLUGS[0],
            ],
            "nota_media_desc": list(VALIDATION_SLUGS),
            "total_avaliacoes_desc": list(VALIDATION_SLUGS),
            "destaque_desc": [
                VALIDATION_SLUGS[0],
                VALIDATION_SLUGS[2],
                VALIDATION_SLUGS[1],
                VALIDATION_SLUGS[3],
            ],
        }

        for ordering, expected_slugs in expected.items():
            payload = _get_listing(
                client,
                {
                    "cidade": "Niterói",
                    "ordenar_por": ordering,
                    "por_pagina": "100",
                },
            )
            if _slugs(payload) != expected_slugs:
                raise AssertionError(f"Ordenação MySQL {ordering} incorreta.")

        averages = _get_listing(
            client,
            {
                "cidade": "Niterói",
                "ordenar_por": "nota_media_desc",
                "por_pagina": "100",
            },
        )["locais"]
        if [local["nota_media"] for local in averages] != [
            5.0,
            4.0,
            4.0,
            None,
        ]:
            raise AssertionError("Médias nulas ou decrescentes incorretas.")

        tied_pairs = (
            ("nome_desc", VALIDATION_SLUGS[2:]),
            ("nota_media_desc", VALIDATION_SLUGS[1:3]),
            ("total_avaliacoes_desc", VALIDATION_SLUGS[1:3]),
        )
        for ordering, slugs in tied_pairs:
            tied_ids = [ids[slug] for slug in slugs]
            if tied_ids != sorted(tied_ids):
                raise AssertionError(f"Desempate inválido: {ordering}.")
