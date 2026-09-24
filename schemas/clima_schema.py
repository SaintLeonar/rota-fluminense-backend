"""Schemas públicos da resposta climática."""

from datetime import date, datetime, timedelta
from datetime import timezone as datetime_timezone
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

import pydantic
from pydantic import BaseModel, Field, StringConstraints

from schemas import openapi_examples, validacao

OPEN_METEO_TIMEZONE = "America/Sao_Paulo"

NumeroFinito = Annotated[float, Field(strict=True, allow_inf_nan=False)]
NumeroNaoNegativo = Annotated[
    float,
    Field(strict=True, ge=0, allow_inf_nan=False),
]
Percentual = Annotated[
    float,
    Field(strict=True, ge=0, le=100, allow_inf_nan=False),
]
CodigoMeteorologico = Annotated[int, Field(strict=True)]
DescricaoMeteorologica = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=120,
    ),
]
IconeMeteorologico = Annotated[
    str,
    StringConstraints(
        strict=True,
        min_length=1,
        max_length=80,
        pattern=r"^[a-z0-9]+(?:_[a-z0-9]+)*$",
    ),
]


def _validar_instante_utc(valor: datetime) -> datetime:
    if valor.tzinfo is None or valor.utcoffset() != timedelta(0):
        raise ValueError("O instante deve possuir timezone UTC explícito.")
    return valor.astimezone(datetime_timezone.utc)


class ClimaLocalSchema(BaseModel):
    """Identifica publicamente o local associado à previsão."""

    model_config = pydantic.ConfigDict(
        extra="forbid",
        json_schema_extra={"example": openapi_examples.CLIMATE_LOCAL_EXAMPLE},
    )

    slug: validacao.Slug = Field(
        description="Identificador público estável do local.",
        examples=["arpoador"],
    )
    nome: validacao.Texto120 = Field(
        description="Nome público atual do local.",
        examples=["Arpoador"],
    )


class ClimaAtualSchema(BaseModel):
    """Representa as condições meteorológicas observadas."""

    model_config = pydantic.ConfigDict(
        extra="forbid",
        json_schema_extra={"example": openapi_examples.CLIMATE_CURRENT_EXAMPLE},
    )

    observado_em: datetime = Field(
        description=("Instante observado em ISO 8601 com offset de America/Sao_Paulo."),
        examples=["2026-09-09T17:15:00-03:00"],
    )
    temperatura_c: NumeroFinito = Field(
        description="Temperatura do ar em graus Celsius.", examples=[24.3]
    )
    sensacao_termica_c: NumeroFinito = Field(
        description="Sensação térmica em graus Celsius.", examples=[24.8]
    )
    precipitacao_mm: NumeroNaoNegativo = Field(
        description="Precipitação acumulada em milímetros.", examples=[0.0]
    )
    velocidade_vento_kmh: NumeroNaoNegativo = Field(
        description="Velocidade do vento em quilômetros por hora.",
        examples=[18.2],
    )
    codigo_meteorologico: CodigoMeteorologico = Field(
        description="Código meteorológico WMO preservado do provedor.",
        examples=[1],
    )
    descricao: DescricaoMeteorologica = Field(
        description="Descrição curta da condição em português.",
        examples=["Predominantemente limpo"],
    )
    icone: IconeMeteorologico = Field(
        description="Chave semântica estável para representação visual.",
        examples=["predominantemente_limpo"],
    )

    @pydantic.field_validator("observado_em")
    @classmethod
    def validar_timezone_observado(cls, valor: datetime) -> datetime:
        """Exige offset coerente com America/Sao_Paulo no instante."""
        if valor.tzinfo is None or valor.utcoffset() is None:
            raise ValueError("O instante observado deve possuir timezone.")
        offset_esperado = valor.astimezone(ZoneInfo(OPEN_METEO_TIMEZONE)).utcoffset()
        if valor.utcoffset() != offset_esperado:
            raise ValueError(
                "O instante observado deve usar o offset de America/Sao_Paulo."
            )
        return valor


