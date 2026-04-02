from models.base import Base, engine


def init_db():
    """Cria todas as tabelas do banco de dados."""
    Base.metadata.create_all(bind=engine)
