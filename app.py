from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route('/')
def home():
    return {"message": "API Rota Fluminense no ar!"}

@app.route("/locais", methods=["GET"])
def listar_locais():
    return jsonify({
        "message": "Rota para listar locais turísticos"
    })
    
@app.route("/locais/<int:id>", methods=["GET"])
def buscar_local_por_id(id):
    return jsonify({
        "message": f"Rota para bucas o local de id {id}"
    })

@app.route("/locais", methods=["POST"])
def criar_local():
    dados = request.get_json()
    return jsonify({
        "message": "Rota para criar local turístico",
        "dados_recebidos": dados
    }), 201
    
@app.route("/locais/<int:id>", methods=["PUT"])
def atualizar_local(id):
    dados = request.get_json()
    return jsonify({
        "message": f"Rota para atualizar o local de id {id}",
        "dados_recebidos": dados
    })
    
@app.route("/locais/<int:id>", methods=["DELETE"])
def deletar_local(id):
    return jsonify({
        "message": f"Rota para deletar o local de id {id}"
    })
    
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

if __name__ == '__main__':
    app.run(debug=True)