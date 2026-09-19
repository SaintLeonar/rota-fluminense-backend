"""Valida artefatos estáticos, links e contrato OpenAPI da fase E5."""

import json
import os
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs" / "CONTRATO_API.md"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
CLIMATE_OPERATION = ("GET", "/locais/{slug}/clima")
CLIMATE_SUCCESS_EXAMPLES = {"provedor", "cacheValido"}
CLIMATE_ERROR_EXAMPLES = {
    "bancoIndisponivel",
    "coordenadasIndisponiveis",
    "climaIndisponivel",
}

EXPECTED_RESPONSES = {
    ("GET", "/locais"): {"200", "400", "500", "503"},
    ("POST", "/locais"): {"201", "400", "409", "500", "503"},
    ("GET", "/locais/{slug}"): {"200", "400", "404", "500", "503"},
    CLIMATE_OPERATION: {"200", "400", "404", "500", "503"},
    ("PUT", "/locais/{slug}"): {"200", "400", "404", "500", "503"},
    ("DELETE", "/locais/{slug}"): {
        "204",
        "400",
        "404",
        "500",
        "503",
    },
    ("GET", "/locais/{slug}/avaliacoes"): {
        "200",
        "400",
        "404",
        "500",
        "503",
    },
    ("POST", "/locais/{slug}/avaliacoes"): {
        "201",
        "400",
        "404",
        "500",
        "503",
    },
    ("PATCH", "/avaliacoes/{avaliacao_id}"): {
        "200",
        "400",
        "404",
        "500",
        "503",
    },
    ("DELETE", "/avaliacoes/{avaliacao_id}"): {
        "204",
        "400",
        "404",
        "500",
        "503",
    },
}

EXPECTED_SUCCESS_SCHEMAS = {
    ("GET", "/locais"): ("200", "LocalListSchema"),
    ("POST", "/locais"): ("201", "LocalSchema"),
    ("GET", "/locais/{slug}"): ("200", "LocalDetalhadoSchema"),
    CLIMATE_OPERATION: ("200", "ClimaResponseSchema"),
    ("PUT", "/locais/{slug}"): ("200", "LocalSchema"),
    ("GET", "/locais/{slug}/avaliacoes"): (
        "200",
        "AvaliacaoListSchema",
    ),
    ("POST", "/locais/{slug}/avaliacoes"): (
        "201",
        "AvaliacaoSchema",
    ),
    ("PATCH", "/avaliacoes/{avaliacao_id}"): (
        "200",
        "AvaliacaoSchema",
    ),
}

EXPECTED_REQUEST_SCHEMAS = {
    ("POST", "/locais"): "LocalInputSchema",
    ("PUT", "/locais/{slug}"): "LocalUpdateSchema",
    ("POST", "/locais/{slug}/avaliacoes"): "AvaliacaoInputSchema",
    ("PATCH", "/avaliacoes/{avaliacao_id}"): "AvaliacaoUpdateSchema",
}

