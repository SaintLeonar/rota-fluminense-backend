from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.types import DateTime, Integer, String

from models.base import Base


def utc_now():
    """Retorna o instante atual em UTC."""
    return datetime.now(timezone.utc)


class Avaliacao(Base):

    __tablename__ = "avaliacoes"
    __table_args__ = (
        CheckConstraint(
            "length(trim(autor)) > 0",
            name="ck_avaliacoes_autor_not_blank",
        ),
        CheckConstraint(
            "nota BETWEEN 1 AND 5",
            name="ck_avaliacoes_nota_range",
        ),
        CheckConstraint(
            "comentario IS NULL OR length(trim(comentario)) > 0",
            name="ck_avaliacoes_comentario_not_blank",
        ),
        CheckConstraint(
            "local_id > 0",
            name="ck_avaliacoes_local_id_positive",
        ),
    )

    id = Column(Integer, primary_key=True)
    autor = Column(String(120), nullable=False)
    nota = Column(Integer, nullable=False)
    comentario = Column(String(1000), nullable=True)
    criado_em = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    local_id = Column(
        Integer,
        ForeignKey("locais_turisticos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    local = relationship("LocalTuristico", back_populates="avaliacoes")
