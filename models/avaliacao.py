from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from models.base import Base

class Avaliacao(Base):
    __tablename__ = "avaliacoes"
    
    id = Column(Integer, primary_key=True, index=True)
    nome_usuario = Column(String, nullable=False)
    nota = Column(Integer, nullable=False)
    comentario = Column(String)
    local_id = Column(Integer, ForeignKey("locais_turistico.id"))
    
    local = relationship("LocalTuristico", back_populates="avaliacoes")
