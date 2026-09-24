import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import asdict
from io import StringIO
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:5173")

from scripts import seed  # noqa: E402


class SeedReportTestCase(unittest.TestCase):
    def build_result(self):
        """Cria resultado sintético com todas as operações relatáveis."""
        return seed.SeedResult(
            locations=seed.LocalSeedResult(
                inserted=1,
                updated=2,
                unchanged=3,
            ),
            evaluations=seed.EvaluationSeedResult(
                inserted=4,
                unchanged=5,
            ),
            rejections=seed.load_seed_rejections(),
        )

    def test_rejections_expose_only_safe_fields_and_reasons(self):
        rejections = seed.load_seed_rejections()

        self.assertEqual(len(rejections), 5)
        self.assertEqual(
            sum(rejection.tipo == "local" for rejection in rejections),
            3,
        )
        self.assertEqual(
            sum(rejection.tipo == "avaliacao" for rejection in rejections),
            2,
        )
        for rejection in rejections:
            self.assertTrue(rejection.codigo)
            self.assertTrue(rejection.motivo)
            self.assertEqual(
                set(asdict(rejection)),
                {"fonte", "tipo", "codigo", "motivo"},
            )

    def test_rejection_counts_must_match_manifest_summary(self):
        manifest = json.loads(seed.DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8"))
        manifest["resumo"]["locais_sqlite_rejeitados"] = 2

        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest_path = Path(temporary_directory) / "manifest.json"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(seed.SeedManifestError, "diverge"):
                seed.load_seed_rejections(manifest_path)

    def test_report_consolidates_all_operation_totals(self):
        report = seed.build_seed_report(self.build_result())

        self.assertEqual(
            report["totais"],
            {
                "inseridos": 5,
                "atualizados": 2,
                "ignorados": 8,
                "rejeitados": 5,
            },
        )
        self.assertEqual(
            report["entidades"]["locais"],
            {
                "inseridos": 1,
                "atualizados": 2,
                "ignorados": 3,
                "rejeitados": 3,
            },
        )
        self.assertEqual(
            report["entidades"]["avaliacoes"],
            {
                "inseridos": 4,
                "atualizados": 0,
                "ignorados": 5,
                "rejeitados": 2,
            },
        )

    def test_serialized_report_omits_private_and_database_fields(self):
        serialized = seed.format_seed_report(self.build_result())
        report = json.loads(serialized)

        self.assertEqual(report["resultado"], "concluido")
        self.assertNotIn("id_origem", serialized)
        self.assertNotIn("identificacao", serialized)
        self.assertNotIn("DATABASE_URL", serialized)
        self.assertNotIn("mysql+pymysql", serialized)
        self.assertTrue(all(rejection["motivo"] for rejection in report["rejeicoes"]))

    def test_main_prints_only_the_json_report(self):
        output = StringIO()
        result = self.build_result()

        with patch("scripts.seed.run_seed", return_value=result), redirect_stdout(
            output
        ):
            seed.main()

        self.assertEqual(
            json.loads(output.getvalue()),
            seed.build_seed_report(result),
        )


if __name__ == "__main__":
    unittest.main()
