"""Executa a suíte reproduzível de validação integrada em MySQL."""

import argparse

from sqlalchemy import delete, func, select, text

import scripts.mysql_climate_validation as climate_validation
import scripts.mysql_evaluation_validation as evaluation_validation
import scripts.mysql_integration_suite as mysql_integration_suite
import scripts.mysql_listing_validation as listing_validation
import scripts.mysql_local_validation as mysql_local_validation
from app import app
from models.avaliacao import Avaliacao
from models.base import DATABASE_URL, SessionLocal
from models.local_turistico import LocalTuristico
from scripts import seed

EXPECTED_SEED_COUNTS = (6, 6)
VALIDATION_AUTHOR_PREFIX = "Validação MySQL"
VALIDATION_LOCAL_SLUGS = ("validacao-mysql-a", "validacao-mysql-b")


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
                Avaliacao.autor.like(f"{VALIDATION_AUTHOR_PREFIX}%")
            )
        )
        session.execute(
            delete(LocalTuristico).where(
                LocalTuristico.slug.in_(VALIDATION_LOCAL_SLUGS)
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

    if (local_count, evaluation_count) != EXPECTED_SEED_COUNTS:
        raise AssertionError("O estado do seed está incorreto.")
    return version, revision


def _validate_seed_idempotence():
    result = seed.run_seed()
    report = seed.build_seed_report(result)
    expected_totals = {
        "inseridos": 0,
        "atualizados": 0,
        "ignorados": 12,
        "rejeitados": 5,
    }
    if report["totais"] != expected_totals:
        raise AssertionError("A segunda execução do seed não foi idempotente.")


def _available_database_cases(client):
    validation_case = mysql_integration_suite.ValidationCase
    filters_validator = listing_validation.validate_filters_and_pagination
    return (
        validation_case("seed_idempotente", _validate_seed_idempotence),
        validation_case(
            "crud_locais",
            lambda: mysql_local_validation.validate_local_crud(client),
        ),
        validation_case(
            "filtros_paginacao",
            lambda: filters_validator(client),
        ),
        validation_case(
            "ordenacoes",
            lambda: listing_validation.validate_orderings(client),
        ),
        validation_case(
            "avaliacoes",
            lambda: evaluation_validation.validate_evaluations(client),
        ),
        validation_case(
            "clima",
            lambda: climate_validation.validate_climate(app, client),
        ),
    )


def validate_available_database():
    """Valida migração, seed e casos registrados no MySQL disponível."""
    if DATABASE_URL.get_backend_name() != "mysql":
        raise RuntimeError("A validação exige uma DATABASE_URL MySQL.")

    app.config.update(TESTING=True)
    client = app.test_client()
    _cleanup_validation_records()
    try:
        version, revision = _assert_seed_state()
        case_results = mysql_integration_suite.run_validation_cases(
            _available_database_cases(client)
        )
    finally:
        _cleanup_validation_records()

    _assert_seed_state()
    mysql_integration_suite.print_validation_report(
        {
            "banco": {"motor": "mysql", "versao": version},
            "casos": case_results,
            "migracao": {"revisao": revision},
            "schema_relatorio": 1,
            "seed": {"avaliacoes": 6, "locais": 6},
            "status": "ok",
        }
    )


def validate_unavailable_database():
    """Confirma o envelope seguro quando o MySQL está indisponível."""
    if DATABASE_URL.get_backend_name() != "mysql":
        raise RuntimeError("A validação exige uma DATABASE_URL MySQL.")

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
        raise AssertionError("A indisponibilidade exige o código público.")
    if error["detalhes"] != []:
        raise AssertionError("A resposta 503 expôs detalhes internos.")
    if error["requisicao_id"] != response.headers.get("X-Request-ID"):
        raise AssertionError("O identificador de correlação deve coincidir.")

    mysql_integration_suite.print_validation_report(
        {
            "casos": [{"nome": "banco_indisponivel", "status": "ok"}],
            "erro_publico": {
                "codigo": error["codigo"],
                "correlacao": "ok",
                "detalhes": error["detalhes"],
                "http_status": response.status_code,
            },
            "schema_relatorio": 1,
            "status": "ok",
        }
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
