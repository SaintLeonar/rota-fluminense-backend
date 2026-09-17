"""Executa a validação integrada da fase E4 em MySQL descartável."""

import argparse
import json
from unittest.mock import patch

from sqlalchemy import delete, func, select, text

from app import app
from models.avaliacao import Avaliacao
from models.base import DATABASE_URL, SessionLocal
from models.local_turistico import LocalTuristico
from services import avaliacao_service

TEST_LOCAL_SLUGS = ("validacao-e4-a", "validacao-e4-b")
TEST_AUTHOR_PREFIX = "Validação E4"


def _assert_status(response, expected_status):
    if response.status_code != expected_status:
        raise AssertionError(
            f"Status esperado {expected_status}, recebido "
            f"{response.status_code}: {response.get_data(as_text=True)}"
        )
    return response.get_json(silent=True)


def _get_local(client, slug):
    return _assert_status(client.get(f"/locais/{slug}"), 200)


def _cleanup_validation_records():
    with SessionLocal.begin() as session:
        session.execute(
            delete(Avaliacao).where(
                Avaliacao.autor.like(f"{TEST_AUTHOR_PREFIX}%")
            )
        )
        session.execute(
            delete(LocalTuristico).where(
                LocalTuristico.slug.in_(TEST_LOCAL_SLUGS)
            )
        )


def _assert_seed_state():
    with SessionLocal() as session:
        version = session.execute(text("SELECT VERSION()")).scalar_one()
        revision = session.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        local_count = session.scalar(select(func.count(LocalTuristico.id)))
        evaluation_count = session.scalar(select(func.count(Avaliacao.id)))

    if (local_count, evaluation_count) != (6, 6):
        raise AssertionError(
            "O seed deveria produzir seis locais e seis avaliações."
        )
    return version, revision


def _validate_ordering(client):
    average_payload = _assert_status(
        client.get(
            "/locais",
            query_string={
                "ordenar_por": "nota_media_desc",
                "por_pagina": "100",
            },
        ),
        200,
    )
    average_locations = average_payload["locais"]
    if average_locations[-1]["slug"] != "museu-de-arte-moderna":
        raise AssertionError("Local sem avaliação deveria ficar ao final.")
    if average_locations[-1]["nota_media"] is not None:
        raise AssertionError("Local sem avaliação deveria ter média nula.")

    total_payload = _assert_status(
        client.get(
            "/locais",
            query_string={
                "ordenar_por": "total_avaliacoes_desc",
                "por_pagina": "100",
            },
        ),
        200,
    )
    total_locations = total_payload["locais"]
    for previous, current in zip(total_locations, total_locations[1:]):
        if (
            previous["total_avaliacoes"] == current["total_avaliacoes"]
            and previous["id"] >= current["id"]
        ):
            raise AssertionError("O desempate deveria usar id crescente.")


def _validate_aggregates(client):
    created_ids = []
    try:
        for suffix, note in (("mínima", 1), ("máxima", 5)):
            payload = _assert_status(
                client.post(
                    "/locais/museu-de-arte-moderna/avaliacoes",
                    json={
                        "autor": f"{TEST_AUTHOR_PREFIX} {suffix}",
                        "nota": note,
                    },
                ),
                201,
            )
            created_ids.append(payload["id"])

            detail = _get_local(client, "museu-de-arte-moderna")
            expected = (1.0, 1) if len(created_ids) == 1 else (3.0, 2)
            if (detail["nota_media"], detail["total_avaliacoes"]) != expected:
                raise AssertionError("Agregados incorretos após criação.")

        _assert_status(
            client.patch(
                f"/avaliacoes/{created_ids[0]}",
                json={"nota": 3},
            ),
            200,
        )
        detail = _get_local(client, "museu-de-arte-moderna")
        if (detail["nota_media"], detail["total_avaliacoes"]) != (4.0, 2):
            raise AssertionError("Agregados incorretos após atualização.")
    finally:
        for evaluation_id in created_ids:
            response = client.delete(f"/avaliacoes/{evaluation_id}")
            if response.status_code not in {204, 404}:
                _assert_status(response, 204)

    detail = _get_local(client, "museu-de-arte-moderna")
    if (detail["nota_media"], detail["total_avaliacoes"]) != (None, 0):
        raise AssertionError(
            "Agregados incorretos após excluir a última nota."
        )


def _local_payload(slug):
    return {
        "slug": slug,
        "nome": "Mesmo nome para desempate E4",
        "categoria": "mirantes",
        "descricao": "Registro temporário da validação MySQL E4.",
        "cidade": "Rio de Janeiro",
        "bairro": "Centro",
        "regiao": "Centro",
        "imagem": f"/imagens/locais/{slug}.jpg",
        "destaque": False,
        "latitude": -22.9,
        "longitude": -43.2,
    }


