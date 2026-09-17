import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.avaliacao import Avaliacao  # noqa: F401
from models.base import SessionLocal
from models.local_turistico import LocalTuristico

DEFAULT_MANIFEST_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "seed_manifest.json"
)
LOCAL_FIELDS = {
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
}
TEXT_LIMITS = {
    "slug": 120,
    "nome": 120,
    "categoria": 80,
    "descricao": 2000,
    "cidade": 120,
    "bairro": 120,
    "regiao": 80,
    "imagem": 500,
}


EVALUATION_FIELDS = {
    "local_slug",
    "autor",
    "nota",
    "comentario",
    "criado_em",
}
EVALUATION_KEY_FIELDS = (
    "local_slug",
    "autor",
    "criado_em",
    "nota",
    "comentario",
)


class SeedManifestError(ValueError):
    """Indica que o manifesto de seed viola o contrato esperado."""


@dataclass(frozen=True)
class LocalSeedData:
    """Representa os campos persistíveis de um local aprovado."""

    slug: str
    nome: str
    categoria: str
    descricao: str
    cidade: str
    bairro: str
    regiao: str
    imagem: str
    destaque: bool
    latitude: Decimal
    longitude: Decimal


@dataclass(frozen=True)
class LocalSeedResult:
    """Resume o resultado interno da reconciliação de locais."""

    inserted: int
    updated: int
    unchanged: int


@dataclass(frozen=True)
class EvaluationSeedData:
    """Representa uma avaliação aprovada e sua chave determinística."""

    local_slug: str
    autor: str
    nota: int
    comentario: str | None
    criado_em: datetime

    @property
    def reconciliation_key(self) -> tuple[str, str, datetime, int, str | None]:
        """Retorna a chave independente dos identificadores legados."""
        return (
            self.local_slug,
            self.autor,
            self.criado_em,
            self.nota,
            self.comentario,
        )


@dataclass(frozen=True)
class EvaluationSeedResult:
    """Resume o resultado interno da carga de avaliações."""

    inserted: int
    unchanged: int


@dataclass(frozen=True)
class SeedRejection:
    """Representa uma rejeição segura para exposição no relatório."""

    fonte: str
    tipo: str
    codigo: str
    motivo: str


@dataclass(frozen=True)
class SeedResult:
    """Agrupa os resultados internos da carga do manifesto."""

    locations: LocalSeedResult
    evaluations: EvaluationSeedResult
    rejections: tuple[SeedRejection, ...]


def _require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SeedManifestError(f"O campo {field} deve ser um objeto JSON.")
    return value


