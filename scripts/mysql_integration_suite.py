"""Fornece componentes reutilizáveis para a validação integrada MySQL."""

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

_CASE_NAME_PATTERN = re.compile(r"[a-z][a-z0-9_]*")
_SENSITIVE_KEY_PARTS = (
    "credential",
    "credencial",
    "database_url",
    "password",
    "secret",
    "senha",
    "token",
)


@dataclass(frozen=True, slots=True)
class ValidationCase:
    """Representa um caso nomeado e executável da validação integrada."""

    name: str
    execute: Callable[[], None]

    def __post_init__(self):
        """Valida o identificador estável e a função do caso."""
        if _CASE_NAME_PATTERN.fullmatch(self.name) is None:
            raise ValueError("O nome do caso de validação não é canônico.")
        if not callable(self.execute):
            raise TypeError("O executor do caso deve ser chamável.")


def run_validation_cases(cases: Sequence[ValidationCase]):
    """Executa casos em ordem e retorna resultados públicos determinísticos."""
    names = set()
    results = []

    for case in cases:
        if case.name in names:
            raise ValueError("Os nomes dos casos devem ser únicos.")
        names.add(case.name)
        case.execute()
        results.append({"nome": case.name, "status": "ok"})

    return results


def _assert_safe_report_value(value):
    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            normalized_key = str(key).casefold()
            if any(part in normalized_key for part in _SENSITIVE_KEY_PARTS):
                raise ValueError(
                    "O relatório contém uma chave potencialmente sensível."
                )
            _assert_safe_report_value(nested_value)
        return

    is_sequence = isinstance(value, Sequence)
    is_scalar = isinstance(value, (str, bytes, bytearray))
    if is_sequence and not is_scalar:
        for nested_value in value:
            _assert_safe_report_value(nested_value)


def serialize_validation_report(report: Mapping):
    """Serializa relatório seguro com ordenação e formatação estáveis."""
    _assert_safe_report_value(report)
    return json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def print_validation_report(report: Mapping):
    """Imprime uma única representação JSON canônica do relatório."""
    print(serialize_validation_report(report))
