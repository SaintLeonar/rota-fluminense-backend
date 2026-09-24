from datetime import datetime
from typing import Optional

import pydantic
from pydantic import BaseModel, Field, field_validator, model_validator

from schemas import openapi_examples
from schemas.validacao import InteiroPositivo, Nota, Slug, Texto120, Texto1000


class AvaliacaoInputSchema(BaseModel):
    model_config = pydantic.ConfigDict(
        extra="forbid",
        json_schema_extra={"example": openapi_examples.EVALUATION_INPUT_EXAMPLE},
    )

    autor: Texto120 = Field(
        description="Nome público da pessoa autora da avaliação.",
        examples=["Teste Swagger"],
    )
    nota: Nota = Field(
        description="Nota inteira entre 1 e 5.",
        examples=[5],
    )
    comentario: Optional[Texto1000] = Field(
        default=None,
        description="Comentário opcional; ausente é representado por null.",
        examples=["Ótimo lugar para acompanhar o pôr do sol."],
    )


class AvaliacaoUpdateSchema(BaseModel):
    model_config = pydantic.ConfigDict(
        extra="forbid",
        json_schema_extra={"example": openapi_examples.EVALUATION_UPDATE_EXAMPLE},
    )

    autor: Optional[Texto120] = Field(
        default=None,
        description="Novo nome da pessoa autora, quando enviado.",
        examples=["Teste Atualizacao Swagger"],
    )
    nota: Optional[Nota] = Field(
        default=None,
        description="Nova nota inteira entre 1 e 5, quando enviada.",
        examples=[4],
    )
    comentario: Optional[Texto1000] = Field(
        default=None,
        description=("Novo comentário; null remove explicitamente o comentário atual."),
        examples=["Vista bonita e ambiente agradável."],
    )

    @field_validator("autor", "nota", mode="before")
    @classmethod
    def rejeitar_nulo_em_campos_obrigatorios(cls, valor):
        """Rejeita remoção de autor ou nota em atualização parcial."""
        if valor is None:
            raise ValueError("O campo não aceita valor nulo.")
        return valor

    @model_validator(mode="after")
    def exigir_campo_presente(self):
        """Exige ao menos um campo mutável no PATCH."""
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualização.")
        return self


class AvaliacaoSchema(BaseModel):
    model_config = pydantic.ConfigDict(
        extra="forbid",
        json_schema_extra={"example": openapi_examples.EVALUATION_RESPONSE_EXAMPLE},
        openapi_extra={
            "description": "Representação de uma avaliação.",
            "example": openapi_examples.EVALUATION_RESPONSE_EXAMPLE,
        },
    )

    id: InteiroPositivo = Field(
        description="Identificador técnico somente leitura.",
        examples=[1],
    )
    local_id: InteiroPositivo = Field(
        description="Identificador técnico do local associado.",
        examples=[1],
    )
    autor: Texto120 = Field(description="Nome público da pessoa autora.")
    nota: Nota = Field(description="Nota inteira entre 1 e 5.")
    comentario: Optional[Texto1000] = Field(
        description="Comentário ou null quando ausente."
    )
    criado_em: datetime = Field(
        description="Instante de criação em ISO 8601 UTC com sufixo Z.",
        examples=["2026-06-05T12:00:00Z"],
    )


class AvaliacaoPathSchema(BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    avaliacao_id: InteiroPositivo = Field(
        description="Identificador técnico positivo da avaliação.",
        json_schema_extra={"example": 1},
    )


class AvaliacaoLocalPathSchema(BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    slug: Slug = Field(
        description="Slug público do local.",
        json_schema_extra={"example": "arpoador"},
    )


class AvaliacaoListSchema(BaseModel):
    model_config = pydantic.ConfigDict(
        extra="forbid",
        json_schema_extra={"example": openapi_examples.EVALUATION_LIST_EXAMPLE},
        openapi_extra={
            "description": "Coleção ordenada de avaliações do local.",
            "example": openapi_examples.EVALUATION_LIST_EXAMPLE,
        },
    )

    avaliacoes: list[AvaliacaoSchema] = Field(
        description=("Avaliações em ordem decrescente de criação e identificador.")
    )
