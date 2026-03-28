from models.base import Base, engine
from models.local_turistico import LocalTuristico
from models.avaliacao import Avaliacao

def init_db():
    Base.metadata.create_all(bind=engine)