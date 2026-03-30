from models.base import SessionLocal
from models.avaliacao import Avaliacao
from models.local_turistico import LocalTuristico
from utils.exceptions import AppError

def listar_avaliacoes(local_id):
    session = SessionLocal()
    
    avaliacoes = session.query(Avaliacao).filter_by(local_id=local_id).all()
    
    resultado = []
    for avaliacao in avaliacoes:
        resultado.append({
            "id": avaliacao.id,
            "nome_usuario": avaliacao.nome_usuario,
            "nota": avaliacao.nota,
            "comentario": avaliacao.comentario
        })
        
    session.close()
    return resultado

def criar_avaliacao(local_id, dados):
    session = SessionLocal()
    
    local = session.query(LocalTuristico).get(local_id)
    if not local:
        session.close()
        raise AppError("Local não encontrado", 404)


    nota = dados.get("nota")
    
    if nota is None or nota < 1 or nota > 5:
        session.close()
        raise AppError("Nota deve ser entre 1 e 5", 400)
    
    avaliacao = Avaliacao(
        nome_usuario=dados.get("nome_usuario"),
        nota=nota,
        comentario=dados.get("comentario"),
        local_id=local_id
    )
    
    session.add(avaliacao)
    session.commit()
    session.refresh(avaliacao)
    session.close()
    
    return avaliacao

def deletar_avaliacao(id):
    session = SessionLocal()
    
    avaliacao = session.query(Avaliacao).get(id)
    
    if not avaliacao:
        session.close()
        raise AppError("Avaliação não encontrada", 404)
    
    session.delete(avaliacao)
    session.commit()
    session.close()
    
    return ""
