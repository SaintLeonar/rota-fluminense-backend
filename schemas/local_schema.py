from typing import List, Optional

from pydantic import BaseModel

from schemas.avaliacao_schema import AvaliacaoSchema


class LocalSchema(BaseModel):
    id: int
    nome: str
    cidade: str
    categoria: str
    descricao: str
    media_avaliacoes: Optional[float]
    total_avaliacoes: int


class LocalDetalhadoSchema(LocalSchema):
    avaliacoes: List[AvaliacaoSchema]


class LocalInputSchema(BaseModel):
    nome: str
    cidade: str
    categoria: str
    descricao: str


class LocalSchema(LocalInputSchema):
    id: int


class LocalListSchema(LocalSchema):
    locais: list[LocalSchema]


class LocalQuerySchema(BaseModel):
    cidade: Optional[str] = None
    categoria: Optional[str] = None


class LocalPathSchema(BaseModel):
    local_id: int


def apresenta_locais(locais):
    """Apresenta a lista de locais.
    
    :param locais: Lista de locais.
    :return: Dicionário com a lista de locais.
    """
    resultado = []
    for local in locais:
        resultado.append(
            {
                "id": local["id"],
                "nome": local["nome"],
                "cidade": local["cidade"],
                "categoria": local.get("categoria"),
                "descricao": local["descricao"],
                "media_avaliacoes": local.get("media_avaliacoes"),
                "total_avaliacoes": local.get("total_avaliacoes", 0),
            }
        )

    return {"locais": resultado}


def apresenta_local(local):
    """Apresenta um local.
    
    :param local: Local a ser apresentado.
    :return: Dicionário com o local.
    """
    return {
        "id": local["id"],
        "nome": local["nome"],
        "cidade": local["cidade"],
        "categoria": local["categoria"],
        "descricao": local["descricao"],
        "media_avaliacoes": local["media_avaliacoes"],
        "avaliacoes": [
            {
                "id": avaliacao["id"],
                "nome_usuario": avaliacao["nome_usuario"],
                "nota": avaliacao["nota"],
                "comentario": avaliacao["comentario"],
            }
            for avaliacao in local["avaliacoes"]
        ],
    }
