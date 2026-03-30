def serializar_local(local):
    return {
        "id": local.id,
        "nome": local.nome,
        "cidade": local.cidade,
        "categoria": local.categoria,
        "descricao": local.descricao
    }
    
def serializar_avaliacao(avaliacao):
    return {
        "id": avaliacao.id,
        "nome_usuario": avaliacao.nome_usuario,
        "nota": avaliacao.nota,
        "comentario": avaliacao.comentario,
        "local_id": avaliacao.local_id
    }
