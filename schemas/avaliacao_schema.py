from pydantic import BaseModel
from typing import Optional

from models.avaliacao import Avaliacao


class AvaliacaoInputSchema(BaseModel):
    nome_usuario: str
    nota: int
    comentario: Optional[str] = None
    
    
class AvaliacaoSchema(AvaliacaoInputSchema):
    id: int
    nome_usuario: str
    nota: float
    comentario: str
    local_id: int
    
    
class AvaliacaoPathSchema(BaseModel):
    avaliacao_id: int
    
    
class AvaliacaoLocalPathSchema(BaseModel):
    local_id: int
    
    
class AvaliacaoListSchema(BaseModel):
    avaliacoes: list[AvaliacaoSchema]
    

def apresenta_avaliacoes(avaliacoes):
    resultado = []
    for avaliacao in avaliacoes:
        resultado.append({
            "id": avaliacao["id"],
            "nome_usuario": avaliacao["nome_usuario"],
            "nota": avaliacao["nota"],
            "comentario": avaliacao["comentario"]
        })
    
    return {"avaliacoes": resultado}