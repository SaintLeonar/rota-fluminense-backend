from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

UNKNOWN_DESCRIPTION = "Condição meteorológica desconhecida"
UNKNOWN_ICON = "condicao_desconhecida"


@dataclass(frozen=True, slots=True)
class CondicaoMeteorologica:
    """Representa a apresentação semântica de um código WMO."""

    codigo_meteorologico: int
    descricao: str
    icone: str


_CONDITIONS: Mapping[int, CondicaoMeteorologica] = MappingProxyType(
    {
        0: CondicaoMeteorologica(0, "Céu limpo", "ceu_limpo"),
        1: CondicaoMeteorologica(
            1,
            "Predominantemente limpo",
            "predominantemente_limpo",
        ),
        2: CondicaoMeteorologica(
            2,
            "Parcialmente nublado",
            "parcialmente_nublado",
        ),
        3: CondicaoMeteorologica(3, "Encoberto", "encoberto"),
        45: CondicaoMeteorologica(45, "Nevoeiro", "nevoeiro"),
        48: CondicaoMeteorologica(
            48,
            "Nevoeiro com geada",
            "nevoeiro_com_geada",
        ),
        51: CondicaoMeteorologica(51, "Garoa fraca", "garoa_fraca"),
        53: CondicaoMeteorologica(
            53,
            "Garoa moderada",
            "garoa_moderada",
        ),
        55: CondicaoMeteorologica(55, "Garoa intensa", "garoa_intensa"),
        56: CondicaoMeteorologica(
            56,
            "Garoa congelante fraca",
            "garoa_congelante_fraca",
        ),
        57: CondicaoMeteorologica(
            57,
            "Garoa congelante intensa",
            "garoa_congelante_intensa",
        ),
        61: CondicaoMeteorologica(61, "Chuva fraca", "chuva_fraca"),
        63: CondicaoMeteorologica(
            63,
            "Chuva moderada",
            "chuva_moderada",
        ),
        65: CondicaoMeteorologica(65, "Chuva forte", "chuva_forte"),
        66: CondicaoMeteorologica(
            66,
            "Chuva congelante fraca",
            "chuva_congelante_fraca",
        ),
        67: CondicaoMeteorologica(
            67,
            "Chuva congelante forte",
            "chuva_congelante_forte",
        ),
        71: CondicaoMeteorologica(71, "Neve fraca", "neve_fraca"),
        73: CondicaoMeteorologica(
            73,
            "Neve moderada",
            "neve_moderada",
        ),
        75: CondicaoMeteorologica(75, "Neve forte", "neve_forte"),
        77: CondicaoMeteorologica(77, "Grãos de neve", "graos_de_neve"),
        80: CondicaoMeteorologica(
            80,
            "Pancadas de chuva fracas",
            "pancadas_de_chuva_fracas",
        ),
        81: CondicaoMeteorologica(
            81,
            "Pancadas de chuva moderadas",
            "pancadas_de_chuva_moderadas",
        ),
        82: CondicaoMeteorologica(
            82,
            "Pancadas de chuva fortes",
            "pancadas_de_chuva_fortes",
        ),
        85: CondicaoMeteorologica(
            85,
            "Pancadas de neve fracas",
            "pancadas_de_neve_fracas",
        ),
        86: CondicaoMeteorologica(
            86,
            "Pancadas de neve fortes",
            "pancadas_de_neve_fortes",
        ),
        95: CondicaoMeteorologica(95, "Tempestade", "tempestade"),
        96: CondicaoMeteorologica(
            96,
            "Tempestade com granizo fraco",
            "tempestade_com_granizo_fraco",
        ),
        99: CondicaoMeteorologica(
            99,
            "Tempestade com granizo forte",
            "tempestade_com_granizo_forte",
        ),
    }
)

SUPPORTED_WMO_CODES = frozenset(_CONDITIONS)


def traduzir_codigo_wmo(codigo: int) -> CondicaoMeteorologica:
    """Traduz um código WMO inteiro ou devolve o fallback aprovado."""
    if type(codigo) is not int:
        raise TypeError("O código meteorológico deve ser um inteiro.")

    condition = _CONDITIONS.get(codigo)
    if condition is not None:
        return condition
    return CondicaoMeteorologica(
        codigo_meteorologico=codigo,
        descricao=UNKNOWN_DESCRIPTION,
        icone=UNKNOWN_ICON,
    )
