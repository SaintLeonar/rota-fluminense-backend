from rota_fluminense_backend.models.avaliacao import Avaliacao
from rota_fluminense_backend.models.local_turistico import LocalTuristico


def serializar_local(local: LocalTuristico):
    """Serializa um objeto Local em um dicionário.

    Args:
        local (Local): Objeto Local a ser serializado.

    Returns:
        dict: Dicionário com os dados do local.
    """
    return {
        "id": local.id,
        "nome": local.nome,
        "cidade": local.cidade,
        "categoria": local.categoria,
        "descricao": local.descricao,
    }


def serializar_avaliacao(avaliacao: Avaliacao):
    """Serializa um objeto Avaliacao em um dicionário.

    Args:
        avaliacao (Avaliacao): Objeto Avaliacao a ser serializado.

    Returns:
        dict: Dicionário com os dados do local.
    """
    return {
        "id": avaliacao.id,
        "nome_usuario": avaliacao.nome_usuario,
        "nota": avaliacao.nota,
        "comentario": avaliacao.comentario,
        "local_id": avaliacao.local_id,
    }