def _require_text(data: Mapping[str, Any], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise SeedManifestError(
            f"O campo {field} deve ser um texto não vazio."
        )
    if len(value) > TEXT_LIMITS[field]:
        raise SeedManifestError(
            f"O campo {field} excede o limite de "
            f"{TEXT_LIMITS[field]} caracteres."
        )
    return value


def _require_coordinate(data: Mapping[str, Any], field: str) -> Decimal:
    value = data.get(field)
    if isinstance(value, bool):
        raise SeedManifestError(f"O campo {field} deve ser numérico.")
    try:
        coordinate = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise SeedManifestError(
            f"O campo {field} deve ser numérico."
        ) from None

    minimum, maximum = (-90, 90) if field == "latitude" else (-180, 180)
    if not Decimal(minimum) <= coordinate <= Decimal(maximum):
        raise SeedManifestError(
            f"O campo {field} deve estar entre {minimum} e {maximum}."
        )
    return coordinate


def _build_category_map(rules: Mapping[str, Any]) -> dict[str, str]:
    categories = _require_mapping(
        rules.get("categorias"), "regras.locais.categorias"
    )
    category_map: dict[str, str] = {}
    for source, canonical in categories.items():
        if not isinstance(source, str) or not isinstance(canonical, str):
            raise SeedManifestError(
                "As categorias do manifesto devem mapear textos para textos."
            )
        category_map[source.casefold()] = canonical
        category_map[canonical.casefold()] = canonical
    return category_map


def _require_evaluation_text(
    data: Mapping[str, Any],
    field: str,
    maximum_length: int,
) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise SeedManifestError(
            f"O campo {field} da avaliação deve ser um texto não vazio."
        )
    if len(value) > maximum_length:
        raise SeedManifestError(
            f"O campo {field} da avaliação excede o limite de "
            f"{maximum_length} caracteres."
        )
    return value


def _require_utc_datetime(data: Mapping[str, Any]) -> datetime:
    value = data.get("criado_em")
    if not isinstance(value, str) or not value.endswith("Z"):
        raise SeedManifestError(
            "O campo criado_em da avaliação deve ser um instante UTC com Z."
        )
    try:
        created_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise SeedManifestError(
            "O campo criado_em da avaliação deve usar o formato ISO 8601."
        ) from None
    offset = created_at.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise SeedManifestError(
            "O campo criado_em da avaliação deve representar UTC."
        )
    normalized = created_at.astimezone(timezone.utc)
    expected = normalized.isoformat(timespec="seconds").replace("+00:00", "Z")
    if value != expected:
        raise SeedManifestError(
            "O campo criado_em da avaliação deve usar segundos e o sufixo Z."
        )
    return normalized


def _normalize_persisted_datetime(value: datetime) -> datetime:
    """Interpreta DATETIME sem fuso como UTC para reconciliar o seed."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def load_local_seed_data(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> tuple[LocalSeedData, ...]:
    """Carrega e valida os seis locais curados do manifesto."""
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SeedManifestError(
            f"Não foi possível ler o manifesto de seed: {error}."
        ) from error

    root = _require_mapping(manifest, "raiz")
    if root.get("schema_version") != 1:
        raise SeedManifestError("A versão do manifesto de seed deve ser 1.")

    rules = _require_mapping(root.get("regras"), "regras")
    local_rules = _require_mapping(rules.get("locais"), "regras.locais")
    if local_rules.get("chave_reconciliacao") != "slug":
        raise SeedManifestError(
            "A chave de reconciliação dos locais deve ser slug."
        )

    category_map = _build_category_map(local_rules)
    curated_city = local_rules.get("cidade_padrao_curada")
    if not isinstance(curated_city, str) or not curated_city.strip():
        raise SeedManifestError("A cidade padrão curada deve ser informada.")

    sources = _require_mapping(root.get("fontes"), "fontes")
    coordinate_sources = sources.get("coordenadas")
    if not isinstance(coordinate_sources, list):
        raise SeedManifestError(
            "As fontes de coordenadas devem formar uma lista."
        )
    coordinate_source_ids = {
        source.get("id")
        for source in coordinate_sources
        if isinstance(source, Mapping) and isinstance(source.get("id"), str)
    }

    entries = root.get("locais")
    summary = _require_mapping(root.get("resumo"), "resumo")
    if not isinstance(entries, list) or len(entries) != 6:
        raise SeedManifestError(
            "O manifesto deve conter exatamente seis locais."
        )
    if summary.get("locais_aprovados") != len(entries):
        raise SeedManifestError(
            "A contagem de locais aprovados diverge dos registros "
            "do manifesto."
        )

    records: list[LocalSeedData] = []
    slugs: set[str] = set()
    for position, entry in enumerate(entries, start=1):
        entry_data = _require_mapping(entry, f"locais[{position}]")
        origin = _require_mapping(
            entry_data.get("origem"), f"locais[{position}].origem"
        )
        if origin.get("fonte") != "mock_locais":
            raise SeedManifestError(
                f"O local na posição {position} não possui origem aprovada."
            )

        curatorship = _require_mapping(
            entry_data.get("curadoria"),
            f"locais[{position}].curadoria",
        )
        if curatorship.get("coordenadas_fonte") not in coordinate_source_ids:
            raise SeedManifestError(
                f"O local na posição {position} não possui fonte "
                "de coordenadas válida."
            )

        data = _require_mapping(
            entry_data.get("dados"), f"locais[{position}].dados"
        )
        if set(data) != LOCAL_FIELDS:
            raise SeedManifestError(
                f"Os campos persistíveis do local na posição {position} "
                "divergem do contrato."
            )

        texts = {field: _require_text(data, field) for field in TEXT_LIMITS}
        slug = texts["slug"]
        if slug in slugs:
            raise SeedManifestError(
                f"O slug {slug} está duplicado no manifesto."
            )
        slugs.add(slug)

        category = category_map.get(texts["categoria"].casefold())
        if category is None:
            raise SeedManifestError(
                f"A categoria {texts['categoria']} não possui "
                "normalização definida."
            )
        if texts["cidade"] != curated_city:
            raise SeedManifestError(
                f"A cidade do local {slug} diverge da cidade curada aprovada."
            )
        if not texts["imagem"].startswith("/imagens/locais/"):
            raise SeedManifestError(
                f"A imagem do local {slug} não usa o caminho público canônico."
            )
        if type(data.get("destaque")) is not bool:
            raise SeedManifestError(
                f"O destaque do local {slug} deve ser booleano."
            )

        records.append(
            LocalSeedData(
                slug=slug,
                nome=texts["nome"],
                categoria=category,
                descricao=texts["descricao"],
                cidade=texts["cidade"],
                bairro=texts["bairro"],
                regiao=texts["regiao"],
                imagem=texts["imagem"],
                destaque=data["destaque"],
                latitude=_require_coordinate(data, "latitude"),
                longitude=_require_coordinate(data, "longitude"),
            )
        )

    return tuple(records)


def load_evaluation_seed_data(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> tuple[EvaluationSeedData, ...]:
    """Carrega e valida as seis avaliações aprovadas do manifesto."""
    approved_slugs = {
        record.slug for record in load_local_seed_data(manifest_path)
    }
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SeedManifestError(
            f"Não foi possível ler o manifesto de seed: {error}."
        ) from error

    root = _require_mapping(manifest, "raiz")
    rules = _require_mapping(root.get("regras"), "regras")
    evaluation_rules = _require_mapping(
        rules.get("avaliacoes"),
        "regras.avaliacoes",
    )
    if evaluation_rules.get("chave_reconciliacao") != list(
        EVALUATION_KEY_FIELDS
    ):
        raise SeedManifestError(
            "A chave de reconciliação das avaliações diverge do contrato."
        )

    entries = root.get("avaliacoes")
    summary = _require_mapping(root.get("resumo"), "resumo")
    if not isinstance(entries, list) or len(entries) != 6:
        raise SeedManifestError(
            "O manifesto deve conter exatamente seis avaliações."
        )
    if summary.get("avaliacoes_aprovadas") != len(entries):
        raise SeedManifestError(
            "A contagem de avaliações aprovadas diverge dos registros "
            "do manifesto."
        )

    records: list[EvaluationSeedData] = []
    keys: set[tuple[str, str, datetime, int, str | None]] = set()
    for position, entry in enumerate(entries, start=1):
        entry_data = _require_mapping(entry, f"avaliacoes[{position}]")
        origin = _require_mapping(
            entry_data.get("origem"),
            f"avaliacoes[{position}].origem",
        )
        if origin.get("fonte") != "mock_avaliacoes":
            raise SeedManifestError(
                f"A avaliação na posição {position} não possui "
                "origem aprovada."
            )

        data = _require_mapping(
            entry_data.get("dados"),
            f"avaliacoes[{position}].dados",
        )
        if set(data) != EVALUATION_FIELDS:
            raise SeedManifestError(
                f"Os campos persistíveis da avaliação na posição "
                f"{position} divergem do contrato."
            )

        local_slug = _require_evaluation_text(data, "local_slug", 120)
        if local_slug not in approved_slugs:
            raise SeedManifestError(
                f"A avaliação na posição {position} referencia "
                "um local não aprovado."
            )
        author = _require_evaluation_text(data, "autor", 120)
        rating = data.get("nota")
        if type(rating) is not int or not 1 <= rating <= 5:
            raise SeedManifestError(
                f"A nota da avaliação na posição {position} deve "
                "ser um inteiro entre 1 e 5."
            )

        comment = data.get("comentario")
        if comment is not None:
            comment = _require_evaluation_text(data, "comentario", 1000)
        record = EvaluationSeedData(
            local_slug=local_slug,
            autor=author,
            nota=rating,
            comentario=comment,
            criado_em=_require_utc_datetime(data),
        )
        if record.reconciliation_key in keys:
            raise SeedManifestError(
                f"A chave da avaliação na posição {position} "
                "está duplicada no manifesto."
            )
        keys.add(record.reconciliation_key)
        records.append(record)

    return tuple(records)


def load_seed_rejections(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> tuple[SeedRejection, ...]:
    """Carrega somente os campos públicos das rejeições aprovadas."""
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SeedManifestError(
            f"Não foi possível ler o manifesto de seed: {error}."
        ) from error

    root = _require_mapping(manifest, "raiz")
    entries = root.get("rejeicoes")
    if not isinstance(entries, list):
        raise SeedManifestError("As rejeições devem formar uma lista.")

    rejections: list[SeedRejection] = []
    for position, entry in enumerate(entries, start=1):
        data = _require_mapping(entry, f"rejeicoes[{position}]")
        public_fields: dict[str, str] = {}
        for field in ("fonte", "tipo", "codigo", "motivo"):
            value = data.get(field)
            if not isinstance(value, str) or not value.strip():
                raise SeedManifestError(
                    f"O campo {field} da rejeição na posição "
                    f"{position} deve ser um texto não vazio."
                )
            public_fields[field] = value
        if public_fields["tipo"] not in {"local", "avaliacao"}:
            raise SeedManifestError(
                f"O tipo da rejeição na posição {position} é inválido."
            )
        rejections.append(SeedRejection(**public_fields))

    summary = _require_mapping(root.get("resumo"), "resumo")
    local_count = sum(rejection.tipo == "local" for rejection in rejections)
    evaluation_count = sum(
        rejection.tipo == "avaliacao" for rejection in rejections
    )
    if local_count != summary.get("locais_sqlite_rejeitados"):
        raise SeedManifestError(
            "A contagem de locais rejeitados diverge do resumo do manifesto."
        )
    if evaluation_count != summary.get("avaliacoes_sqlite_rejeitadas"):
        raise SeedManifestError(
            "A contagem de avaliações rejeitadas diverge do resumo "
            "do manifesto."
        )
    return tuple(rejections)


def seed_locations(
    session: Session,
    records: tuple[LocalSeedData, ...],
) -> LocalSeedResult:
    """Insere ou atualiza locais usando o slug como chave estável."""
    inserted = updated = unchanged = 0
    for record in records:
        values = asdict(record)
        local = session.scalar(
            select(LocalTuristico).where(LocalTuristico.slug == record.slug)
        )
        if local is None:
            session.add(LocalTuristico(**values))
            inserted += 1
            continue

        changed = any(
            getattr(local, field) != value for field, value in values.items()
        )
        if not changed:
            unchanged += 1
            continue

        for field, value in values.items():
            setattr(local, field, value)
        updated += 1

    return LocalSeedResult(
        inserted=inserted,
        updated=updated,
        unchanged=unchanged,
    )


def seed_evaluations(
    session: Session,
    records: tuple[EvaluationSeedData, ...],
) -> EvaluationSeedResult:
    """Insere avaliações ausentes pela chave determinística aprovada."""
    session.flush()
    slugs = {record.local_slug for record in records}
    locations = session.scalars(
        select(LocalTuristico).where(LocalTuristico.slug.in_(slugs))
    ).all()
    locations_by_slug = {local.slug: local for local in locations}
    missing_slugs = slugs - locations_by_slug.keys()
    if missing_slugs:
        raise SeedManifestError(
            "Não foi possível resolver os locais das avaliações: "
            + ", ".join(sorted(missing_slugs))
            + "."
        )

    slugs_by_local_id = {
        local.id: local.slug for local in locations_by_slug.values()
    }
    existing_evaluations = session.scalars(
        select(Avaliacao).where(Avaliacao.local_id.in_(slugs_by_local_id))
    ).all()
    existing_keys = {
        (
            slugs_by_local_id[evaluation.local_id],
            evaluation.autor,
            _normalize_persisted_datetime(evaluation.criado_em),
            evaluation.nota,
            evaluation.comentario,
        )
        for evaluation in existing_evaluations
    }

    inserted = unchanged = 0
    for record in records:
        if record.reconciliation_key in existing_keys:
            unchanged += 1
            continue
        local = locations_by_slug[record.local_slug]
        session.add(
            Avaliacao(
                autor=record.autor,
                nota=record.nota,
                comentario=record.comentario,
                criado_em=record.criado_em,
                local_id=local.id,
            )
        )
        existing_keys.add(record.reconciliation_key)
        inserted += 1

    return EvaluationSeedResult(inserted=inserted, unchanged=unchanged)


def run_location_seed(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> LocalSeedResult:
    """Executa a carga dos locais em uma única transação."""
    records = load_local_seed_data(manifest_path)
    with SessionLocal.begin() as session:
        return seed_locations(session, records)


def run_seed(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> SeedResult:
    """Carrega locais e avaliações em uma única transação."""
    locations = load_local_seed_data(manifest_path)
    evaluations = load_evaluation_seed_data(manifest_path)
    rejections = load_seed_rejections(manifest_path)
    with SessionLocal.begin() as session:
        location_result = seed_locations(session, locations)
        evaluation_result = seed_evaluations(session, evaluations)
    return SeedResult(
        locations=location_result,
        evaluations=evaluation_result,
        rejections=rejections,
    )


def build_seed_report(result: SeedResult) -> dict[str, Any]:
    """Monta um relatório sem identificadores ou configuração sensível."""
    local_rejections = sum(
        rejection.tipo == "local" for rejection in result.rejections
    )
    evaluation_rejections = sum(
        rejection.tipo == "avaliacao" for rejection in result.rejections
    )
    entities = {
        "locais": {
            "inseridos": result.locations.inserted,
            "atualizados": result.locations.updated,
            "ignorados": result.locations.unchanged,
            "rejeitados": local_rejections,
        },
        "avaliacoes": {
            "inseridos": result.evaluations.inserted,
            "atualizados": 0,
            "ignorados": result.evaluations.unchanged,
            "rejeitados": evaluation_rejections,
        },
    }
    return {
        "resultado": "concluido",
        "totais": {
            "inseridos": sum(
                entity["inseridos"] for entity in entities.values()
            ),
            "atualizados": sum(
                entity["atualizados"] for entity in entities.values()
            ),
            "ignorados": sum(
                entity["ignorados"] for entity in entities.values()
            ),
            "rejeitados": len(result.rejections),
        },
        "entidades": entities,
        "rejeicoes": [asdict(rejection) for rejection in result.rejections],
    }


def format_seed_report(result: SeedResult) -> str:
    """Serializa o relatório de seed como JSON UTF-8 determinístico."""
    return json.dumps(
        build_seed_report(result),
        ensure_ascii=False,
        indent=2,
    )


def main() -> None:
    """Executa a etapa atual do seed pela linha de comando."""
    print(format_seed_report(run_seed()))


if __name__ == "__main__":
    main()
