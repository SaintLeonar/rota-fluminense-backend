from flask import current_app
from flask_openapi3 import APIBlueprint, Tag

from schemas import clima_schema, local_schema
from schemas.error import CLIMATE_SERVICE_UNAVAILABLE_RESPONSE, ErrorSchema
from services import local_service
from utils import error_handlers
from utils.serializers import serializar_locais, serializar_local

local_bp = APIBlueprint("locais", __name__)


local_tag = Tag(
    name="Locais",
    description="Operações relacionadas a locais turísticos",
)


@local_bp.get(
    "/locais",
    tags=[local_tag],
    summary="Listar locais turísticos",
    description=(
        "Lista locais com filtros exatos combinados por AND, paginação, "
        "ordenação determinística e agregados derivados das avaliações."
    ),
    operation_id="listar_locais",
    responses={
        200: local_schema.LocalListSchema,
        400: ErrorSchema,
        503: ErrorSchema,
        500: ErrorSchema,
    },
)
def get_locais(query: local_schema.LocalQuerySchema):
    """Endpoint para listar os locais."""
    locais, total_itens, total_paginas = local_service.listar_locais(
        query.cidade,
        query.categoria,
        query.destaque,
        query.pagina,
        query.por_pagina,
        query.ordenar_por,
    )
    return serializar_locais(
        locais,
        pagina=query.pagina,
        por_pagina=query.por_pagina,
        total_itens=total_itens,
        total_paginas=total_paginas,
    )


@local_bp.get(
    "/locais/<slug>",
    tags=[local_tag],
    summary="Consultar local por slug",
    description=(
        "Retorna a representação canônica do local, sem incorporar a "
        "coleção de avaliações."
    ),
    operation_id="consultar_local",
    responses={
        200: local_schema.LocalDetalhadoSchema,
        400: ErrorSchema,
        404: ErrorSchema,
        503: ErrorSchema,
        500: ErrorSchema,
    },
)
def get_local(path: local_schema.LocalPathSchema):
    """Endpoint para buscar um local pelo slug público."""
    local = local_service.buscar_local(path.slug)
    return serializar_local(local)


@local_bp.get(
    "/locais/<slug>/clima",
    tags=[local_tag],
    summary="Consultar clima do local",
    description=(
        "Retorna as condições atuais e a previsão de três dias usando as "
        "coordenadas persistidas do local, com metadados de cache."
    ),
    operation_id="consultar_clima_local",
    responses={
        200: clima_schema.ClimaResponseSchema,
        400: ErrorSchema,
        404: ErrorSchema,
        500: ErrorSchema,
        503: CLIMATE_SERVICE_UNAVAILABLE_RESPONSE,
    },
)
def get_clima_local(path: local_schema.LocalPathSchema):
    """Endpoint para consultar o clima associado a um local."""
    service = current_app.config["OPEN_METEO_SERVICE"]
    clima = service.consultar_clima(
        path.slug,
        requisicao_id=error_handlers.obter_requisicao_id(),
    )
    return clima.model_dump(mode="json")


@local_bp.post(
    "/locais",
    tags=[local_tag],
    summary="Criar local turístico",
    description=(
        "Cria um local completo. O slug é opcional e, quando omitido, é "
        "gerado de forma canônica a partir do nome."
    ),
    operation_id="criar_local",
    responses={
        201: local_schema.LocalSchema,
        400: ErrorSchema,
        409: ErrorSchema,
        503: ErrorSchema,
        500: ErrorSchema,
    },
)
def post_local(body: local_schema.LocalInputSchema):
    """Endpoint para criar um novo local."""
    local = local_service.criar_local(body.model_dump())
    return serializar_local(local), 201


@local_bp.put(
    "/locais/<slug>",
    tags=[local_tag],
    summary="Substituir local turístico",
    description=(
        "Substitui todos os dez campos mutáveis, preservando id, slug e "
        "agregados derivados."
    ),
    operation_id="substituir_local",
    responses={
        200: local_schema.LocalSchema,
        400: ErrorSchema,
        404: ErrorSchema,
        503: ErrorSchema,
        500: ErrorSchema,
    },
)
def put_local(
    path: local_schema.LocalPathSchema,
    body: local_schema.LocalUpdateSchema,
):
    """Endpoint para substituir os campos mutáveis de um local."""
    local = local_service.atualizar_local(path.slug, body.model_dump())
    return serializar_local(local)


@local_bp.delete(
    "/locais/<slug>",
    tags=[local_tag],
    summary="Excluir local turístico",
    description=(
        "Exclui o local identificado pelo slug; avaliações relacionadas "
        "são removidas pela integridade referencial do banco."
    ),
    operation_id="excluir_local",
    responses={
        204: None,
        400: ErrorSchema,
        404: ErrorSchema,
        503: ErrorSchema,
        500: ErrorSchema,
    },
)
def delete_local(path: local_schema.LocalPathSchema):
    """Endpoint para excluir um local pelo slug público."""
    local_service.deletar_local(path.slug)
    return "", 204
