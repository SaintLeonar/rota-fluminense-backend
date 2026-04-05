from flask import redirect
from flask_cors import CORS
from flask_openapi3 import Info, OpenAPI, Tag

from models import init_db
from routes.avaliacao_routes import avaliacao_bp
from routes.local_routes import local_bp

info = Info(title="Rota Fluminense API", version="1.0.0")
app = OpenAPI(__name__, info=info)

app.register_api(local_bp)
app.register_api(avaliacao_bp)
CORS(app)

home_tag = Tag(
    name="Documentação",
    description="Seleção de documentação: Swagger, Redoc ou RapiDoc",
)


@app.get("/", tags=[home_tag])
def home():
    """Redireciona para /openapi.
    
    Tela que permite a escolha do estilo de documentação.
    """
    return redirect("/openapi")


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
