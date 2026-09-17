from models.avaliacao import Avaliacao
from models.base import SessionLocal
from models.local_turistico import LocalTuristico
from services.session_manager import gerenciar_sessao
from utils.exceptions import AppError


def listar_avaliacoes(slug: str) -> list[dict]:
    """Lista as avaliações de um local pelo slug público.

    Args:
        slug (str): Slug canônico do local.

    Returns:
        list[dict]: Avaliações em ordem cronológica decrescente.

    Raises:
        AppError: Se o local não existir.
    """
    with gerenciar_sessao(SessionLocal) as session:
        local_id = (
            session.query(LocalTuristico.id)
            .filter(LocalTuristico.slug == slug)
            .scalar()
        )
        if local_id is None:
            raise AppError(
                "local_nao_encontrado",
                "Local turístico não encontrado.",
                404,
            )

        avaliacoes = (
            session.query(Avaliacao)
            .filter(Avaliacao.local_id == local_id)
            .order_by(Avaliacao.criado_em.desc(), Avaliacao.id.desc())
            .all()
        )

        return [
            {
                "id": avaliacao.id,
                "local_id": avaliacao.local_id,
                "autor": avaliacao.autor,
                "nota": avaliacao.nota,
                "comentario": avaliacao.comentario,
                "criado_em": avaliacao.criado_em,
            }
            for avaliacao in avaliacoes
        ]


def criar_avaliacao(slug: str, dados: dict) -> dict:
    """Cria uma avaliação vinculada ao local identificado pelo slug.

    Args:
        slug (str): Slug canônico do local.
        dados (dict): Dados da avaliação.

    Returns:
        dict: Representação materializada da avaliação criada.

    Raises:
        AppError: Se o local não existir.
    """
    with gerenciar_sessao(SessionLocal) as session:
        local_id = (
            session.query(LocalTuristico.id)
            .filter(LocalTuristico.slug == slug)
            .scalar()
        )
        if local_id is None:
            raise AppError(
                "local_nao_encontrado",
                "Local turístico não encontrado.",
                404,
            )

        avaliacao = Avaliacao(
            autor=dados["autor"],
            nota=dados["nota"],
            comentario=dados.get("comentario"),
            local_id=local_id,
        )
        session.add(avaliacao)
        session.commit()
        session.refresh(avaliacao)

        return {
            "id": avaliacao.id,
            "local_id": avaliacao.local_id,
            "autor": avaliacao.autor,
            "nota": avaliacao.nota,
            "comentario": avaliacao.comentario,
            "criado_em": avaliacao.criado_em,
        }


def atualizar_avaliacao(avaliacao_id: int, dados: dict) -> dict:
    """Atualiza parcialmente os campos mutáveis de uma avaliação.

    Args:
        avaliacao_id (int): Identificador técnico da avaliação.
        dados (dict): Campos mutáveis presentes no corpo da requisição.

    Returns:
        dict: Representação materializada da avaliação atualizada.

    Raises:
        AppError: Se a avaliação não existir.
    """
    with gerenciar_sessao(SessionLocal) as session:
        avaliacao = session.get(Avaliacao, avaliacao_id)
        if avaliacao is None:
            raise AppError(
                "avaliacao_nao_encontrada",
                "Avaliação não encontrada.",
                404,
            )

        for campo, valor in dados.items():
            setattr(avaliacao, campo, valor)

        session.commit()
        session.refresh(avaliacao)

        return {
            "id": avaliacao.id,
            "local_id": avaliacao.local_id,
            "autor": avaliacao.autor,
            "nota": avaliacao.nota,
            "comentario": avaliacao.comentario,
            "criado_em": avaliacao.criado_em,
        }


def deletar_avaliacao(avaliacao_id: int) -> None:
    """Exclui uma avaliação pelo identificador técnico.

    Args:
        avaliacao_id (int): Identificador técnico da avaliação.

    Raises:
        AppError: Se a avaliação não existir.
    """
    with gerenciar_sessao(SessionLocal) as session:
        avaliacao = session.get(Avaliacao, avaliacao_id)
        if avaliacao is None:
            raise AppError(
                "avaliacao_nao_encontrada",
                "Avaliação não encontrada.",
                404,
            )

        session.delete(avaliacao)
        session.commit()
