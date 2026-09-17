from collections.abc import Callable, Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session


@contextmanager
def gerenciar_sessao(
    session_factory: Callable[[], Session],
) -> Iterator[Session]:
    """Garante rollback em falhas e fechamento em qualquer caminho."""
    session = session_factory()

    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
