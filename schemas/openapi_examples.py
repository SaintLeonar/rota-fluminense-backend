"""Exemplos públicos e seguros reutilizados pela documentação OpenAPI."""

LOCAL_MUTABLE_EXAMPLE = {
    "nome": "Arpoador",
    "categoria": "praias",
    "descricao": "Praia e mirante conhecidos pelo pôr do sol.",
    "cidade": "Rio de Janeiro",
    "bairro": "Ipanema",
    "regiao": "Zona Sul",
    "imagem": "/imagens/locais/arpoador.jpg",
    "destaque": True,
    "latitude": -22.988,
    "longitude": -43.191,
}

LOCAL_INPUT_EXAMPLE = {
    **LOCAL_MUTABLE_EXAMPLE,
    "slug": "arpoador",
}

LOCAL_RESPONSE_EXAMPLE = {
    "id": 1,
    "slug": "arpoador",
    **LOCAL_MUTABLE_EXAMPLE,
    "nota_media": 4.5,
    "total_avaliacoes": 2,
}

PAGINATION_EXAMPLE = {
    "pagina": 1,
    "por_pagina": 12,
    "total_itens": 6,
    "total_paginas": 1,
}

LOCAL_LIST_EXAMPLE = {
    "locais": [LOCAL_RESPONSE_EXAMPLE],
    "paginacao": PAGINATION_EXAMPLE,
}

EVALUATION_INPUT_EXAMPLE = {
    "autor": "Marina Costa",
    "nota": 5,
    "comentario": "Ótimo lugar para acompanhar o pôr do sol.",
}

EVALUATION_UPDATE_EXAMPLE = {
    "nota": 4,
    "comentario": "Vista bonita e ambiente agradável.",
}

EVALUATION_RESPONSE_EXAMPLE = {
    "id": 1,
    "local_id": 1,
    **EVALUATION_INPUT_EXAMPLE,
    "criado_em": "2026-06-05T12:00:00Z",
}

EVALUATION_LIST_EXAMPLE = {
    "avaliacoes": [EVALUATION_RESPONSE_EXAMPLE],
}

CLIMATE_LOCAL_EXAMPLE = {
    "slug": "arpoador",
    "nome": "Arpoador",
}

CLIMATE_CURRENT_EXAMPLE = {
    "observado_em": "2026-09-09T17:15:00-03:00",
    "temperatura_c": 24.3,
    "sensacao_termica_c": 24.8,
    "precipitacao_mm": 0.0,
    "velocidade_vento_kmh": 18.2,
    "codigo_meteorologico": 1,
    "descricao": "Predominantemente limpo",
    "icone": "predominantemente_limpo",
}

CLIMATE_DAILY_EXAMPLES = [
    {
        "data": "2026-09-09",
        "temperatura_max_c": 27.1,
        "temperatura_min_c": 19.4,
        "probabilidade_precipitacao_max_pct": 10.0,
        "codigo_meteorologico": 1,
        "descricao": "Predominantemente limpo",
        "icone": "predominantemente_limpo",
    },
    {
        "data": "2026-09-10",
        "temperatura_max_c": 26.5,
        "temperatura_min_c": 20.1,
        "probabilidade_precipitacao_max_pct": 35.0,
        "codigo_meteorologico": 2,
        "descricao": "Parcialmente nublado",
        "icone": "parcialmente_nublado",
    },
    {
        "data": "2026-09-11",
        "temperatura_max_c": 25.8,
        "temperatura_min_c": 19.8,
        "probabilidade_precipitacao_max_pct": 45.0,
        "codigo_meteorologico": 61,
        "descricao": "Chuva fraca",
        "icone": "chuva_fraca",
    },
]

CLIMATE_CACHE_EXAMPLE = {
    "utilizado": False,
    "expira_em": "2026-09-09T20:46:00Z",
}

CLIMATE_RESPONSE_EXAMPLE = {
    "local": CLIMATE_LOCAL_EXAMPLE,
    "timezone": "America/Sao_Paulo",
    "atual": CLIMATE_CURRENT_EXAMPLE,
    "previsao": CLIMATE_DAILY_EXAMPLES,
    "atualizado_em": "2026-09-09T20:16:00Z",
    "cache": CLIMATE_CACHE_EXAMPLE,
}

