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