def _validate_tiebreak_and_cascade(client):
    created = []
    try:
        for slug in TEST_LOCAL_SLUGS:
            payload = _assert_status(
                client.post("/locais", json=_local_payload(slug)),
                201,
            )
            created.append(payload)

        listing = _assert_status(
            client.get(
                "/locais",
                query_string={
                    "categoria": "mirantes",
                    "ordenar_por": "nome_asc",
                    "por_pagina": "100",
                },
            ),
            200,
        )["locais"]
        temporary = [
            local for local in listing if local["slug"] in TEST_LOCAL_SLUGS
        ]
        if [local["id"] for local in temporary] != sorted(
            local["id"] for local in temporary
        ):
            raise AssertionError(
                "O desempate de nomes deveria usar id crescente."
            )

        evaluation = _assert_status(
            client.post(
                f"/locais/{TEST_LOCAL_SLUGS[0]}/avaliacoes",
                json={"autor": f"{TEST_AUTHOR_PREFIX} cascata", "nota": 4},
            ),
            201,
        )
        _assert_status(client.delete(f"/locais/{TEST_LOCAL_SLUGS[0]}"), 204)

        with SessionLocal() as session:
            if session.get(Avaliacao, evaluation["id"]) is not None:
                raise AssertionError("A cascata deixou uma avaliação órfã.")
        created = [
            local for local in created if local["slug"] != TEST_LOCAL_SLUGS[0]
        ]
    finally:
        for local in created:
            response = client.delete(f"/locais/{local['slug']}")
            if response.status_code not in {204, 404}:
                _assert_status(response, 204)


def _validate_real_rollback():
    session = SessionLocal()

    def fail_after_flush():
        session.flush()
        raise RuntimeError("falha controlada E4")

    try:
        with (
            patch(
                "services.avaliacao_service.SessionLocal",
                return_value=session,
            ),
            patch.object(session, "commit", side_effect=fail_after_flush),
        ):
            try:
                avaliacao_service.criar_avaliacao(
                    "museu-de-arte-moderna",
                    {
                        "autor": f"{TEST_AUTHOR_PREFIX} rollback",
                        "nota": 2,
                        "comentario": None,
                    },
                )
            except RuntimeError as error:
                if str(error) != "falha controlada E4":
                    raise
            else:
                raise AssertionError(
                    "A falha controlada deveria ser propagada."
                )
    finally:
        session.close()

    with SessionLocal() as verification:
        count = verification.scalar(
            select(func.count(Avaliacao.id)).where(
                Avaliacao.autor == f"{TEST_AUTHOR_PREFIX} rollback"
            )
        )
    if count != 0:
        raise AssertionError("O rollback deveria remover a escrita parcial.")


def validate_available_database():
    """Valida migração, seed e fluxos reais no MySQL disponível."""
    if DATABASE_URL.get_backend_name() != "mysql":
        raise RuntimeError("A validação E4 exige uma DATABASE_URL MySQL.")

    app.config.update(TESTING=True)
    client = app.test_client()
    _cleanup_validation_records()
    try:
        version, revision = _assert_seed_state()
        _validate_ordering(client)
        _validate_aggregates(client)
        _validate_tiebreak_and_cascade(client)
        _validate_real_rollback()
    finally:
        _cleanup_validation_records()

    _assert_seed_state()
    print(
        json.dumps(
            {
                "status": "ok",
                "mysql_version": version,
                "alembic_revision": revision,
                "locais": 6,
                "avaliacoes": 6,
                "agregados": "ok",
                "ordenacao_nulos": "ok",
                "desempates": "ok",
                "integridade_referencial": "ok",
                "rollback": "ok",
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def validate_unavailable_database():
    """Confirma o envelope 503 quando o MySQL está indisponível."""
    if DATABASE_URL.get_backend_name() != "mysql":
        raise RuntimeError("A validação E4 exige uma DATABASE_URL MySQL.")

    app.config.update(TESTING=True)
    logger_disabled = app.logger.disabled
    app.logger.disabled = True
    try:
        response = app.test_client().get("/locais")
    finally:
        app.logger.disabled = logger_disabled
    payload = _assert_status(response, 503)
    error = payload["erro"]
    if error["codigo"] != "banco_indisponivel":
        raise AssertionError(
            "A indisponibilidade deveria usar o código público."
        )
    if error["detalhes"] != []:
        raise AssertionError(
            "A resposta 503 não deveria expor detalhes internos."
        )
    if error["requisicao_id"] != response.headers.get("X-Request-ID"):
        raise AssertionError(
            "O identificador de correlação deveria coincidir."
        )

    print(
        json.dumps(
            {
                "status": "ok",
                "http_status": response.status_code,
                "codigo": error["codigo"],
                "detalhes": error["detalhes"],
                "correlacao": "ok",
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def main():
    """Seleciona a validação com banco disponível ou indisponível."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--expect-unavailable", action="store_true")
    arguments = parser.parse_args()

    if arguments.expect_unavailable:
        validate_unavailable_database()
    else:
        validate_available_database()


if __name__ == "__main__":
    main()
