from sqlalchemy import CheckConstraint, Column, text
from sqlalchemy.orm import relationship
from sqlalchemy.types import Boolean, Integer, Numeric, String

from models.base import Base


class LocalTuristico(Base):
    __tablename__ = "locais_turisticos"
    __table_args__ = (
        CheckConstraint(
            "latitude BETWEEN -90 AND 90",
            name="ck_locais_turisticos_latitude_range",
        ),
        CheckConstraint(
            "longitude BETWEEN -180 AND 180",
            name="ck_locais_turisticos_longitude_range",
        ),
    )

    id = Column(Integer, primary_key=True)
    slug = Column(String(120), nullable=False, unique=True, index=True)
    nome = Column(String(120), nullable=False)
    categoria = Column(String(80), nullable=False, index=True)
    descricao = Column(String(2000), nullable=False)
    cidade = Column(String(120), nullable=False, index=True)
    bairro = Column(String(120), nullable=False)
    regiao = Column(String(80), nullable=False)
    imagem = Column(String(500), nullable=False)
    destaque = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
    )
    latitude = Column(Numeric(8, 6), nullable=False)
    longitude = Column(Numeric(9, 6), nullable=False)

    avaliacoes = relationship(
        "Avaliacao",
        back_populates="local",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
