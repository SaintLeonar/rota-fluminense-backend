from flask import Flask, jsonify, request
from models import init_db
from models.base import SessionLocal
from models.local_turistico import LocalTuristico
from models.avaliacao import Avaliacao
from routes.local_routes import local_bp
from routes.avaliacao_routes import avaliacao_bp

app = Flask(__name__)

app.register_blueprint(local_bp)
app.register_blueprint(avaliacao_bp)

@app.route('/')
def home():
    return {"message": "API Rota Fluminense no ar!"}

if __name__ == '__main__':
    init_db()
    app.run(debug=True)