CLIMATE_CACHE_RESPONSE_EXAMPLE = {
    **CLIMATE_RESPONSE_EXAMPLE,
    "cache": {
        **CLIMATE_CACHE_EXAMPLE,
        "utilizado": True,
    },
}

CLIMATE_RESPONSE_EXAMPLES = {
    "provedor": {
        "summary": "Resposta recém-obtida do provedor",
        "description": (
            "O Open-Meteo foi consultado e o resultado válido entrou no cache."
        ),
        "value": CLIMATE_RESPONSE_EXAMPLE,
    },
    "cacheValido": {
        "summary": "Resposta reutilizada do cache",
        "description": (
            "Uma entrada ainda válida evitou nova chamada ao Open-Meteo."
        ),
        "value": CLIMATE_CACHE_RESPONSE_EXAMPLE,
    },
}

ERROR_REQUEST_ID = "req_0123456789abcdef0123456789abcdef"

ERROR_EXAMPLES = {
    "requisicaoInvalida": {
        "summary": "Requisição inválida",
        "value": {
            "erro": {
                "codigo": "requisicao_invalida",
                "mensagem": "A requisição contém valores inválidos.",
                "detalhes": [
                    {
                        "campo": "pagina",
                        "codigo": "fora_do_limite",
                        "mensagem": (
                            "O valor está fora dos limites permitidos."
                        ),
                    }
                ],
                "requisicao_id": ERROR_REQUEST_ID,
            }
        },
    },
    "recursoNaoEncontrado": {
        "summary": "Recurso não encontrado",
        "value": {
            "erro": {
                "codigo": "local_nao_encontrado",
                "mensagem": "Local turístico não encontrado.",
                "detalhes": [],
                "requisicao_id": ERROR_REQUEST_ID,
            }
        },
    },
    "slugJaExistente": {
        "summary": "Slug já existente",
        "value": {
            "erro": {
                "codigo": "slug_ja_existente",
                "mensagem": "Já existe um local turístico com este slug.",
                "detalhes": [
                    {
                        "campo": "slug",
                        "codigo": "valor_duplicado",
                        "mensagem": "O slug informado já está em uso.",
                    }
                ],
                "requisicao_id": ERROR_REQUEST_ID,
            }
        },
    },
    "bancoIndisponivel": {
        "summary": "Banco temporariamente indisponível",
        "value": {
            "erro": {
                "codigo": "banco_indisponivel",
                "mensagem": (
                    "O banco de dados está temporariamente indisponível."
                ),
                "detalhes": [],
                "requisicao_id": ERROR_REQUEST_ID,
            }
        },
    },
    "erroInterno": {
        "summary": "Falha interna inesperada",
        "value": {
            "erro": {
                "codigo": "erro_interno",
                "mensagem": "Ocorreu um erro interno inesperado.",
                "detalhes": [],
                "requisicao_id": ERROR_REQUEST_ID,
            }
        },
    },
}

COORDINATES_UNAVAILABLE_ERROR_EXAMPLE = {
    "summary": "Coordenadas indisponíveis",
    "value": {
        "erro": {
            "codigo": "coordenadas_indisponiveis",
            "mensagem": (
                "As coordenadas deste local não estão disponíveis para "
                "consulta meteorológica."
            ),
            "detalhes": [],
            "requisicao_id": ERROR_REQUEST_ID,
        }
    },
}

CLIMATE_UNAVAILABLE_ERROR_EXAMPLE = {
    "summary": "Serviço de clima temporariamente indisponível",
    "value": {
        "erro": {
            "codigo": "clima_indisponivel",
            "mensagem": (
                "O serviço de clima está temporariamente indisponível."
            ),
            "detalhes": [],
            "requisicao_id": ERROR_REQUEST_ID,
        }
    },
}

CLIMATE_SERVICE_ERROR_EXAMPLES = {
    "bancoIndisponivel": ERROR_EXAMPLES["bancoIndisponivel"],
    "coordenadasIndisponiveis": COORDINATES_UNAVAILABLE_ERROR_EXAMPLE,
    "climaIndisponivel": CLIMATE_UNAVAILABLE_ERROR_EXAMPLE,
}

ERROR_SCHEMA_EXAMPLE = ERROR_EXAMPLES["requisicaoInvalida"]["value"]
