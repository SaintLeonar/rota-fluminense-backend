from flask_openapi3 import APIBlueprint, Tag

from schemas.error import ErrorSchema
from schemas.local_schema import (LocalDetalhadoSchema, LocalInputSchema,
                                  LocalListSchema, LocalPathSchema,
                                  LocalQuerySchema, LocalSchema,
                                  apresenta_locais, apresenta_local)
from services.local_service import (atualizar_local, buscar_local, criar_local,
                                    deletar_local, listar_locais)
from utils.exceptions import AppError
from utils.serializers import serializar_local

local_bp = APIBlueprint("locais", __name__)


local_tag = Tag(
    name="Locais",
    description="Operações relacionadas a locais turísticos",
)


@local_bp.get(
    "/locais",
    tags=[local_tag],
    responses={200: LocalListSchema, 404: ErrorSchema, 500: ErrorSchema},
)
def get_locais(query: LocalQuerySchema):
    """Endpoint para listar os locais."""
    try:
        resultado = listar_locais(query.cidade, query.categoria)
        return apresenta_locais(resultado)
    except AppError as e:
        return {"message": e.message}, e.status_code
    except Exception:
        return {"message": "Erro interno"}, 500


@local_bp.get(
    "/locais/<int:local_id>",
    tags=[local_tag],
    responses={200: LocalDetalhadoSchema, 404: ErrorSchema, 500: ErrorSchema},
)
def get_local(path: LocalPathSchema):
    """Endpoint para buscar um local por ID."""
    try:
        local = buscar_local(path.local_id)
        return apresenta_local(local)
    except AppError as e:
        return {"message": e.message}, e.status_code
    except Exception:
        return {"message": "Erro interno"}, 500


@local_bp.post(
    "/locais",
    tags=[local_tag],
    responses={201: LocalSchema, 400: ErrorSchema, 500: ErrorSchema},
)
def post_local(body: LocalInputSchema):
    """Endpoint para criar um novo local."""
    try:
        local = criar_local(body.dict())

        return serializar_local(local), 201
    except AppError as e:
        return {"message": e.message}, e.status_code
    except Exception:
        return {"message": "Erro interno"}, 500


@local_bp.put(
    "/locais/<int:local_id>",
    tags=[local_tag],
    responses={200: LocalSchema, 400: ErrorSchema, 404: ErrorSchema, 500: ErrorSchema},
)
def put_local(path: LocalPathSchema, body: LocalInputSchema):
    """Endpoint para atualizar um local."""
    try:
        local = atualizar_local(path.local_id, body.dict())

        return serializar_local(local)
    except AppError as e:
        return {"message": e.message}, e.status_code
    except Exception:
        return {"message": "Erro interno"}, 500


@local_bp.delete(
    "/locais/<int:local_id>",
    tags=[local_tag],
    responses={204: None, 404: ErrorSchema, 500: ErrorSchema},
)
def delete_local(path: LocalPathSchema):
    """Endpoint para deletar um local."""
    try:
        deletar_local(path.local_id)
        return "", 204
    except AppError as e:
        return {"message": e.message}, e.status_code
    except Exception:
        return {"message": "Erro interno"}, 500