EXPECTED_SCHEMA_FIELDS = {
    "LocalSchema": {
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
    "AvaliacaoSchema": {
        "id",
        "local_id",
        "autor",
        "nota",
        "comentario",
        "criado_em",
    },
    "ErrorContentSchema": {
        "codigo",
        "mensagem",
        "detalhes",
        "requisicao_id",
    },
    "ClimaLocalSchema": {"slug", "nome"},
    "ClimaAtualSchema": {
        "observado_em",
        "temperatura_c",
        "sensacao_termica_c",
        "precipitacao_mm",
        "velocidade_vento_kmh",
        "codigo_meteorologico",
        "descricao",
        "icone",
    },
    "ClimaPrevisaoDiariaSchema": {
        "data",
        "temperatura_max_c",
        "temperatura_min_c",
        "probabilidade_precipitacao_max_pct",
        "codigo_meteorologico",
        "descricao",
        "icone",
    },
    "ClimaCacheSchema": {"utilizado", "expira_em"},
    "ClimaResponseSchema": {
        "local",
        "timezone",
        "atual",
        "previsao",
        "atualizado_em",
        "cache",
    },
}


class ArtifactValidationError(RuntimeError):
    """Indica uma divergência encontrada pela auditoria E5."""


def _project_files(pattern):
    return sorted(
        path
        for path in ROOT.rglob(pattern)
        if not any(
            part in {".git", ".venv", "__pycache__"} for part in path.parts
        )
    )


def _validate_json_files():
    files = _project_files("*.json")
    for path in files:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            relative = path.relative_to(ROOT)
            raise ArtifactValidationError(
                f"JSON inválido em {relative}: {error}"
            ) from error
    return len(files)


def _markdown_anchor(heading):
    normalized = unicodedata.normalize("NFC", heading.strip().casefold())
    return re.sub(r"[^\w\- ]", "", normalized).replace(" ", "-")


def _heading_anchors(path):
    anchors = set()
    counts = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if not match:
            continue
        base = _markdown_anchor(match.group(1))
        count = counts.get(base, 0)
        counts[base] = count + 1
        anchors.add(base if count == 0 else f"{base}-{count}")
    return anchors


def _validate_markdown_links():
    files = _project_files("*.md")
    link_count = 0
    failures = []
    link_pattern = re.compile(r"(?<!!)\[[^]]+\]\(([^)]+)\)")

    for source in files:
        content = source.read_text(encoding="utf-8")
        for raw_target in link_pattern.findall(content):
            target = raw_target.strip().strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or target.startswith("//"):
                continue

            link_count += 1
            relative_target = unquote(parsed.path)
            destination = (
                source
                if not relative_target
                else (source.parent / relative_target).resolve()
            )

            try:
                destination.relative_to(ROOT)
            except ValueError:
                failures.append(
                    f"{source.relative_to(ROOT)} -> {target} (fora do projeto)"
                )
                continue

            if not destination.exists():
                failures.append(
                    f"{source.relative_to(ROOT)} -> {target} (inexistente)"
                )
                continue

            if parsed.fragment and destination.suffix.casefold() == ".md":
                anchor = unquote(parsed.fragment).casefold()
                if anchor not in _heading_anchors(destination):
                    failures.append(
                        f"{source.relative_to(ROOT)} -> {target} "
                        "(âncora inexistente)"
                    )

    if failures:
        raise ArtifactValidationError(
            "Links Markdown inválidos:\n- " + "\n- ".join(failures)
        )
    return len(files), link_count


def _contract_operations():
    content = CONTRACT_PATH.read_text(encoding="utf-8")
    section = content.split("## Matriz canônica de rotas do Dia 3", 1)[1]
    section = section.split("\n## ", 1)[0]
    pattern = re.compile(
        r"^\| `(?P<method>GET|POST|PUT|PATCH|DELETE)` "
        r"\| `(?P<path>/[^`]+)` .* \| `(?P<status>\d{3})` \|$",
        re.MULTILINE,
    )
    operations = {}
    for match in pattern.finditer(section):
        path = re.sub(r"<([^>]+)>", r"{\1}", match.group("path"))
        operations[(match.group("method"), path)] = match.group("status")

    climate_heading = "## Clima do local — implementado no Dia 4"
    if climate_heading not in content:
        raise ArtifactValidationError(
            "A seção contratual de clima do Dia 4 está ausente."
        )
    operations[CLIMATE_OPERATION] = "200"
    return operations


def _schema_reference(container):
    try:
        reference = container["content"]["application/json"]["schema"]["$ref"]
    except KeyError as error:
        raise ArtifactValidationError(
            "O OpenAPI não contém a referência de schema esperada."
        ) from error
    return reference.rsplit("/", 1)[-1]


def _openapi_operations(specification):
    operations = {}
    for path, path_item in specification["paths"].items():
        if path == "/":
            continue
        for method, operation in path_item.items():
            if method.casefold() in HTTP_METHODS:
                operations[(method.upper(), path)] = operation
    return operations


def _validate_openapi_contract():
    os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    from app import app

    response = app.test_client().get("/openapi/openapi.json")
    if (
        response.status_code != 200
        or response.content_type != "application/json"
    ):
        raise ArtifactValidationError(
            "O documento OpenAPI não respondeu JSON 200."
        )

    specification = response.get_json()
    operations = _openapi_operations(specification)
    contract = _contract_operations()

    if set(operations) != set(contract):
        raise ArtifactValidationError(
            "A matriz de operações do Swagger diverge do contrato."
        )
    for key, success_status in contract.items():
        if success_status not in operations[key]["responses"]:
            raise ArtifactValidationError(
                f"Resposta de sucesso ausente no Swagger: {key}."
            )

    for key, expected in EXPECTED_RESPONSES.items():
        actual = set(operations[key]["responses"])
        if actual != expected:
            raise ArtifactValidationError(
                f"Respostas divergentes em {key}: {sorted(actual)}."
            )

    for key, (status, schema) in EXPECTED_SUCCESS_SCHEMAS.items():
        actual = _schema_reference(operations[key]["responses"][status])
        if actual != schema:
            raise ArtifactValidationError(
                f"Schema de sucesso divergente em {key}: {actual}."
            )

    for key, schema in EXPECTED_REQUEST_SCHEMAS.items():
        actual = _schema_reference(operations[key]["requestBody"])
        if actual != schema:
            raise ArtifactValidationError(
                f"Schema de entrada divergente em {key}: {actual}."
            )

    query_parameters = operations[("GET", "/locais")]["parameters"]
    query_names = {parameter["name"] for parameter in query_parameters}
    expected_query_names = {
        "cidade",
        "categoria",
        "destaque",
        "pagina",
        "por_pagina",
        "ordenar_por",
    }
    if query_names != expected_query_names:
        raise ArtifactValidationError("Parâmetros de GET /locais divergentes.")

    ordering = next(
        parameter
        for parameter in query_parameters
        if parameter["name"] == "ordenar_por"
    )
    if set(ordering["schema"]["enum"]) != {
        "nome_asc",
        "nome_desc",
        "nota_media_desc",
        "total_avaliacoes_desc",
        "destaque_desc",
    }:
        raise ArtifactValidationError("Ordenações divergentes no Swagger.")

    schemas = specification["components"]["schemas"]
    for schema, expected_fields in EXPECTED_SCHEMA_FIELDS.items():
        actual_fields = set(schemas[schema]["properties"])
        if actual_fields != expected_fields:
            raise ArtifactValidationError(
                f"Campos divergentes no schema {schema}."
            )

    for operation in operations.values():
        for status, response_definition in operation["responses"].items():
            if status.startswith(("4", "5")):
                if _schema_reference(response_definition) != "ErrorSchema":
                    raise ArtifactValidationError(
                        "Resposta de erro sem o ErrorSchema canônico."
                    )

    climate_responses = operations[CLIMATE_OPERATION]["responses"]
    success_media = climate_responses["200"]["content"]["application/json"]
    if set(success_media.get("examples", {})) != CLIMATE_SUCCESS_EXAMPLES:
        raise ArtifactValidationError(
            "Exemplos de sucesso climático divergentes no Swagger."
        )
    provider = success_media["examples"]["provedor"]["value"]
    cached = success_media["examples"]["cacheValido"]["value"]
    if provider["cache"]["utilizado"] is not False:
        raise ArtifactValidationError(
            "O exemplo do provedor deve informar cache não utilizado."
        )
    if cached["cache"]["utilizado"] is not True:
        raise ArtifactValidationError(
            "O exemplo de cache deve informar cache utilizado."
        )

    error_media = climate_responses["503"]["content"]["application/json"]
    if set(error_media.get("examples", {})) != CLIMATE_ERROR_EXAMPLES:
        raise ArtifactValidationError(
            "Exemplos de indisponibilidade climática divergentes."
        )

    return len(operations), len(schemas)


def validate_artifacts():
    """Executa todas as verificações estáticas e retorna o resumo."""
    json_count = _validate_json_files()
    markdown_count, link_count = _validate_markdown_links()
    operation_count, schema_count = _validate_openapi_contract()
    return {
        "status": "ok",
        "json_files": json_count,
        "markdown_files": markdown_count,
        "markdown_links": link_count,
        "openapi_operations": operation_count,
        "openapi_schemas": schema_count,
        "contract_divergences": 0,
    }


def main():
    """Executa a auditoria E5 e imprime um resumo JSON seguro."""
    print(json.dumps(validate_artifacts(), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
