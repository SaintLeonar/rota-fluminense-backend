from flask import Blueprint, request
from services.avaliacao_service import listar_avaliacoes, criar_avaliacao, deletar_avaliacao
from utils.serializers import serializar_avaliacao

avaliacao_bp = Blueprint('avaliacao', __name__)

@avaliacao_bp.route('/locais/<int:local_id>/avaliacoes', methods=['GET'])
def get_avaliacoes(local_id):
    
    try:
        return listar_avaliacoes(local_id), 200
    except Exception as e:
        return {"erro": str(e)}, e.status_code

@avaliacao_bp.route('/locais/<int:local_id>/avaliacoes', methods=['POST'])
def post_avaliacao(local_id):
    
    try:
        avaliacao = criar_avaliacao(local_id, request.json)
        
        return serializar_avaliacao(avaliacao), 201
    except Exception as e:
        return {"erro": str(e)}, e.status_code

@avaliacao_bp.route('/avaliacoes/<int:id>', methods=['DELETE'])
def delete_avaliacao(id):
    
    try:
        return deletar_avaliacao(id), 204
    except Exception as e:
        return {"erro": str(e)}, e.status_code