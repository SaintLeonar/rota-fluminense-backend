import json
import os
import tempfile
import unittest
from collections import Counter
from datetime import timezone
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from models.avaliacao import Avaliacao  # noqa: E402
from models.base import Base  # noqa: E402
from models.local_turistico import LocalTuristico  # noqa: E402
from scripts import seed  # noqa: E402

EXPECTED_EVALUATIONS_BY_SLUG = {
    "arpoador": 2,
    "parque-lage": 1,
    "museu-do-amanha": 1,
    "vista-chinesa": 1,
    "praia-de-sao-conrado": 1,
}


class SeedEvaluationsTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

    def tearDown(self):
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def write_manifest(self, manifest):
        """Grava uma variação temporária do manifesto."""
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        manifest_path = Path(temporary_directory.name) / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False),
            encoding="utf-8",
        )
        return manifest_path

    def read_manifest(self):
        """Lê o manifesto oficial para testes de validação."""
        return json.loads(
            seed.DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8")
        )

    def test_manifest_loads_six_evaluations_with_deterministic_keys(self):
        records = seed.load_evaluation_seed_data()

        self.assertEqual(len(records), 6)
        self.assertEqual(
            len({record.reconciliation_key for record in records}),
            6,
        )
        self.assertTrue(
            all(record.criado_em.tzinfo is timezone.utc for record in records)
        )
        self.assertEqual(
            Counter(record.local_slug for record in records),
            EXPECTED_EVALUATIONS_BY_SLUG,
        )

    def test_manifest_rejects_unapproved_local_reference(self):
        manifest = self.read_manifest()
        manifest["avaliacoes"][0]["dados"]["local_slug"] = "local-inexistente"

        with self.assertRaisesRegex(seed.SeedManifestError, "não aprovado"):
            seed.load_evaluation_seed_data(self.write_manifest(manifest))

    def test_manifest_rejects_duplicate_evaluation_key(self):
        manifest = self.read_manifest()
        manifest["avaliacoes"][1]["dados"] = dict(
            manifest["avaliacoes"][0]["dados"]
        )

        with self.assertRaisesRegex(seed.SeedManifestError, "duplicada"):
            seed.load_evaluation_seed_data(self.write_manifest(manifest))

    def test_full_seed_resolves_local_ids_by_slug(self):
        with patch("scripts.seed.SessionLocal", self.session_factory):
            result = seed.run_seed()

        with self.session_factory() as session:
            rows = session.execute(
                select(Avaliacao, LocalTuristico.slug).join(
                    LocalTuristico,
                    Avaliacao.local_id == LocalTuristico.id,
                )
            ).all()
            locations_count = session.scalar(
                select(func.count()).select_from(LocalTuristico)
            )

        self.assertEqual(result.locations.inserted, 6)
        self.assertEqual(result.evaluations.inserted, 6)
        self.assertEqual(result.evaluations.unchanged, 0)
        self.assertEqual(locations_count, 6)
        self.assertEqual(len(rows), 6)
        self.assertEqual(
            Counter(slug for _evaluation, slug in rows),
            EXPECTED_EVALUATIONS_BY_SLUG,
        )

    def test_second_seed_does_not_duplicate_evaluations(self):
        with patch("scripts.seed.SessionLocal", self.session_factory):
            first = seed.run_seed()
            second = seed.run_seed()

        with self.session_factory() as session:
            count = session.scalar(select(func.count()).select_from(Avaliacao))

        self.assertEqual(first.evaluations.inserted, 6)
        self.assertEqual(second.evaluations.inserted, 0)
        self.assertEqual(second.evaluations.unchanged, 6)
        self.assertEqual(count, 6)


if __name__ == "__main__":
    unittest.main()
