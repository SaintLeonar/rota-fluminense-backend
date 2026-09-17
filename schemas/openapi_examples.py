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

ERROR_SCHEMA_EXAMPLE = ERROR_EXAMPLES["requisicaoInvalida"]["value"]
