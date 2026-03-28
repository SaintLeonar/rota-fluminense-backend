from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from models.base import Base

class LocalTuristico(Base):
    __tablename__ = "locais_turistico"
    
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    cidade = Column(String, nullable=False)
    categoria = Column(String, nullable=False)
    descricao = Column(String, nullable=False)
    
    avaliacoes = relationship("Avaliacao", back_populates="local", cascade="all, delete")