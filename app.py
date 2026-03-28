from flask import Flask, jsonify, request
from models import init_db
from models.base import SessionLocal
from models.local_turistico import LocalTuristico
from models.avaliacao import Avaliacao

app = Flask(__name__)

@app.route('/')
def home():
    return {"message": "API Rota Fluminense no ar!"}

@app.route("/locais/<int:id>", methods=["GET"])
def buscar_local(id):
    session = SessionLocal()
    
    local = session.query(LocalTuristico).get(id)
    
    if not local:
        session.close()
        return {"erro" :"Local não encontrado"}, 404
    
    notas = [avaliacao.nota for avaliacao in local.avaliacoes]
    media = round(sum(notas) / len(notas), 2) if notas else None
    
    resultado = {
        "id": local.id,
        "nome": local.nome,
        "cidade": local.cidade,
        "categoria": local.categoria,
        "descricao": local.descricao,
        "media_avaliacoes": media,
        "avaliacoes": [
            {
                "id": avaliacao.id,
                "nome_usuario": avaliacao.nome_usuario,
                "nota": avaliacao.nota,
                "comentario": avaliacao.comentario
            } for avaliacao in local.avaliacoes
        ]
    }
    
    session.close()
    return resultado
    
@app.route("/locais", methods=["GET"])
def listar_locais():
    session = SessionLocal()
    locais = session.query(LocalTuristico).all()
    
    resultado = []
    
    for local in locais:
        notas = [avaliacao.nota for avaliacao in local.avaliacoes]
        
        media = round(sum(notas) / len(notas), 2) if notas else None
        
        resultado.append({
            "id": local.id,
            "nome": local.nome,
            "cidade": local.cidade,
            "categoria": local.categoria,
            "media_avaliacoes": media
        })
    
    session.close()
    return resultado

@app.route("/locais", methods=["POST"])
def criar_local():
    dados = request.get_json()
    
    session = SessionLocal()
    
    local = LocalTuristico(
        nome = dados["nome"],
        cidade = dados["cidade"],
        categoria = dados["categoria"],
        descricao = dados["descricao"]
    )
    
    session.add(local)
    session.commit()
    session.refresh(local)
    session.close
    
    return {"id": local.id, "mensagem": "Local criado com sucesso!"}, 201
    
@app.route("/locais/<int:id>", methods=["PUT"])
def atualizar_local(id):
    dados = request.get_json()
    session = SessionLocal()
    
    local = session.query(LocalTuristico).get(id)
    
    if not local:
        session.close()
        return{"erro": "Local não encontrado"}, 404
    
    local.nome = dados.get("nome", local.nome)
    local.cidade = dados.get("cidade", local.cidade)
    local.categoria = dados.get("categoria", local.categoria)
    local.descricao = dados.get("descricao", local.descricao)
    
    session.commit()
    session.close()
    
    return {"mensagem": "Local atualizado com sucesso!"}
    
@app.route("/locais/<int:id>", methods=["DELETE"])
def deletar_local(id):
    session = SessionLocal()
    
    local = session.query(LocalTuristico).get(id)
    
    if not local:
        session.close()
        return {"erro": "Local não encontrado"}, 404
    
    session.delete(local)
    session.commit()
    session.close()
    
    return {"mensagem": "Local deletado com sucesso!"}
    
@app.route("/locais/filtro", methods=["GET"])
def filtrar_locais():
    cidade = request.args.get("cidade")
    categoria = request.args.get("categoria")
    
    return jsonify({
        "message": "Rota para filtrar locais turísticos",
        "filtros": {
            "cidade": cidade,
            "categoria": categoria
        }
    })

'''
    Rotas de Avaliações
'''
@app.route("/locais/<int:local_id>/avaliacoes", methods=["GET"])
def listar_avaliacoes(local_id):
    session = SessionLocal()
    
    avaliacoes = session.query(Avaliacao).filter_by(local_id=local_id).all()
    
    resultado = []
    for avaliacao in avaliacoes:
        resultado.append({
            "id": avaliacao.id,
            "nome_usuario": avaliacao.nome_usuario,
            "nota": avaliacao.nota,
            "comentario": avaliacao.comentario
        })
        
    session.close()
    return resultado

@app.route("/locais/<int:local_id>/avaliacoes", methods=["POST"])
def criar_avaliacao(local_id):
    dados = request.get_json()
    session = SessionLocal()
    
    local = session.query(LocalTuristico).get(local_id)
    if not local:
        session.close()
        return {"erro": "Local não encontrado"}, 404

    nota = dados.get("nota")
    
    if nota < 1 or nota > 5:
        session.close()
        return {"erro": "Nota deve ser entre 1 e 5"}, 400
    
    avaliacao = Avaliacao(
        nome_usuario=dados.get("nome_usuario"),
        nota=nota,
        comentario=dados.get("comentario"),
        local_id=local_id
    )
    
    session.add(avaliacao)
    session.commit()
    session.close()
    
    return {"mensagem": "Avaliação criada com sucesso!"}, 201

@app.route("//avaliacoes/<int:id>", methods=["DELETE"])
def deletar_avaliacao(id):
    session = SessionLocal()
    
    avaliacao = session.query(Avaliacao).get(id)
    
    if not avaliacao:
        session.close()
        return {"erro": "avaliaçäo não encontrada"}, 404
    
    session.delete(avaliacao)
    session.commit()
    session.close()
    
    return {"mensagem": "Avaliação deletada com sucesso!"}

if __name__ == '__main__':
    init_db()
    app.run(debug=True)