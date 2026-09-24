from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from models.avaliacao import Avaliacao
    from models.local_turistico import LocalTuristico


def _obter_campo(registro: Any, campo: str) -> Any:
    if isinstance(registro, Mapping):
        return registro[campo]
    return getattr(registro, campo)


def _obter_campo_opcional(
    registro: Any,
    campo: str,
    padrao: Any,
) -> Any:
    if isinstance(registro, Mapping):
        return registro.get(campo, padrao)
    return getattr(registro, campo, padrao)


def _serializar_instante_utc(instante: datetime) -> str:
    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=timezone.utc)
    else:
        instante = instante.astimezone(timezone.utc)

    return instante.isoformat().replace("+00:00", "Z")


def serializar_local(
    local: LocalTuristico | Mapping[str, Any],
) -> dict[str, Any]:
    """Serializa todos os campos públicos de um local turístico."""
    nota_media = _obter_campo_opcional(local, "nota_media", None)

    return {
        "id": _obter_campo(local, "id"),
        "slug": _obter_campo(local, "slug"),
        "nome": _obter_campo(local, "nome"),
        "categoria": _obter_campo(local, "categoria"),
        "descricao": _obter_campo(local, "descricao"),
        "cidade": _obter_campo(local, "cidade"),
        "bairro": _obter_campo(local, "bairro"),
        "regiao": _obter_campo(local, "regiao"),
        "imagem": _obter_campo(local, "imagem"),
        "destaque": bool(_obter_campo(local, "destaque")),
        "latitude": float(_obter_campo(local, "latitude")),
        "longitude": float(_obter_campo(local, "longitude")),
        "nota_media": None if nota_media is None else float(nota_media),
        "total_avaliacoes": int(_obter_campo_opcional(local, "total_avaliacoes", 0)),
    }


def serializar_locais(
    locais: list[LocalTuristico | Mapping[str, Any]],
    *,
    pagina: int,
    por_pagina: int,
    total_itens: int,
    total_paginas: int,
) -> dict[str, Any]:
    """Serializa uma coleção paginada de locais turísticos."""
    return {
        "locais": [serializar_local(local) for local in locais],
        "paginacao": {
            "pagina": int(pagina),
            "por_pagina": int(por_pagina),
            "total_itens": int(total_itens),
            "total_paginas": int(total_paginas),
        },
    }


def serializar_avaliacao(
    avaliacao: Avaliacao | Mapping[str, Any],
) -> dict[str, Any]:
    """Serializa uma avaliação conforme o contrato público."""
    return {
        "id": _obter_campo(avaliacao, "id"),
        "local_id": _obter_campo(avaliacao, "local_id"),
        "autor": _obter_campo(avaliacao, "autor"),
        "nota": _obter_campo(avaliacao, "nota"),
        "comentario": _obter_campo(avaliacao, "comentario"),
        "criado_em": _serializar_instante_utc(_obter_campo(avaliacao, "criado_em")),
    }


def serializar_avaliacoes(
    avaliacoes: list[Avaliacao | Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Serializa a coleção canônica de avaliações."""
    return {"avaliacoes": [serializar_avaliacao(avaliacao) for avaliacao in avaliacoes]}