class ClimaPrevisaoDiariaSchema(BaseModel):
    """Representa um dia da previsão meteorológica."""

    model_config = pydantic.ConfigDict(
        extra="forbid",
        json_schema_extra={"example": openapi_examples.CLIMATE_DAILY_EXAMPLES[0]},
    )

    data: date = Field(
        description="Data civil da previsão no formato YYYY-MM-DD.",
        examples=["2026-09-09"],
    )
    temperatura_max_c: NumeroFinito = Field(
        description="Temperatura máxima prevista em graus Celsius.",
        examples=[27.1],
    )
    temperatura_min_c: NumeroFinito = Field(
        description="Temperatura mínima prevista em graus Celsius.",
        examples=[19.4],
    )
    probabilidade_precipitacao_max_pct: Percentual = Field(
        description="Probabilidade máxima de precipitação, de 0 a 100%.",
        examples=[10.0],
    )
    codigo_meteorologico: CodigoMeteorologico = Field(
        description="Código meteorológico WMO preservado do provedor.",
        examples=[1],
    )
    descricao: DescricaoMeteorologica = Field(
        description="Descrição curta da condição em português.",
        examples=["Predominantemente limpo"],
    )
    icone: IconeMeteorologico = Field(
        description="Chave semântica estável para representação visual.",
        examples=["predominantemente_limpo"],
    )


class ClimaCacheSchema(BaseModel):
    """Informa a origem e o limite de validade da resposta."""

    model_config = pydantic.ConfigDict(
        extra="forbid",
        json_schema_extra={"example": openapi_examples.CLIMATE_CACHE_EXAMPLE},
    )

    utilizado: pydantic.StrictBool = Field(
        description="Indica se uma entrada válida evitou chamada ao provedor.",
        examples=[False],
    )
    expira_em: datetime = Field(
        description="Limite de validade em ISO 8601 UTC com sufixo Z.",
        examples=["2026-09-09T20:46:00Z"],
    )

    @pydantic.field_validator("expira_em")
    @classmethod
    def validar_expiracao_utc(cls, valor: datetime) -> datetime:
        """Exige instante de expiração consciente e normalizado em UTC."""
        return _validar_instante_utc(valor)


class ClimaResponseSchema(BaseModel):
    """Representa a resposta pública completa da consulta climática."""

    model_config = pydantic.ConfigDict(
        extra="forbid",
        json_schema_extra={"example": openapi_examples.CLIMATE_RESPONSE_EXAMPLE},
        openapi_extra={
            "description": "Condições atuais e previsão de três dias.",
            "examples": openapi_examples.CLIMATE_RESPONSE_EXAMPLES,
        },
    )

    local: ClimaLocalSchema = Field(
        description="Identificação pública mínima do local."
    )
    timezone: Literal["America/Sao_Paulo"] = Field(
        description="Timezone fixo usado na consulta meteorológica.",
        examples=[OPEN_METEO_TIMEZONE],
    )
    atual: ClimaAtualSchema = Field(description="Condições meteorológicas observadas.")
    previsao: Annotated[
        tuple[ClimaPrevisaoDiariaSchema, ...],
        Field(min_length=3, max_length=3),
    ] = Field(description="Exatamente três dias ordenados por data crescente.")
    atualizado_em: datetime = Field(
        description="Instante de atualização em ISO 8601 UTC com sufixo Z.",
        examples=["2026-09-09T20:16:00Z"],
    )
    cache: ClimaCacheSchema = Field(
        description="Metadados de origem e validade do cache."
    )

    @pydantic.field_validator("previsao")
    @classmethod
    def validar_ordem_previsao(
        cls,
        valor: tuple[ClimaPrevisaoDiariaSchema, ...],
    ) -> tuple[ClimaPrevisaoDiariaSchema, ...]:
        """Exige datas únicas e estritamente crescentes."""
        datas = tuple(item.data for item in valor)
        if datas != tuple(sorted(datas)) or len(set(datas)) != len(datas):
            raise ValueError("A previsão deve possuir datas únicas e crescentes.")
        return valor

    @pydantic.field_validator("atualizado_em")
    @classmethod
    def validar_atualizacao_utc(cls, valor: datetime) -> datetime:
        """Exige instante de atualização consciente e normalizado em UTC."""
        return _validar_instante_utc(valor)

    @pydantic.model_validator(mode="after")
    def validar_intervalo_cache(self):
        """Exige expiração posterior ao instante de atualização."""
        if self.cache.expira_em <= self.atualizado_em:
            raise ValueError("A expiração do cache deve ser posterior à atualização.")
        return self
