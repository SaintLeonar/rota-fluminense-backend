from typing import Any, Optional


class AppError(Exception):
    """Representa um erro esperado com contrato público explícito."""

    def __init__(
        self,
        codigo: str,
        mensagem: str,
        status_code: int,
        detalhes: Optional[list[dict[str, Any]]] = None,
    ) -> None:
        """Inicializa um erro esperado com sua representação pública."""
        self.codigo = codigo
        self.mensagem = mensagem
        self.status_code = status_code
        self.detalhes = detalhes or []
        super().__init__(mensagem)


class ClimaIndisponivelError(AppError):
    """Representa uma falha segura e temporária da integração climática."""

    _MOTIVOS_PERMITIDOS = frozenset(
        {
            "timeout",
            "conectividade",
            "resposta_http_invalida",
            "resposta_invalida",
        }
    )

    def __init__(self, motivo: str) -> None:
        """Inicializa o erro público com uma classificação interna segura."""
        if motivo not in self._MOTIVOS_PERMITIDOS:
            raise ValueError("O motivo da indisponibilidade climática é inválido.")
        self.motivo = motivo
        super().__init__(
            "clima_indisponivel",
            "O serviço de clima está temporariamente indisponível.",
            503,
        )


class CoordenadasIndisponiveisError(AppError):
    """Representa coordenadas persistidas inutilizáveis para clima."""

    def __init__(self) -> None:
        """Inicializa o erro público sem expor os valores persistidos."""
        super().__init__(
            "coordenadas_indisponiveis",
            (
                "As coordenadas deste local não estão disponíveis para "
                "consulta meteorológica."
            ),
            503,
        )
