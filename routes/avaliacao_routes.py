from flask import Blueprint, request

from services.avaliacao_service import (
    criar_avaliacao,
    deletar_avaliacao,
    listar_avaliacoes,
)
from utils.serializers import serializar_avaliacao

avaliacao_bp = Blueprint("avaliacao", __name__)


@avaliacao_bp.route("/locais/<int:local_id>/avaliacoes", methods=["GET"])
def get_avaliacoes(local_id: int):
    """Endpoint para listar as avaliações de um local.

    Args:
        local_id (int): ID do local.
    """
    try:
        return listar_avaliacoes(local_id), 200
    except Exception as e:
        return {"erro": str(e)}, e.status_code


@avaliacao_bp.route("/locais/<int:local_id>/avaliacoes", methods=["POST"])
def post_avaliacao(local_id: int):
    """Endpoint para criar uma avaliação de um local.

    Args:
        local_id (int): ID do local.
    """
    try:
        avaliacao = criar_avaliacao(local_id, request.json)

        return serializar_avaliacao(avaliacao), 201
    except Exception as e:
        return {"erro": str(e)}, e.status_code


@avaliacao_bp.route("/avaliacoes/<int:avaliacao_id>", methods=["DELETE"])
def delete_avaliacao(avaliacao_id: int):
    """Endpoint para deletar uma avaliação.

    Args:
        avaliacao_id (int): ID da avaliação.
    """
    try:
        return deletar_avaliacao(avaliacao_id), 204
    except Exception as e:
        return {"erro": str(e)}, e.status_code
