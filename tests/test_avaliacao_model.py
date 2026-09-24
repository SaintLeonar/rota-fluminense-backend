import os
import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import CheckConstraint, create_engine, delete, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.types import DateTime, Integer, String

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:5173")

from models.avaliacao import Avaliacao  # noqa: E402
from models.base import Base  # noqa: E402
from models.local_turistico import LocalTuristico  # noqa: E402


def build_local(slug="pao-de-acucar"):
    """Cria um local válido para os testes da avaliação."""
    return LocalTuristico(
        slug=slug,
        nome="Pão de Açúcar",
        categoria="Mirante",
        descricao="Complexo turístico com vista para a Baía de Guanabara.",
        cidade="Rio de Janeiro",
        bairro="Urca",
        regiao="Zona Sul",
        imagem="https://example.com/pao-de-acucar.jpg",
        destaque=True,
        latitude=-22.948559,
        longitude=-43.156579,
    )


class AvaliacaoModelTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(self.engine)

    def tearDown(self):
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_columns_match_official_contract(self):
        columns = Avaliacao.__table__.columns

        self.assertEqual(
            set(columns.keys()),
            {"id", "autor", "nota", "comentario", "criado_em", "local_id"},
        )
        self.assertIsInstance(columns.id.type, Integer)
        self.assertTrue(columns.id.primary_key)
        self.assertFalse(columns.id.index)
        self.assertIsInstance(columns.autor.type, String)
        self.assertEqual(columns.autor.type.length, 120)
        self.assertFalse(columns.autor.nullable)
        self.assertIsInstance(columns.nota.type, Integer)
        self.assertFalse(columns.nota.nullable)
        self.assertIsInstance(columns.comentario.type, String)
        self.assertEqual(columns.comentario.type.length, 1000)
        self.assertTrue(columns.comentario.nullable)
        self.assertIsInstance(columns.criado_em.type, DateTime)
        self.assertTrue(columns.criado_em.type.timezone)
        self.assertFalse(columns.criado_em.nullable)
        self.assertIsNotNone(columns.criado_em.default)
        self.assertFalse(columns.local_id.nullable)
        self.assertTrue(columns.local_id.index)

    def test_check_constraints_protect_domain_rules(self):
        constraints = {
            constraint.name: str(constraint.sqltext)
            for constraint in Avaliacao.__table__.constraints
            if isinstance(constraint, CheckConstraint)
        }

        self.assertEqual(
            constraints,
            {
                "ck_avaliacoes_autor_not_blank": "length(trim(autor)) > 0",
                "ck_avaliacoes_nota_range": "nota BETWEEN 1 AND 5",
                "ck_avaliacoes_comentario_not_blank": (
                    "comentario IS NULL OR length(trim(comentario)) > 0"
                ),
                "ck_avaliacoes_local_id_positive": "local_id > 0",
            },
        )

    def test_foreign_key_and_relationship_define_explicit_deletion(self):
        foreign_key = next(iter(Avaliacao.__table__.c.local_id.foreign_keys))
        relationship = LocalTuristico.avaliacoes.property

        self.assertEqual(foreign_key.target_fullname, "locais_turisticos.id")
        self.assertEqual(foreign_key.ondelete, "CASCADE")
        self.assertIn("delete-orphan", relationship.cascade)
        self.assertTrue(relationship.passive_deletes)

    def test_created_at_is_generated_in_utc(self):
        before = datetime.now(timezone.utc)

        with Session(self.engine) as session:
            local = build_local()
            avaliacao = Avaliacao(
                autor="Visitante",
                nota=5,
                comentario="Vista inesquecível.",
                local=local,
            )
            session.add(avaliacao)
            session.flush()

            self.assertEqual(avaliacao.criado_em.utcoffset(), timedelta(0))
            self.assertGreaterEqual(avaliacao.criado_em, before)
            self.assertLessEqual(
                avaliacao.criado_em,
                datetime.now(timezone.utc),
            )

    def test_invalid_domain_values_are_rejected(self):
        invalid_values = (
            {"autor": "   ", "nota": 5, "comentario": None},
            {"autor": "Visitante", "nota": 0, "comentario": None},
            {"autor": "Visitante", "nota": 6, "comentario": None},
            {"autor": "Visitante", "nota": 5, "comentario": "   "},
        )

        for index, values in enumerate(invalid_values):
            with self.subTest(values=values), Session(self.engine) as session:
                local = build_local(slug=f"local-{index}")
                session.add(local)
                session.flush()
                session.add(Avaliacao(local_id=local.id, **values))

                with self.assertRaises(IntegrityError):
                    session.flush()

    def test_evaluation_cannot_exist_without_a_local(self):
        with Session(self.engine) as session:
            session.add(
                Avaliacao(
                    autor="Visitante",
                    nota=5,
                    comentario=None,
                    local_id=999,
                )
            )

            with self.assertRaises(IntegrityError):
                session.flush()

    def test_database_cascade_prevents_orphan_evaluations(self):
        with Session(self.engine) as session:
            local = build_local()
            avaliacao = Avaliacao(
                autor="Visitante",
                nota=5,
                comentario=None,
                local=local,
            )
            session.add(local)
            session.commit()
            avaliacao_id = avaliacao.id
            local_id = local.id

            delete_local = delete(LocalTuristico).where(
                LocalTuristico.id == local_id,
            )
            session.execute(delete_local)
            session.commit()

            self.assertIsNone(session.get(Avaliacao, avaliacao_id))


if __name__ == "__main__":
    unittest.main()
