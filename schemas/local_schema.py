from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from schemas import openapi_examples, validacao


class LocalMutableFieldsSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": openapi_examples.LOCAL_MUTABLE_EXAMPLE},
    )

    nome: validacao.Texto120 = Field(
        description="Nome público do local turístico.",
        examples=["Arpoador"],
    )
    categoria: validacao.Categoria = Field(
        description="Categoria canônica usada em filtros.",
        examples=["praias"],
    )
    descricao: validacao.Texto2000 = Field(
        description="Descrição pública do local turístico.",
        examples=["Praia e mirante conhecidos pelo pôr do sol."],
    )
    cidade: validacao.Cidade = Field(
        description="Município do estado do Rio de Janeiro.",
        examples=["Rio de Janeiro"],
    )
    bairro: validacao.Texto120 = Field(
        description="Bairro onde o local está situado.",
        examples=["Ipanema"],
    )
    regiao: validacao.Texto80 = Field(
        description="Região turística ou administrativa.",
        examples=["Zona Sul"],
    )
    imagem: validacao.ImagemPublica = Field(
        description="URL HTTP(S) ou caminho público absoluto da imagem.",
        examples=["/imagens/locais/arpoador.jpg"],
    )
    destaque: StrictBool = Field(
        description="Indica se o local integra a seleção de destaques.",
        examples=[True],
    )
    latitude: validacao.Latitude = Field(
        description="Latitude em graus decimais entre -90 e 90.",
        examples=[-22.988],
    )
    longitude: validacao.Longitude = Field(
        description="Longitude em graus decimais entre -180 e 180.",
        examples=[-43.191],
    )


class LocalInputSchema(LocalMutableFieldsSchema):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": openapi_examples.LOCAL_INPUT_EXAMPLE},
    )

    slug: Optional[validacao.Slug] = Field(
        default=None,
        description=(
            "Identificador público canônico; quando omitido, é gerado a "
            "partir do nome."
        ),
        examples=["arpoador"],
    )
    destaque: StrictBool = Field(
        default=False,
        description="Indica se o local integra a seleção de destaques.",
        examples=[True],
    )


class LocalUpdateSchema(LocalMutableFieldsSchema):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": openapi_examples.LOCAL_MUTABLE_EXAMPLE},
    )


class LocalSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": openapi_examples.LOCAL_RESPONSE_EXAMPLE},
        openapi_extra={
            "description": "Representação canônica de um local turístico.",
            "example": openapi_examples.LOCAL_RESPONSE_EXAMPLE,
        },
    )

    id: validacao.InteiroPositivo = Field(
        description="Identificador técnico somente leitura.",
        examples=[1],
    )
    slug: validacao.Slug = Field(
        description="Identificador público estável usado nas URLs.",
        examples=["arpoador"],
    )
    nome: validacao.Texto120 = Field(description="Nome público do local.")
    categoria: validacao.Categoria = Field(
        description="Categoria canônica do local."
    )
    descricao: validacao.Texto2000 = Field(
        description="Descrição pública do local."
    )
    cidade: validacao.Cidade = Field(description="Município fluminense.")
    bairro: validacao.Texto120 = Field(description="Bairro do local.")
    regiao: validacao.Texto80 = Field(description="Região do local.")
    imagem: validacao.ImagemPublica = Field(
        description="URL ou caminho público da imagem."
    )
    destaque: StrictBool = Field(
        description="Indica participação na seleção de destaques."
    )
    latitude: validacao.Latitude = Field(
        description="Latitude em graus decimais."
    )
    longitude: validacao.Longitude = Field(
        description="Longitude em graus decimais."
    )
    nota_media: Optional[Annotated[float, Field(ge=1, le=5)]] = Field(
        description=(
            "Média derivada das avaliações, com uma casa decimal; nula "
            "quando não há avaliações."
        ),
        examples=[4.5],
    )
    total_avaliacoes: validacao.InteiroNaoNegativo = Field(
        description="Quantidade de avaliações persistidas.",
        examples=[2],
    )


class LocalDetalhadoSchema(LocalSchema):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": openapi_examples.LOCAL_RESPONSE_EXAMPLE},
        openapi_extra={
            "description": "Detalhe canônico de um local turístico.",
            "example": openapi_examples.LOCAL_RESPONSE_EXAMPLE,
        },
    )


class PaginacaoSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": openapi_examples.PAGINATION_EXAMPLE},
    )

    pagina: validacao.InteiroPositivo = Field(
        description="Página solicitada.", examples=[1]
    )
    por_pagina: Annotated[
        int,
        Field(
            strict=True,
            ge=1,
            le=100,
            description="Quantidade de itens por página.",
            examples=[12],
        ),
    ]
    total_itens: validacao.InteiroNaoNegativo = Field(
        description="Total de itens após os filtros.", examples=[6]
    )
    total_paginas: validacao.InteiroNaoNegativo = Field(
        description="Total de páginas calculado.", examples=[1]
    )


class LocalListSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": openapi_examples.LOCAL_LIST_EXAMPLE},
        openapi_extra={
            "description": "Coleção paginada de locais turísticos.",
            "example": openapi_examples.LOCAL_LIST_EXAMPLE,
        },
    )

    locais: list[LocalSchema] = Field(description="Locais da página corrente.")
    paginacao: PaginacaoSchema = Field(description="Metadados da paginação.")


class LocalQuerySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cidade: Optional[validacao.Cidade] = Field(
        default=None,
        description="Filtra pelo município fluminense completo.",
        json_schema_extra={"example": "Rio de Janeiro"},
    )
    categoria: Optional[validacao.Categoria] = Field(
        default=None,
        description="Filtra pela categoria canônica.",
        json_schema_extra={"example": "praias"},
    )
    destaque: Optional[validacao.DestaqueConsulta] = Field(
        default=None,
        description="Filtra exatamente por locais destacados ou não.",
        json_schema_extra={"example": True},
    )
    pagina: validacao.Pagina = Field(
        default=1,
        description="Página solicitada, iniciando em 1.",
        json_schema_extra={"example": 1},
    )
    por_pagina: validacao.PorPagina = Field(
        default=12,
        description="Itens por página, entre 1 e 100.",
        json_schema_extra={"example": 12},
    )
    ordenar_por: validacao.OrdenacaoLocal = Field(
        default="nome_asc",
        description="Critério de ordenação determinística.",
        json_schema_extra={"example": "nota_media_desc"},
    )


class LocalPathSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: validacao.Slug = Field(
        description="Slug público canônico do local.",
        json_schema_extra={"example": "arpoador"},
    )


def apresenta_locais(locais):
    """Apresenta a lista de locais."""
    resultado = []
    for local in locais:
        resultado.append(
            {
                "id": local["id"],
                "slug": local["slug"],
                "nome": local["nome"],
                "categoria": local.get("categoria"),
                "descricao": local["descricao"],
                "cidade": local["cidade"],
                "bairro": local["bairro"],
                "regiao": local["regiao"],
                "imagem": local["imagem"],
                "destaque": local["destaque"],
                "latitude": local["latitude"],
                "longitude": local["longitude"],
                "nota_media": local.get("nota_media"),
                "total_avaliacoes": local.get("total_avaliacoes", 0),
            }
        )

    return {"locais": resultado}


def apresenta_local(local):
    """Apresenta um local."""
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
