import re
import unicodedata
from typing import Optional

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SLUG_MAX_LENGTH = 120


def validar_slug(slug: str) -> str:
    """Valida um slug sem corrigi-lo silenciosamente."""
    if (
        not isinstance(slug, str)
        or not 1 <= len(slug) <= SLUG_MAX_LENGTH
        or SLUG_PATTERN.fullmatch(slug) is None
    ):
        raise ValueError("O slug informado não é canônico.")
    return slug


def gerar_slug(nome: str) -> str:
    """Gera um slug canônico e determinístico a partir do nome."""
    texto = unicodedata.normalize("NFKD", nome)
    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    ).casefold()
    slug = re.sub(r"[^a-z0-9]+", "-", texto).strip("-")
    return validar_slug(slug)


def resolver_slug(nome: str, slug: Optional[str] = None) -> str:
    """Preserva o slug explícito ou gera um valor quando omitido."""
    if slug is not None:
        return validar_slug(slug)
    return gerar_slug(nome)
