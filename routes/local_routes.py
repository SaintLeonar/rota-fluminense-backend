from flask import Blueprint, request
from services.local_service import listar_locais, buscar_local, criar_local, atualizar_local, deletar_local
from utils.serializers import serializar_local

local_bp = Blueprint("locais", __name__)

@local_bp.route("/locais", methods=["GET"])
def get_locais():
    cidade = request.args.get("cidade")
    categoria = request.args.get("categoria")
    
    try:
        return listar_locais(cidade, categoria), 200
    except Exception as e:
        return {"erro": str(e)}, e.status_code

@local_bp.route("/locais/<int:id>", methods=["GET"])
def get_local(id):
    
    try:
        return buscar_local(id), 200
    except Exception as e:
        return {"erro": str(e)}, e.status_code

@local_bp.route("/locais", methods=["POST"])
def post_local():
    try:
        local = criar_local(request.get_json())
        
        return serializar_local(local), 201
    except Exception as e:
        return {"erro": str(e)}, e.status_code

@local_bp.route("/locais/<int:id>", methods=["PUT"])
def put_local(id):
    
    try:
        local = atualizar_local(id, request.get_json())
        
        return serializar_local(local), 201
    except Exception as e:
        return {"erro": str(e)}, e.status_code

@local_bp.route("/locais/<int:id>", methods=["DELETE"])
def delete_local(id):
    
    try:
        return deletar_local(id), 204
    except Exception as e:
        return {"erro": str(e)}, e.status_code