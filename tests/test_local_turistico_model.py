import os
import unittest

from sqlalchemy import Boolean, CheckConstraint, Numeric, String, create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:5173")

from models.avaliacao import Avaliacao  # noqa: E402, F401
from models.base import Base  # noqa: E402
from models.local_turistico import LocalTuristico  # noqa: E402


class LocalTuristicoModelTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def build_local(self, **overrides):
        data = {
            "slug": "arpoador",
            "nome": "Arpoador",
            "categoria": "praias",
            "descricao": "Praia e mirante conhecidos pelo pôr do sol.",
            "cidade": "Rio de Janeiro",
            "bairro": "Ipanema",
            "regiao": "Zona Sul",
            "imagem": "/imagens/arpoador.jpg",
            "latitude": -22.988500,
            "longitude": -43.191000,
        }
        data.update(overrides)
        return LocalTuristico(**data)

    def test_campos_obrigatorios_e_tamanhos_seguem_o_contrato(self):
        columns = LocalTuristico.__table__.columns
        expected_columns = {
            "id",
            "slug",
            "nome",
            "categoria",
            "descricao",
            "cidade",
            "bairro",
            "regiao",
            "imagem",
            "destaque",
            "latitude",
            "longitude",
        }
        self.assertEqual(set(columns.keys()), expected_columns)

        expected_lengths = {
            "slug": 120,
            "nome": 120,
            "categoria": 80,
            "descricao": 2000,
            "cidade": 120,
            "bairro": 120,
            "regiao": 80,
            "imagem": 500,
        }
        for name, length in expected_lengths.items():
            self.assertIsInstance(columns[name].type, String)
            self.assertEqual(columns[name].type.length, length)
            self.assertFalse(columns[name].nullable)

        self.assertIsInstance(columns.destaque.type, Boolean)
        self.assertFalse(columns.destaque.nullable)
        self.assertEqual(str(columns.destaque.server_default.arg), "0")
        self.assertIsInstance(columns.latitude.type, Numeric)
        self.assertEqual(
            (columns.latitude.type.precision, columns.latitude.type.scale),
            (8, 6),
        )
        self.assertFalse(columns.latitude.nullable)
        self.assertIsInstance(columns.longitude.type, Numeric)
        self.assertEqual(
            (columns.longitude.type.precision, columns.longitude.type.scale),
            (9, 6),
        )
        self.assertFalse(columns.longitude.nullable)

    def test_slug_e_campos_de_filtro_possuem_indices_esperados(self):
        columns = LocalTuristico.__table__.columns
        self.assertTrue(columns.slug.unique)
        self.assertTrue(columns.slug.index)
        self.assertTrue(columns.cidade.index)
        self.assertTrue(columns.categoria.index)
        self.assertFalse(columns.id.index)

        indexes = {
            index.name: (
                tuple(column.name for column in index.columns),
                index.unique,
            )
            for index in LocalTuristico.__table__.indexes
        }
        self.assertEqual(
            indexes["ix_locais_turisticos_slug"],
            (("slug",), True),
        )
        self.assertEqual(
            indexes["ix_locais_turisticos_cidade"],
            (("cidade",), False),
        )
        self.assertEqual(
            indexes["ix_locais_turisticos_categoria"],
            (("categoria",), False),
        )

    def test_coordenadas_possuem_constraints_de_faixa(self):
        constraints = {
            constraint.name: str(constraint.sqltext)
            for constraint in LocalTuristico.__table__.constraints
            if isinstance(constraint, CheckConstraint)
        }
        self.assertEqual(
            constraints["ck_locais_turisticos_latitude_range"],
            "latitude BETWEEN -90 AND 90",
        )
        self.assertEqual(
            constraints["ck_locais_turisticos_longitude_range"],
            "longitude BETWEEN -180 AND 180",
        )

    def test_destaque_assume_false_quando_omitido(self):
        with Session(self.engine) as session:
            local = self.build_local()
            session.add(local)
            session.flush()

            self.assertFalse(local.destaque)

    def test_slug_duplicado_e_coordenadas_invalidas_sao_rejeitados(self):
        with Session(self.engine) as session:
            session.add(self.build_local())
            session.commit()

            session.add(self.build_local(nome="Outro local"))
            with self.assertRaises(IntegrityError):
                session.commit()
            session.rollback()

            session.add(
                self.build_local(
                    slug="latitude-invalida",
                    latitude=90.000001,
                )
            )
            with self.assertRaises(IntegrityError):
                session.commit()
            session.rollback()

            session.add(
                self.build_local(
                    slug="longitude-invalida",
                    longitude=-180.000001,
                )
            )
            with self.assertRaises(IntegrityError):
                session.commit()


if __name__ == "__main__":
    unittest.main()
