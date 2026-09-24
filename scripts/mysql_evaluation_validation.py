"""Valida avaliações, agregados e integridade transacional no MySQL."""

from datetime import datetime
from unittest.mock import patch

from sqlalchemy import delete, func, select
from sqlalchemy.exc import DBAPIError

from models.avaliacao import Avaliacao
from models.base import SessionLocal
from services import avaliacao_service

TARGET_SLUG = "museu-de-arte-moderna"
AUTHOR_PREFIX = "Validação MySQL B6"
EVALUATION_RESPONSE_FIELDS = frozenset(
    {
        "id",
        "local_id",
        "autor",
        "nota",
        "comentario",
        "criado_em",
    }
)


def _assert_status(response, expected_status):
    if response.status_code != expected_status:
        raise AssertionError(
            f"Status esperado {expected_status}, recebido "
            f"{response.status_code}: {response.get_data(as_text=True)}"
        )
    return response.get_json(silent=True)


def _parse_utc_instant(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise AssertionError("criado_em não retornou em UTC com Z.")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise AssertionError("O instante da avaliação não está em UTC.")
    return parsed


def _assert_evaluation(payload, *, author, note, comment):
    if set(payload) != EVALUATION_RESPONSE_FIELDS:
        raise AssertionError("A avaliação não contém os seis campos públicos.")
    if payload["autor"] != author:
        raise AssertionError("O autor retornado diverge do valor persistido.")
    if payload["nota"] != note:
        raise AssertionError("A nota retornada diverge do valor persistido.")
    if payload["comentario"] != comment:
        raise AssertionError("O comentário retornado é divergente.")
    if not isinstance(payload["id"], int) or payload["id"] <= 0:
        raise AssertionError("O identificador da avaliação é inválido.")
    if not isinstance(payload["local_id"], int) or payload["local_id"] <= 0:
        raise AssertionError("O vínculo público da avaliação é inválido.")
    _parse_utc_instant(payload["criado_em"])


def _cleanup_records():
    with SessionLocal.begin() as session:
        session.execute(
            delete(Avaliacao).where(Avaliacao.autor.like(f"{AUTHOR_PREFIX}%"))
        )


def _assert_aggregate(client, average, total):
    detail = _assert_status(client.get(f"/locais/{TARGET_SLUG}"), 200)
    if (detail["nota_media"], detail["total_avaliacoes"]) != (
        average,
        total,
    ):
        raise AssertionError("Os agregados da avaliação estão incorretos.")


def _validate_foreign_key():
    invalid_author = f"{AUTHOR_PREFIX} vínculo inválido"
    try:
        with SessionLocal.begin() as session:
            session.add(
                Avaliacao(
                    autor=invalid_author,
                    nota=3,
                    comentario=None,
                    local_id=2147483647,
                )
            )
    except DBAPIError as error:
        error_args = getattr(error.orig, "args", ())
        error_code = error_args[0] if error_args else None
        if error_code != 1452:
            raise AssertionError(
                "A chave estrangeira retornou código inesperado."
            ) from error
    else:
        raise AssertionError("O MySQL aceitou uma avaliação órfã.")

    invalid_author_filter = Avaliacao.autor == invalid_author
    with SessionLocal() as session:
        residual = session.scalar(
            select(func.count(Avaliacao.id)).where(invalid_author_filter)
        )
    if residual != 0:
        raise AssertionError("A avaliação órfã rejeitada deixou resíduo.")


def _validate_rollback():
    author = f"{AUTHOR_PREFIX} rollback"
    session = SessionLocal()

    def fail_after_flush():
        session.flush()
        raise RuntimeError("falha controlada MySQL B6")

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
                    TARGET_SLUG,
                    {
                        "autor": author,
                        "nota": 2,
                        "comentario": None,
                    },
                )
            except RuntimeError as error:
                if str(error) != "falha controlada MySQL B6":
                    raise
            else:
                raise AssertionError("A falha controlada deveria propagar.")
    finally:
        session.close()

    with SessionLocal() as verification:
        residual = verification.scalar(
            select(func.count(Avaliacao.id)).where(Avaliacao.autor == author)
        )
    if residual != 0:
        raise AssertionError("O rollback deixou uma escrita parcial.")


def validate_evaluations(client):
    """Valida CRUD, UTC, comentário nulo, agregados, FK e rollback."""
    first_author = f"{AUTHOR_PREFIX} primeira"
    second_author = f"{AUTHOR_PREFIX} segunda"
    created_ids = []
    _cleanup_records()
    try:
        _assert_aggregate(client, None, 0)
        first = _assert_status(
            client.post(
                f"/locais/{TARGET_SLUG}/avaliacoes",
                json={"autor": first_author, "nota": 1},
            ),
            201,
        )
        _assert_evaluation(
            first,
            author=first_author,
            note=1,
            comment=None,
        )
        created_ids.append(first["id"])

        second = _assert_status(
            client.post(
                f"/locais/{TARGET_SLUG}/avaliacoes",
                json={
                    "autor": second_author,
                    "nota": 5,
                    "comentario": "Comentário temporário da fase B6.",
                },
            ),
            201,
        )
        _assert_evaluation(
            second,
            author=second_author,
            note=5,
            comment="Comentário temporário da fase B6.",
        )
        created_ids.append(second["id"])
        if first["local_id"] != second["local_id"]:
            raise AssertionError("As avaliações não apontam ao mesmo local.")
        _assert_aggregate(client, 3.0, 2)

        listing = _assert_status(
            client.get(f"/locais/{TARGET_SLUG}/avaliacoes"),
            200,
        )["avaliacoes"]
        if [item["id"] for item in listing] != [second["id"], first["id"]]:
            raise AssertionError("A listagem não preservou a ordem canônica.")

        first_updated = _assert_status(
            client.patch(
                f"/avaliacoes/{first['id']}",
                json={
                    "nota": 3,
                    "comentario": "Comentário atualizado na fase B6.",
                },
            ),
            200,
        )
        _assert_evaluation(
            first_updated,
            author=first_author,
            note=3,
            comment="Comentário atualizado na fase B6.",
        )
        if first_updated["criado_em"] != first["criado_em"]:
            raise AssertionError("A atualização alterou criado_em.")

        second_updated = _assert_status(
            client.patch(
                f"/avaliacoes/{second['id']}",
                json={"comentario": None},
            ),
            200,
        )
        _assert_evaluation(
            second_updated,
            author=second_author,
            note=5,
            comment=None,
        )
        _assert_aggregate(client, 4.0, 2)

        _assert_status(client.delete(f"/avaliacoes/{first['id']}"), 204)
        created_ids.remove(first["id"])
        _assert_aggregate(client, 5.0, 1)

        _assert_status(client.delete(f"/avaliacoes/{second['id']}"), 204)
        created_ids.remove(second["id"])
        _assert_aggregate(client, None, 0)
        empty = _assert_status(
            client.get(f"/locais/{TARGET_SLUG}/avaliacoes"),
            200,
        )
        if empty != {"avaliacoes": []}:
            raise AssertionError("A coleção final não ficou vazia.")

        _validate_foreign_key()
        _validate_rollback()
    finally:
        for evaluation_id in created_ids:
            response = client.delete(f"/avaliacoes/{evaluation_id}")
            if response.status_code not in {204, 404}:
                _assert_status(response, 204)
        _cleanup_records()
