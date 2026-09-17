from flask_openapi3 import APIBlueprint, Tag

from schemas import avaliacao_schema
from schemas.error import ErrorSchema
from services import avaliacao_service
from utils.serializers import serializar_avaliacao, serializar_avaliacoes

avaliacao_bp = APIBlueprint("avaliacoes", __name__)


avaliacao_tag = Tag(
    name="Avaliações",
    description="Operações relacionadas às avaliações de locais",
)


@avaliacao_bp.get(
    "/locais/<slug>/avaliacoes",
    tags=[avaliacao_tag],
    summary="Listar avaliações do local",
    description=(
        "Lista as avaliações por data de criação decrescente e usa o id "
        "decrescente como desempate."
    ),
    operation_id="listar_avaliacoes",
    responses={
        200: avaliacao_schema.AvaliacaoListSchema,
        400: ErrorSchema,
        404: ErrorSchema,
        503: ErrorSchema,
        500: ErrorSchema,
    },
)
def get_avaliacoes(path: avaliacao_schema.AvaliacaoLocalPathSchema):
    """Endpoint para listar as avaliações pelo slug público do local."""
    avaliacoes = avaliacao_service.listar_avaliacoes(path.slug)
    return serializar_avaliacoes(avaliacoes)


@avaliacao_bp.post(
    "/locais/<slug>/avaliacoes",
    tags=[avaliacao_tag],
    summary="Criar avaliação do local",
    description=(
        "Cria uma avaliação associada ao local identificado pelo slug; o "
        "vínculo não é aceito no corpo."
    ),
    operation_id="criar_avaliacao",
    responses={
        201: avaliacao_schema.AvaliacaoSchema,
        400: ErrorSchema,
        404: ErrorSchema,
        503: ErrorSchema,
        500: ErrorSchema,
    },
)
def post_avaliacao(
    path: avaliacao_schema.AvaliacaoLocalPathSchema,
    body: avaliacao_schema.AvaliacaoInputSchema,
):
    """Endpoint para criar uma avaliação pelo slug público do local."""
    avaliacao = avaliacao_service.criar_avaliacao(
        path.slug,
        body.model_dump(),
    )
    return serializar_avaliacao(avaliacao), 201


@avaliacao_bp.patch(
    "/avaliacoes/<int:avaliacao_id>",
    tags=[avaliacao_tag],
    summary="Atualizar parcialmente avaliação",
    description=(
        "Atualiza ao menos um entre autor, nota e comentário, preservando "
        "id, local_id e criado_em."
    ),
    operation_id="atualizar_avaliacao",
    responses={
        200: avaliacao_schema.AvaliacaoSchema,
        400: ErrorSchema,
        404: ErrorSchema,
        503: ErrorSchema,
        500: ErrorSchema,
    },
)
def patch_avaliacao(
    path: avaliacao_schema.AvaliacaoPathSchema,
    body: avaliacao_schema.AvaliacaoUpdateSchema,
):
    """Endpoint para atualizar parcialmente uma avaliação."""
    avaliacao = avaliacao_service.atualizar_avaliacao(
        path.avaliacao_id,
        body.model_dump(exclude_unset=True),
    )
    return serializar_avaliacao(avaliacao)


@avaliacao_bp.delete(
    "/avaliacoes/<int:avaliacao_id>",
    tags=[avaliacao_tag],
    summary="Excluir avaliação",
    description="Exclui somente a avaliação identificada pelo id técnico.",
    operation_id="excluir_avaliacao",
    responses={
        204: None,
        400: ErrorSchema,
        404: ErrorSchema,
        503: ErrorSchema,
        500: ErrorSchema,
    },
)
def delete_avaliacao(path: avaliacao_schema.AvaliacaoPathSchema):
    """Endpoint para excluir uma avaliação pelo identificador técnico."""
    avaliacao_service.deletar_avaliacao(path.avaliacao_id)
    return "", 204
