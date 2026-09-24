from flask import redirect
from flask_openapi3 import Info, OpenAPI, Tag

from routes.avaliacao_routes import avaliacao_bp
from routes.local_routes import local_bp
from schemas.error import ErrorSchema
from services.cors_config import configure_cors, load_cors_settings
from services.open_meteo_cache import OPEN_METEO_CACHE
from services.open_meteo_client import OPEN_METEO_CLIENT
from services.open_meteo_config import OPEN_METEO_SETTINGS
from services.open_meteo_service import OPEN_METEO_SERVICE
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
CORS_SETTINGS = load_cors_settings()
app.config["CORS_SETTINGS"] = CORS_SETTINGS
app.config["OPEN_METEO_SETTINGS"] = OPEN_METEO_SETTINGS
app.config["OPEN_METEO_CLIENT"] = OPEN_METEO_CLIENT
app.config["OPEN_METEO_CACHE"] = OPEN_METEO_CACHE
app.config["OPEN_METEO_SERVICE"] = OPEN_METEO_SERVICE
error_handlers.registrar_manipuladores_erro(app)

app.register_api(local_bp)
app.register_api(avaliacao_bp)
configure_cors(app, CORS_SETTINGS)

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
