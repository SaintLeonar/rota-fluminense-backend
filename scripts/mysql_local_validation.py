"""Valida o ciclo completo de locais turísticos no MySQL."""

from sqlalchemy import delete, func, select
from sqlalchemy.exc import DBAPIError

from models.avaliacao import Avaliacao
from models.base import SessionLocal
from models.local_turistico import LocalTuristico

CRUD_LOCAL_SLUG = "validacao-mysql-crud"
INVALID_LATITUDE_SLUG = "validacao-mysql-latitude-invalida"
MISSING_NAME_SLUG = "validacao-mysql-nome-ausente"
TEMPORARY_LOCAL_SLUGS = (
    CRUD_LOCAL_SLUG,
    INVALID_LATITUDE_SLUG,
    MISSING_NAME_SLUG,
)
VALIDATION_AUTHOR = "Validação MySQL CRUD"
LOCAL_RESPONSE_FIELDS = frozenset(
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
    }
)


def _assert_status(response, expected_status):
    if response.status_code != expected_status:
        raise AssertionError(
            f"Status esperado {expected_status}, recebido "
            f"{response.status_code}: {response.get_data(as_text=True)}"
        )
    return response.get_json(silent=True)


def _create_payload(slug=CRUD_LOCAL_SLUG):
    return {
        "slug": slug,
        "nome": "Local temporário da validação MySQL",
        "categoria": "mirantes",
        "descricao": "Registro exclusivo do ciclo CRUD integrado.",
        "cidade": "Rio de Janeiro",
        "bairro": "Centro",
        "regiao": "Centro",
        "imagem": "/imagens/locais/validacao-mysql-crud.jpg",
        "destaque": False,
        "latitude": -22.9,
        "longitude": -43.2,
    }


def _update_payload():
    return {
        "nome": "Local temporário atualizado no MySQL",
        "categoria": "museus",
        "descricao": "Registro substituído integralmente no banco real.",
        "cidade": "Niterói",
        "bairro": "Icaraí",
        "regiao": "Região Metropolitana",
        "imagem": "/imagens/locais/validacao-mysql-atualizada.jpg",
        "destaque": True,
        "latitude": -22.9068,
        "longitude": -43.1729,
    }


def _expected_response(local_id, mutable_payload):
    return {
        "id": local_id,
        "slug": CRUD_LOCAL_SLUG,
        **mutable_payload,
        "nota_media": None,
        "total_avaliacoes": 0,
    }


def _assert_local_response(payload, expected):
    if set(payload) != LOCAL_RESPONSE_FIELDS:
        raise AssertionError("A resposta do local não contém os 14 campos.")
    if payload != expected:
        raise AssertionError("A resposta do local diverge do estado esperado.")


def _cleanup_temporary_records():
    with SessionLocal.begin() as session:
        evaluation_filter = Avaliacao.autor == VALIDATION_AUTHOR
        local_filter = LocalTuristico.slug.in_(TEMPORARY_LOCAL_SLUGS)
        session.execute(delete(Avaliacao).where(evaluation_filter))
        session.execute(delete(LocalTuristico).where(local_filter))


def _assert_integrity_rejected(payload, rule_name, expected_error_code):
    try:
        with SessionLocal.begin() as session:
            session.add(LocalTuristico(**payload))
    except DBAPIError as error:
        error_args = getattr(error.orig, "args", ())
        error_code = error_args[0] if error_args else None
        if error_code != expected_error_code:
            raise AssertionError(
                f"A restrição {rule_name} retornou código inesperado."
            ) from error
        return
    raise AssertionError(f"O MySQL não aplicou a restrição {rule_name}.")


def _validate_database_constraints():
    duplicate_payload = _create_payload()
    _assert_integrity_rejected(duplicate_payload, "unique de slug", 1062)

    invalid_latitude = _create_payload(INVALID_LATITUDE_SLUG)
    invalid_latitude["latitude"] = 91
    _assert_integrity_rejected(invalid_latitude, "check de latitude", 3819)

    missing_name = _create_payload(MISSING_NAME_SLUG)
    missing_name["nome"] = None
    _assert_integrity_rejected(missing_name, "not null de nome", 1048)

    invalid_slugs = (INVALID_LATITUDE_SLUG, MISSING_NAME_SLUG)
    with SessionLocal() as session:
        invalid_count = session.scalar(
            select(func.count(LocalTuristico.id)).where(
                LocalTuristico.slug.in_(invalid_slugs)
            )
        )
    if invalid_count != 0:
        raise AssertionError("Uma escrita rejeitada deixou resíduo no MySQL.")


def _validate_deleted_state(local_id, evaluation_id):
    with SessionLocal() as session:
        local = session.get(LocalTuristico, local_id)
        evaluation = session.get(Avaliacao, evaluation_id)
    if local is not None:
        raise AssertionError("O local excluído permaneceu no MySQL.")
    if evaluation is not None:
        raise AssertionError("A cascata deixou uma avaliação órfã.")


def validate_local_crud(client):
    """Valida CRUD, contrato, conflito e restrições reais de local."""
    _cleanup_temporary_records()
    try:
        create_payload = _create_payload()
        created = _assert_status(
            client.post("/locais", json=create_payload),
            201,
        )
        local_id = created["id"]
        expected_created = _expected_response(local_id, create_payload)
        _assert_local_response(created, expected_created)

        detail = _assert_status(client.get(f"/locais/{CRUD_LOCAL_SLUG}"), 200)
        _assert_local_response(detail, expected_created)

        conflict = _assert_status(
            client.post("/locais", json=create_payload),
            409,
        )
        if conflict["erro"]["codigo"] != "slug_ja_existente":
            raise AssertionError("O conflito não usou o código canônico.")

        _validate_database_constraints()

        update_payload = _update_payload()
        updated = _assert_status(
            client.put(
                f"/locais/{CRUD_LOCAL_SLUG}",
                json=update_payload,
            ),
            200,
        )
        expected_updated = _expected_response(local_id, update_payload)
        _assert_local_response(updated, expected_updated)
        persisted = _assert_status(
            client.get(f"/locais/{CRUD_LOCAL_SLUG}"),
            200,
        )
        _assert_local_response(persisted, expected_updated)

        evaluation = _assert_status(
            client.post(
                f"/locais/{CRUD_LOCAL_SLUG}/avaliacoes",
                json={"autor": VALIDATION_AUTHOR, "nota": 4},
            ),
            201,
        )
        with_aggregate = _assert_status(
            client.get(f"/locais/{CRUD_LOCAL_SLUG}"),
            200,
        )
        expected_updated["nota_media"] = 4.0
        expected_updated["total_avaliacoes"] = 1
        _assert_local_response(with_aggregate, expected_updated)

        _assert_status(client.delete(f"/locais/{CRUD_LOCAL_SLUG}"), 204)
        missing = _assert_status(
            client.get(f"/locais/{CRUD_LOCAL_SLUG}"),
            404,
        )
        if missing["erro"]["codigo"] != "local_nao_encontrado":
            raise AssertionError("A exclusão não produziu o erro canônico.")
        _validate_deleted_state(local_id, evaluation["id"])
    finally:
        _cleanup_temporary_records()
