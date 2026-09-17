from sqlalchemy import case, func

from models.avaliacao import Avaliacao
from models.base import SessionLocal
from models.local_turistico import LocalTuristico
from services.session_manager import gerenciar_sessao
from utils.exceptions import AppError
from utils.slug import resolver_slug


def _erro_slug_invalido() -> AppError:
    return AppError(
        "requisicao_invalida",
        "A requisição contém valores inválidos.",
        400,
        [
            {
                "campo": "slug",
                "codigo": "valor_invalido",
                "mensagem": "Não foi possível obter um slug canônico.",
            }
        ],
    )


def _erro_slug_existente() -> AppError:
    return AppError(
        "slug_ja_existente",
        "Já existe um local turístico com este slug.",
        409,
        [
            {
                "campo": "slug",
                "codigo": "valor_duplicado",
                "mensagem": "O slug informado já está em uso.",
            }
        ],
    )


def _slug_em_uso(session, slug: str) -> bool:
    return (
        session.query(LocalTuristico.id)
        .filter(LocalTuristico.slug == slug)
        .first()
        is not None
    )


def _consulta_locais_com_agregados(session):
    agregados = (
        session.query(
            Avaliacao.local_id.label("local_id"),
            func.avg(Avaliacao.nota).label("nota_media"),
            func.count(Avaliacao.id).label("total_avaliacoes"),
        )
        .group_by(Avaliacao.local_id)
        .subquery()
    )
    nota_media = agregados.c.nota_media
    total_avaliacoes = func.coalesce(
        agregados.c.total_avaliacoes,
        0,
    ).label("total_avaliacoes")
    query = session.query(
        LocalTuristico,
        nota_media,
        total_avaliacoes,
    ).outerjoin(
        agregados,
        agregados.c.local_id == LocalTuristico.id,
    )
    return query, nota_media, total_avaliacoes


def _mapear_local_com_agregados(linha):
    local, media, quantidade_avaliacoes = linha
    return {
        "id": local.id,
        "slug": local.slug,
        "nome": local.nome,
        "categoria": local.categoria,
        "descricao": local.descricao,
        "cidade": local.cidade,
        "bairro": local.bairro,
        "regiao": local.regiao,
        "imagem": local.imagem,
        "destaque": bool(local.destaque),
        "latitude": float(local.latitude),
        "longitude": float(local.longitude),
        "nota_media": None if media is None else round(float(media), 1),
        "total_avaliacoes": int(quantidade_avaliacoes),
    }


def _aplicar_ordenacao(query, ordenar_por, nota_media, total_avaliacoes):
    ordenacoes = {
        "nome_asc": (LocalTuristico.nome.asc(), LocalTuristico.id.asc()),
        "nome_desc": (LocalTuristico.nome.desc(), LocalTuristico.id.asc()),
        "nota_media_desc": (
            case((nota_media.is_(None), 1), else_=0).asc(),
            nota_media.desc(),
            LocalTuristico.id.asc(),
        ),
        "total_avaliacoes_desc": (
            total_avaliacoes.desc(),
            LocalTuristico.id.asc(),
        ),
        "destaque_desc": (
            LocalTuristico.destaque.desc(),
            LocalTuristico.id.asc(),
        ),
    }
    return query.order_by(*ordenacoes[ordenar_por])


def listar_locais(
    cidade=None,
    categoria=None,
    destaque=None,
    pagina=1,
    por_pagina=12,
    ordenar_por="nome_asc",
):
    """Lista uma página de locais com filtros e agregados calculados em SQL.

    Args:
        cidade (str): Nome da cidade.
        categoria (str): Categoria do local.
        destaque (bool): Seleção opcional por destaque.
        pagina (int): Página solicitada.
        por_pagina (int): Quantidade de itens por página.
        ordenar_por (str): Ordenação canônica solicitada.

    Returns:
        tuple: Locais da página, total de itens e total de páginas.
    """
    with gerenciar_sessao(SessionLocal) as session:
        query, nota_media, total_avaliacoes = _consulta_locais_com_agregados(
            session
        )

        if cidade is not None:
            query = query.filter(LocalTuristico.cidade == cidade)

        if categoria is not None:
            query = query.filter(LocalTuristico.categoria == categoria)

        if destaque is not None:
            query = query.filter(LocalTuristico.destaque == destaque)

        total_itens = query.count()
        total_paginas = (total_itens + por_pagina - 1) // por_pagina
        query = _aplicar_ordenacao(
            query,
            ordenar_por,
            nota_media,
            total_avaliacoes,
        )
        linhas = (
            query.offset((pagina - 1) * por_pagina).limit(por_pagina).all()
        )

        resultado = [_mapear_local_com_agregados(linha) for linha in linhas]
        return resultado, total_itens, total_paginas


