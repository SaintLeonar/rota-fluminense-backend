from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas import openapi_examples


class ErrorDetailSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campo: Optional[str] = Field(
        description="Campo relacionado ao erro, quando aplicável.",
        examples=["pagina"],
    )
    codigo: str = Field(
        description="Código estável do detalhe de validação.",
        examples=["fora_do_limite"],
    )
    mensagem: str = Field(
        description="Mensagem pública do detalhe.",
        examples=["O valor está fora dos limites permitidos."],
    )


class ErrorContentSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: str = Field(
        description="Código público do erro.",
        examples=["requisicao_invalida"],
    )
    mensagem: str = Field(
        description="Mensagem pública sem detalhes técnicos.",
        examples=["A requisição contém valores inválidos."],
    )
    detalhes: list[ErrorDetailSchema] = Field(
        description="Detalhes seguros; lista vazia quando não se aplicam."
    )
    requisicao_id: str = Field(
        description="Identificador opaco também retornado em X-Request-ID.",
        examples=[openapi_examples.ERROR_REQUEST_ID],
    )


class ErrorSchema(BaseModel):
    """Representa o envelope público e canônico de erro."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": openapi_examples.ERROR_SCHEMA_EXAMPLE},
        openapi_extra={
            "description": "Envelope público e canônico de erro.",
            "examples": openapi_examples.ERROR_EXAMPLES,
        },
    )

    erro: ErrorContentSchema = Field(description="Conteúdo público do erro.")


CLIMATE_SERVICE_UNAVAILABLE_RESPONSE = {
    "description": ("Persistência, coordenadas ou serviço climático indisponível."),
    "content": {
        "application/json": {
            "schema": {"$ref": "#/components/schemas/ErrorSchema"},
            "examples": openapi_examples.CLIMATE_SERVICE_ERROR_EXAMPLES,
        }
    },
}
