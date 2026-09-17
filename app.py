from flask import redirect
from flask_cors import CORS
from flask_openapi3 import Info, OpenAPI, Tag

from routes.avaliacao_routes import avaliacao_bp
from routes.local_routes import local_bp
from schemas.error import ErrorSchema
from utils import error_handlers

info = Info(
    title="Rota Fluminense API",
    summary="API de locais turísticos e avaliações fluminenses.",
    description=(
        "Contrato público do MVP para consultar e administrar locais "
        "turísticos e suas avaliações. As rotas de escrita não possuem "
        "autenticação nesta etapa e devem ser usadas somente no ambiente "
        "controlado de demonstração."
    ),
    version="1.0.0",
)
app = OpenAPI(
    __name__,
    info=info,
    validation_error_status=400,
    validation_error_model=ErrorSchema,
    validation_error_callback=error_handlers.tratar_erro_validacao,
)
error_handlers.registrar_manipuladores_erro(app)

app.register_api(local_bp)
app.register_api(avaliacao_bp)
CORS(app)

home_tag = Tag(
    name="Documentação",
    description="Seleção de documentação: Swagger, Redoc ou RapiDoc",
)


@app.get(
    "/",
    tags=[home_tag],
    summary="Abrir documentação interativa",
    description="Redireciona para a interface Swagger publicada em /openapi.",
    operation_id="abrir_documentacao",
)
def home():
    """Redireciona para /openapi."""
    return redirect("/openapi")


if __name__ == "__main__":
    app.run(debug=True)