def buscar_local(slug: str):
    """Busca um local turístico pelo slug público.

    Args:
        slug (str): Slug canônico do local.

    Returns:
        dict: Dados do local turístico.

    Raises:
        AppError: Se o local não existir.
    """
    with gerenciar_sessao(SessionLocal) as session:
        query, _, _ = _consulta_locais_com_agregados(session)
        linha = query.filter(LocalTuristico.slug == slug).one_or_none()

        if linha is None:
            raise AppError(
                "local_nao_encontrado",
                "Local turístico não encontrado.",
                404,
            )

        return _mapear_local_com_agregados(linha)


def criar_local(dados: dict) -> dict:
    """Persiste um local turístico com todos os campos contratuais.

    Args:
        dados (dict): Dados do local.

    Returns:
        dict: Representação materializada do local criado.
    """
    try:
        slug = resolver_slug(dados["nome"], dados.get("slug"))
    except ValueError:
        raise _erro_slug_invalido() from None

    with gerenciar_sessao(SessionLocal) as session:
        if _slug_em_uso(session, slug):
            raise _erro_slug_existente()

        local = LocalTuristico(
            slug=slug,
            nome=dados["nome"],
            categoria=dados["categoria"],
            descricao=dados["descricao"],
            cidade=dados["cidade"],
            bairro=dados["bairro"],
            regiao=dados["regiao"],
            imagem=dados["imagem"],
            destaque=dados["destaque"],
            latitude=dados["latitude"],
            longitude=dados["longitude"],
        )

        session.add(local)
        session.commit()
        session.refresh(local)
        query, _, _ = _consulta_locais_com_agregados(session)
        linha = query.filter(LocalTuristico.slug == slug).one()
        return _mapear_local_com_agregados(linha)


def atualizar_local(slug: str, dados: dict):
    """Substitui todos os campos mutáveis de um local turístico.

    Args:
        slug (str): Slug canônico do local.
        dados (dict): Conjunto completo de campos mutáveis.

    Returns:
        dict: Representação completa do local atualizado.

    Raises:
        AppError: Se o local não existir.
    """
    with gerenciar_sessao(SessionLocal) as session:
        local = (
            session.query(LocalTuristico)
            .filter(LocalTuristico.slug == slug)
            .one_or_none()
        )

        if local is None:
            raise AppError(
                "local_nao_encontrado",
                "Local turístico não encontrado.",
                404,
            )

        for campo in (
            "nome",
            "categoria",
            "descricao",
            "cidade",
            "bairro",
            "regiao",
            "imagem",
            "destaque",
            "latitude",
            "longitude",
        ):
            setattr(local, campo, dados[campo])

        session.commit()
        query, _, _ = _consulta_locais_com_agregados(session)
        linha = query.filter(LocalTuristico.slug == slug).one()
        return _mapear_local_com_agregados(linha)


def deletar_local(slug: str) -> None:
    """Exclui pelo slug um local e suas avaliações por cascata no banco.

    Args:
        slug (str): Slug canônico do local.

    Raises:
        AppError: Se o local não existir.
    """
    with gerenciar_sessao(SessionLocal) as session:
        local = (
            session.query(LocalTuristico)
            .filter(LocalTuristico.slug == slug)
            .one_or_none()
        )

        if local is None:
            raise AppError(
                "local_nao_encontrado",
                "Local turístico não encontrado.",
                404,
            )

        session.delete(local)
        session.commit()
