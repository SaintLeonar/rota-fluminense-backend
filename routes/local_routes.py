from flask import Blueprint, request

from services.local_service import (
    atualizar_local,
    buscar_local,
    criar_local,
    deletar_local,
    listar_locais,
)
from utils.serializers import serializar_local

local_bp = Blueprint("locais", __name__)


@local_bp.route("/locais", methods=["GET"])
def get_locais():
    """Endpoint para listar os locais."""
    cidade = request.args.get("cidade")
    categoria = request.args.get("categoria")

    try:
        return listar_locais(cidade, categoria), 200
    except Exception as e:
        return {"erro": str(e)}, e.status_code


@local_bp.route("/locais/<int:local_id>", methods=["GET"])
def get_local(local_id: int):
    """Endpoint para buscar um local por ID.

    Args:
        local_id (int): ID do local.
    """
    try:
        return buscar_local(local_id), 200
    except Exception as e:
        return {"erro": str(e)}, e.status_code


@local_bp.route("/locais", methods=["POST"])
def post_local():
    """Endpoint para criar um novo local."""
    try:
        local = criar_local(request.get_json())

        return serializar_local(local), 201
    except Exception as e:
        return {"erro": str(e)}, e.status_code


@local_bp.route("/locais/<int:local_id>", methods=["PUT"])
def put_local(local_id: int):
    """Endpoint para atualizar um local.

    Args:
        local_id (int): ID do local.
    """
    try:
        local = atualizar_local(local_id, request.get_json())

        return serializar_local(local), 201
    except Exception as e:
        return {"erro": str(e)}, e.status_code


@local_bp.route("/locais/<int:local_id>", methods=["DELETE"])
def delete_local(local_id: int):
    """Endpoint para deletar um local.

    Args:
        local_id (int): ID do local.
    """
    try:
        return deletar_local(local_id), 204
    except Exception as e:
        return {"erro": str(e)}, e.status_code
