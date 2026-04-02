from flask import Flask

from models import init_db
from routes.avaliacao_routes import avaliacao_bp
from routes.local_routes import local_bp

app = Flask(__name__)

app.register_blueprint(local_bp)
app.register_blueprint(avaliacao_bp)


@app.route("/")
def home():
    """Endpoint raiz da API.
    
    Returns:
        dict: Mensagem de boas-vindas.
    """
    return {"message": "API Rota Fluminense no ar!"}


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
