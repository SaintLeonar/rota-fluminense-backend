from models.base import SessionLocal
from models.local_turistico import LocalTuristico
from utils.calculos import calcular_media
from utils.exceptions import AppError

def listar_locais(cidade = None, categoria = None):
    session = SessionLocal()
    
    query = session.query(LocalTuristico)
    
    if cidade:
        query = query.filter(LocalTuristico.cidade.ilike(f"%{cidade}%"))
    
    if categoria:
        query = query.filter(LocalTuristico.categoria.ilike(f"%{categoria}%"))
    
    locais = query.all()
    
    resultado = []
    
    for local in locais:
        media, total_avaliacoes = calcular_media(local.avaliacoes)
        
        resultado.append({
            "id": local.id,
            "nome": local.nome,
            "cidade": local.cidade,
            "categoria": local.categoria,
            "descricao": local.descricao,
            "media_avaliacoes": media,
            "total_avaliacoes": total_avaliacoes
        })
    
    session.close()
    return resultado

def buscar_local(id):
    session = SessionLocal()
    
    local = session.query(LocalTuristico).get(id)
    
    if not local:
        session.close()
        raise AppError("Local não encontrado", 404)
    
    notas = [avaliacao.nota for avaliacao in local.avaliacoes]
    media = round(sum(notas) / len(notas), 2) if notas else None
    
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
                "comentario": avaliacao.comentario
            } for avaliacao in local.avaliacoes
        ]
    }
    
    session.close()
    return resultado

def criar_local(dados):
    session = SessionLocal()
    
    local = LocalTuristico(
        nome = dados["nome"],
        cidade = dados["cidade"],
        categoria = dados["categoria"],
        descricao = dados["descricao"]
    )
    
    session.add(local)
    session.commit()
    session.refresh(local)
    session.close()
    
    return local

def atualizar_local(id, dados):
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

def deletar_local(id):
    session = SessionLocal()
    
    local = session.query(LocalTuristico).get(id)
    
    if not local:
        session.close()
        raise AppError("Local não encontrado", 404)
    
    session.delete(local)
    session.commit()
    session.close()
    
    return ""