import json
import os
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from models.avaliacao import Avaliacao  # noqa: E402, F401
from models.base import Base  # noqa: E402
from models.local_turistico import LocalTuristico  # noqa: E402
from scripts import seed  # noqa: E402

EXPECTED_SLUGS = {
    "arpoador",
    "parque-lage",
    "museu-do-amanha",
    "vista-chinesa",
    "praia-de-sao-conrado",
    "museu-de-arte-moderna",
}


class SeedLocationsTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

    def tearDown(self):
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_manifest_loads_exactly_six_curated_locations(self):
        records = seed.load_local_seed_data()

        self.assertEqual(len(records), 6)
        self.assertEqual({record.slug for record in records}, EXPECTED_SLUGS)
        self.assertEqual(
            {record.categoria for record in records},
            {"praias", "parques", "museus", "mirantes"},
        )
        self.assertTrue(
            all(record.cidade == "Rio de Janeiro" for record in records)
        )
        self.assertTrue(
            all(
                record.imagem.startswith("/imagens/locais/")
                for record in records
            )
        )
        self.assertTrue(
            all(isinstance(record.latitude, Decimal) for record in records)
        )
        self.assertTrue(
            all(isinstance(record.longitude, Decimal) for record in records)
        )

    def test_category_is_normalized_from_manifest_rule(self):
        manifest = json.loads(
            seed.DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8")
        )
        manifest["locais"][0]["dados"]["categoria"] = "Praias"

        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest_path = Path(temporary_directory) / "manifest.json"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False),
                encoding="utf-8",
            )
            records = seed.load_local_seed_data(manifest_path)

        self.assertEqual(records[0].categoria, "praias")

    def test_invalid_manifest_is_rejected_before_persistence(self):
        manifest = json.loads(
            seed.DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8")
        )
        manifest["locais"][1]["dados"]["slug"] = "arpoador"

        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest_path = Path(temporary_directory) / "manifest.json"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(seed.SeedManifestError, "duplicado"):
                seed.load_local_seed_data(manifest_path)

    def test_seed_inserts_all_locations_in_one_transaction(self):
        with patch("scripts.seed.SessionLocal", self.session_factory):
            result = seed.run_location_seed()

        with self.session_factory() as session:
            persisted_slugs = set(session.scalars(select(LocalTuristico.slug)))

        self.assertEqual(result.inserted, 6)
        self.assertEqual(result.updated, 0)
        self.assertEqual(result.unchanged, 0)
        self.assertEqual(persisted_slugs, EXPECTED_SLUGS)

    def test_seed_reconciles_existing_location_by_slug(self):
        records = seed.load_local_seed_data()
        arpoador = next(
            record for record in records if record.slug == "arpoador"
        )
        outdated = LocalTuristico(
            slug=arpoador.slug,
            nome="Nome desatualizado",
            categoria="Praias",
            descricao=arpoador.descricao,
            cidade=arpoador.cidade,
            bairro=arpoador.bairro,
            regiao=arpoador.regiao,
            imagem=arpoador.imagem,
            destaque=False,
            latitude=arpoador.latitude,
            longitude=arpoador.longitude,
        )
        with self.session_factory.begin() as session:
            session.add(outdated)
            session.flush()
            original_id = outdated.id

        with self.session_factory.begin() as session:
            result = seed.seed_locations(session, records)

        with self.session_factory() as session:
            persisted = session.scalar(
                select(LocalTuristico).where(LocalTuristico.slug == "arpoador")
            )
            count = session.scalar(
                select(func.count()).select_from(LocalTuristico)
            )

        self.assertEqual(result.inserted, 5)
        self.assertEqual(result.updated, 1)
        self.assertEqual(result.unchanged, 0)
        self.assertEqual(count, 6)
        self.assertEqual(persisted.id, original_id)
        self.assertEqual(persisted.nome, arpoador.nome)
        self.assertEqual(persisted.categoria, "praias")
        self.assertTrue(persisted.destaque)


if __name__ == "__main__":
    unittest.main()
