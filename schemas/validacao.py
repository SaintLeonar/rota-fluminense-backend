import ipaddress
import re
import unicodedata
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from pydantic import AfterValidator, BeforeValidator, Field, StringConstraints

from utils.constants import CATEGORIAS_LOCAL, CIDADES_RJ
from utils.slug import SLUG_MAX_LENGTH, SLUG_PATTERN


def _chave_normalizada(valor: str) -> str:
    texto = unicodedata.normalize("NFKD", valor)
    return "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    ).casefold()


_CIDADES_POR_CHAVE = {
    _chave_normalizada(cidade): cidade for cidade in CIDADES_RJ
}


def normalizar_categoria(valor: str) -> str:
    """Normaliza e valida uma categoria de local."""
    categoria = valor.casefold()
    if categoria not in CATEGORIAS_LOCAL:
        raise ValueError("A categoria informada não é aceita.")
    return categoria


def normalizar_cidade(valor: str) -> str:
    """Normaliza um município fluminense para o nome oficial."""
    cidade = _CIDADES_POR_CHAVE.get(_chave_normalizada(valor))
    if cidade is None:
        raise ValueError("A cidade deve ser um município do Rio de Janeiro.")
    return cidade


def validar_imagem_publica(valor: str) -> str:
    """Valida URL HTTP(S) pública ou caminho público absoluto."""
    if "\\" in valor or "\x00" in valor:
        raise ValueError("A imagem deve usar uma URL ou caminho público.")

    if valor.startswith("/"):
        partes = urlsplit(valor)
        segmentos = partes.path.split("/")
        if valor.startswith("//") or ".." in segmentos:
            raise ValueError("O caminho público da imagem é inválido.")
        return valor

    partes = urlsplit(valor)
    if partes.scheme not in {"http", "https"} or not partes.hostname:
        raise ValueError("A imagem deve usar uma URL ou caminho público.")
    if partes.username is not None or partes.password is not None:
        raise ValueError("A URL pública da imagem não aceita credenciais.")

    hostname = partes.hostname.casefold()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise ValueError("A URL da imagem deve possuir um host público.")

    try:
        endereco = ipaddress.ip_address(hostname)
    except ValueError:
        return valor

    if not endereco.is_global:
        raise ValueError("A URL da imagem deve possuir um host público.")
    return valor


def validar_booleano_consulta(valor: Any) -> bool:
    """Aceita somente booleano ou os literais HTTP true e false."""
    if isinstance(valor, bool):
        return valor
    if valor == "true":
        return True
    if valor == "false":
        return False
    raise ValueError("O valor deve ser true ou false.")


def converter_inteiro_consulta(valor: Any) -> int:
    """Converte um inteiro textual sem aceitar booleanos ou decimais."""
    if isinstance(valor, bool):
        raise ValueError("O valor deve ser um número inteiro.")
    if isinstance(valor, int):
        return valor
    if isinstance(valor, str) and re.fullmatch(r"[+-]?\d+", valor):
        return int(valor)
    raise ValueError("O valor deve ser um número inteiro.")


Texto80 = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=80,
    ),
]
Texto120 = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=SLUG_MAX_LENGTH,
    ),
]
Texto500 = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=500,
    ),
]
Texto1000 = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=1000,
    ),
]
Texto2000 = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=2000,
    ),
]

Slug = Annotated[
    str,
    StringConstraints(
        strict=True,
        min_length=1,
        max_length=120,
        pattern=SLUG_PATTERN,
    ),
]
Categoria = Annotated[Texto80, AfterValidator(normalizar_categoria)]
Cidade = Annotated[Texto120, AfterValidator(normalizar_cidade)]
ImagemPublica = Annotated[Texto500, AfterValidator(validar_imagem_publica)]
Latitude = Annotated[
    float,
    Field(strict=True, ge=-90, le=90, allow_inf_nan=False),
]
Longitude = Annotated[
    float,
    Field(strict=True, ge=-180, le=180, allow_inf_nan=False),
]
Nota = Annotated[int, Field(strict=True, ge=1, le=5)]
InteiroPositivo = Annotated[int, Field(strict=True, gt=0)]
InteiroNaoNegativo = Annotated[int, Field(strict=True, ge=0)]
Pagina = Annotated[
    int,
    BeforeValidator(converter_inteiro_consulta),
    Field(ge=1),
]
PorPagina = Annotated[
    int,
    BeforeValidator(converter_inteiro_consulta),
    Field(ge=1, le=100),
]
DestaqueConsulta = Annotated[bool, BeforeValidator(validar_booleano_consulta)]
OrdenacaoLocal = Literal[
    "nome_asc",
    "nome_desc",
    "nota_media_desc",
    "total_avaliacoes_desc",
    "destaque_desc",
]
