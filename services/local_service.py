from models.base import SessionLocal
from models.local_turistico import LocalTuristico
from utils.calculos import calcular_media
from utils.constants import CIDADES_RJ
from utils.exceptions import AppError


def listar_locais(cidade=None, categoria=None):
    """Lista todos os locais turísticos.

    Args:
        cidade (str): Nome da cidade.
        categoria (str): Categoria do local.

    Returns:
        list: Lista de locais turísticos.
    """
    session = SessionLocal()

    query = session.query(LocalTuristico)

    # Filtra por cidade se fornecida
    if cidade:
        query = query.filter(LocalTuristico.cidade.ilike(f"%{cidade}%"))

    # Filtra por categoria se fornecida
    if categoria:
        query = query.filter(LocalTuristico.categoria.ilike(f"%{categoria}%"))

    locais = query.all()

    if not locais:
        raise AppError("Nenhum local encontrado", 404)

    resultado = []

    for local in locais:
        media, total_avaliacoes = calcular_media(local.avaliacoes)

        resultado.append(
            {
                "id": local.id,
                "nome": local.nome,
                "cidade": local.cidade,
                "categoria": local.categoria,
                "descricao": local.descricao,
                "media_avaliacoes": media,
                "total_avaliacoes": total_avaliacoes,
            }
        )

    session.close()
    return resultado


def buscar_local(id: int):
    """Busca um local turístico por ID.

    Args:
        id (int): ID do local.

    Returns:
        dict: Dados do local turístico.

    Raises:
        AppError: Se o local não existir ou nota inválida.
    """
    session = SessionLocal()

    local = session.query(LocalTuristico).get(id)

    if not local:
        session.close()
        raise AppError("Local não encontrado", 404)

    notas = [avaliacao.nota for avaliacao in local.avaliacoes]
    media = round(sum(notas) / len(notas), 1) if notas else None

    resultado = {
        "id": local.id,
        "nome": local.nome,
        "cidade": local.cidade,
        "categoria": local.categoria,
        "descricao": local.descricao,
        "media_avaliacoes": media,
        "avaliacoes": [
            {
                "id": avaliacao.id,
                "nome_usuario": avaliacao.nome_usuario,
                "nota": avaliacao.nota,
                "comentario": avaliacao.comentario,
            }
            for avaliacao in local.avaliacoes
        ],
    }

    session.close()
    return resultado


def criar_local(dados: dict):
    """Cria um novo local turístico.

    Args:
        dados (dict): Dados do local.

    Returns:
        LocalTuristico: Objeto criado.
    """
    session = SessionLocal()
    
    # Normaliza a cidade (remove espaços e coloca em title case)
    # Ainda possui um problema nos casos de preposições (de, do, da, etc.)
    cidade = dados["cidade"].strip().title()
    
    if cidade not in CIDADES_RJ:
        session.close()
        raise AppError("Cidade inválida", 400)

    local = LocalTuristico(
        nome=dados["nome"],
        cidade=dados["cidade"],
        categoria=dados["categoria"],
        descricao=dados["descricao"],
    )

    session.add(local)
    session.commit()
    session.refresh(local)
    session.close()

    return local


def atualizar_local(id: int, dados: dict):
    """Atualiza um local turístico.

    Args:
        id (int): ID do local.
        dados (dict): Novos dados do local.

    Returns:
        LocalTuristico: Objeto atualizado.

    Raises:
        AppError: Se o local não existir ou nota inválida.
    """
    session = SessionLocal()

    local = session.query(LocalTuristico).get(id)

    if not local:
        session.close()
        raise AppError("Local não encontrado", 404)

    local.nome = dados.get("nome", local.nome)
    local.cidade = dados.get("cidade", local.cidade)
    local.categoria = dados.get("categoria", local.categoria)
    local.descricao = dados.get("descricao", local.descricao)

    session.commit()
    session.refresh(local)
    session.close()

    return local


def deletar_local(id: int):
    """Deleta um local turístico.

    Args:
        id (int): ID do local.

    Returns:
        str: Mensagem de sucesso.

    Raises:
        AppError: Se o local não existir.
    """
    session = SessionLocal()

    local = session.query(LocalTuristico).get(id)

    if not local:
        session.close()
        raise AppError("Local não encontrado", 404)

    session.delete(local)
    session.commit()
    session.close()

    return ""
