from typing import Any, Optional
from uuid import uuid4

from flask import Flask, Response, current_app, g, jsonify, request
from pydantic import ValidationError
from sqlalchemy import exc as sqlalchemy_exc
from werkzeug.exceptions import HTTPException

from utils.exceptions import AppError

REQUEST_ID_HEADER = "X-Request-ID"


def gerar_requisicao_id() -> str:
    """Gera um identificador opaco para correlação da requisição."""
    return f"req_{uuid4().hex}"


def obter_requisicao_id() -> str:
    """Obtém o identificador da requisição corrente."""
    if not hasattr(g, "requisicao_id"):
        g.requisicao_id = gerar_requisicao_id()
    return g.requisicao_id


def construir_envelope_erro(
    codigo: str,
    mensagem: str,
    detalhes: Optional[list[dict[str, Any]]] = None,
    requisicao_id: Optional[str] = None,
) -> dict[str, Any]:
    """Constrói o envelope público de erro."""
    return {
        "erro": {
            "codigo": codigo,
            "mensagem": mensagem,
            "detalhes": detalhes or [],
            "requisicao_id": requisicao_id or obter_requisicao_id(),
        }
    }


def criar_resposta_erro(
    codigo: str,
    mensagem: str,
    status_code: int,
    detalhes: Optional[list[dict[str, Any]]] = None,
) -> Response:
    """Cria uma resposta JSON segura no formato canônico."""
    resposta = jsonify(
        construir_envelope_erro(
            codigo,
            mensagem,
            detalhes,
        )
    )
    resposta.status_code = status_code
    return resposta


def _campo_validacao(localizacao: tuple[Any, ...]) -> Optional[str]:
    partes = list(localizacao)
    if partes and partes[0] in {"body", "path", "query"}:
        partes.pop(0)
    if not partes:
        return None
    return ".".join(str(parte) for parte in partes)


def _codigo_detalhe_validacao(tipo: str) -> str:
    if tipo == "missing":
        return "obrigatorio"
    if tipo == "extra_forbidden":
        return "campo_nao_permitido"
    if tipo.endswith("_type") or tipo.endswith("_parsing"):
        return "tipo_invalido"
    if tipo in {
        "greater_than",
        "greater_than_equal",
        "less_than",
        "less_than_equal",
        "string_too_long",
        "string_too_short",
        "too_long",
        "too_short",
    }:
        return "fora_do_limite"
    return "valor_invalido"


def _mensagem_detalhe_validacao(codigo: str) -> str:
    return {
        "obrigatorio": "O campo é obrigatório.",
        "campo_nao_permitido": "O campo não é permitido.",
        "tipo_invalido": "O tipo informado é inválido.",
        "fora_do_limite": "O valor está fora dos limites permitidos.",
        "valor_invalido": "O valor informado é inválido.",
    }[codigo]


def normalizar_erros_validacao(
    erro: ValidationError,
) -> list[dict[str, Any]]:
    """Converte erros Pydantic sem expor entrada ou contexto internos."""
    detalhes = []
    for item in erro.errors():
        codigo = _codigo_detalhe_validacao(item["type"])
        detalhes.append(
            {
                "campo": _campo_validacao(item["loc"]),
                "codigo": codigo,
                "mensagem": _mensagem_detalhe_validacao(codigo),
            }
        )
    return detalhes


def tratar_erro_validacao(erro: ValidationError) -> Response:
    """Converte a validação do flask-openapi3 em HTTP 400 canônico."""
    return criar_resposta_erro(
        "requisicao_invalida",
        "A requisição contém valores inválidos.",
        400,
        normalizar_erros_validacao(erro),
    )


def _violacao_unicidade(erro: sqlalchemy_exc.IntegrityError) -> bool:
    origem = erro.orig
    codigo = getattr(origem, "errno", None)
    if codigo is None:
        argumentos = getattr(origem, "args", ())
        codigo = argumentos[0] if argumentos else None

    return (
        codigo in {1062, 1555, 2067}
        or getattr(origem, "pgcode", None) == "23505"
        or getattr(origem, "sqlite_errorcode", None) in {1555, 2067}
    )


def registrar_manipuladores_erro(app: Flask) -> None:
    """Registra correlação, logs e handlers globais da API."""

    @app.before_request
    def iniciar_correlacao() -> None:
        g.requisicao_id = gerar_requisicao_id()

    @app.after_request
    def finalizar_correlacao(resposta: Response) -> Response:
        requisicao_id = obter_requisicao_id()
        resposta.headers[REQUEST_ID_HEADER] = requisicao_id
        current_app.logger.info(
            "Requisição concluída requisicao_id=%s método=%s caminho=%s " "status=%s",
            requisicao_id,
            request.method,
            request.path,
            resposta.status_code,
        )
        return resposta

    @app.errorhandler(AppError)
    def responder_erro_aplicacao(erro: AppError) -> Response:
        current_app.logger.warning(
            "Erro esperado requisicao_id=%s codigo=%s status=%s",
            obter_requisicao_id(),
            erro.codigo,
            erro.status_code,
        )
        return criar_resposta_erro(
            erro.codigo,
            erro.mensagem,
            erro.status_code,
            erro.detalhes,
        )

    @app.errorhandler(sqlalchemy_exc.IntegrityError)
    def responder_erro_integridade(
        erro: sqlalchemy_exc.IntegrityError,
    ) -> Response:
        if _violacao_unicidade(erro):
            current_app.logger.warning(
                "Conflito de slug requisicao_id=%s",
                obter_requisicao_id(),
            )
            return criar_resposta_erro(
                "slug_ja_existente",
                "Já existe um local turístico com este slug.",
                409,
                [
                    {
                        "campo": "slug",
                        "codigo": "valor_duplicado",
                        "mensagem": "O slug informado já está em uso.",
                    }
                ],
            )
        return responder_erro_interno(erro)

    def responder_banco_indisponivel(
        erro: sqlalchemy_exc.SQLAlchemyError,
    ) -> Response:
        current_app.logger.error(
            "Banco indisponível requisicao_id=%s",
            obter_requisicao_id(),
            exc_info=True,
        )
        return criar_resposta_erro(
            "banco_indisponivel",
            "O banco de dados está temporariamente indisponível.",
            503,
        )

    for tipo_erro in (
        sqlalchemy_exc.DisconnectionError,
        sqlalchemy_exc.InterfaceError,
        sqlalchemy_exc.OperationalError,
        sqlalchemy_exc.TimeoutError,
    ):
        app.register_error_handler(tipo_erro, responder_banco_indisponivel)

    @app.errorhandler(HTTPException)
    def responder_erro_http(erro: HTTPException) -> Response:
        configuracoes = {
            400: (
                "requisicao_invalida",
                "A requisição contém valores inválidos.",
            ),
            404: ("rota_nao_encontrada", "A rota solicitada não existe."),
            405: (
                "metodo_nao_permitido",
                "O método não é permitido para esta rota.",
            ),
        }
        codigo, mensagem = configuracoes.get(
            erro.code,
            ("erro_http", "Não foi possível processar a requisição."),
        )
        return criar_resposta_erro(
            codigo,
            mensagem,
            erro.code or 500,
        )

    @app.errorhandler(Exception)
    def responder_erro_interno(erro: Exception) -> Response:
        current_app.logger.error(
            "Falha interna requisicao_id=%s",
            obter_requisicao_id(),
            exc_info=True,
        )
        return criar_resposta_erro(
            "erro_interno",
            "Ocorreu um erro interno inesperado.",
            500,
        )
