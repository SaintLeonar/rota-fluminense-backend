from flask_openapi3 import APIBlueprint
from flask_openapi3 import Tag

from schemas.avaliacao_schema import (
    AvaliacaoSchema,
    AvaliacaoInputSchema,
    AvaliacaoPathSchema,
    AvaliacaoLocalPathSchema,
    AvaliacaoListSchema,
    apresenta_avaliacoes,
)
from schemas.error import ErrorSchema

from services.avaliacao_service import (
    criar_avaliacao,
    deletar_avaliacao,
    listar_avaliacoes,
)
from utils.serializers import serializar_avaliacao
from utils.exceptions import AppError


avaliacao_bp = APIBlueprint("avaliacoes", __name__)


avaliacao_tag = Tag(
    name="Avaliações",
    description="Operações relacionadas às avaliações de locais"
)


@avaliacao_bp.get("/locais/<int:local_id>/avaliacoes", tags=[avaliacao_tag],
                  responses={200: AvaliacaoListSchema, 404: ErrorSchema, 500: ErrorSchema})
def get_avaliacoes(path: AvaliacaoLocalPathSchema):
    """Endpoint para listar as avaliações de um local."""
    try:
        resultado = listar_avaliacoes(path.local_id)
        return apresenta_avaliacoes(resultado)
    except AppError as e:
        return {"message": e.message}, e.status_code
    except Exception:
        return {"message": "Erro interno"}, 500


@avaliacao_bp.post("/locais/<int:local_id>/avaliacoes", tags=[avaliacao_tag],
                   responses={201: AvaliacaoSchema, 400: ErrorSchema, 500: ErrorSchema} )
def post_avaliacao(path: AvaliacaoLocalPathSchema, body: AvaliacaoInputSchema):
    """Endpoint para criar uma avaliação de um local."""
    try:
        avaliacao = criar_avaliacao(path.local_id, body.dict())
        return serializar_avaliacao(avaliacao), 201
    except AppError as e:
        return {"message": e.message}, e.status_code
    except Exception:
        return {"message": "Erro interno"}, 500


@avaliacao_bp.delete("/avaliacoes/<int:avaliacao_id>", tags=[avaliacao_tag],
                     responses={204: None, 404: ErrorSchema, 500: ErrorSchema})
def delete_avaliacao(path: AvaliacaoPathSchema):
    """Endpoint para deletar uma avaliação."""
    try:
        deletar_avaliacao(path.avaliacao_id)
        return "", 204
    except AppError as e:
        return {"message": e.message}, e.status_code
    except Exception:
        return {"message": "Erro interno"}, 500
