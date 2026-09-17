import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_CONFIG = PROJECT_ROOT / "alembic.ini"
REVISION_ID = "1f9d5faddb44"


def run_alembic(database_url, *arguments):
    """Executa um comando Alembic com ambiente isolado."""
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    environment["PYTHONUTF8"] = "1"

    return subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(ALEMBIC_CONFIG),
            *arguments,
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


class InitialMigrationTestCase(unittest.TestCase):
    def test_revision_is_the_only_base_and_head(self):
        scripts = ScriptDirectory.from_config(Config(ALEMBIC_CONFIG))
        revision = scripts.get_revision(REVISION_ID)

        self.assertEqual(scripts.get_bases(), [REVISION_ID])
        self.assertEqual(scripts.get_heads(), [REVISION_ID])
        self.assertIsNotNone(revision)
        self.assertIsNone(revision.down_revision)

    def test_mysql_upgrade_sql_contains_reviewed_schema(self):
        secret = "segredo_nao_deve_aparecer"
        database_url = "".join(
            (
                "mysql+pymysql://usuario:",
                secret,
                "@localhost:3306/rota_fluminense",
            )
        )
        result = run_alembic(database_url, "upgrade", "head", "--sql")
        output = result.stdout + result.stderr

        self.assertEqual(result.returncode, 0, output)
        self.assertIn("CREATE TABLE locais_turisticos", result.stdout)
        self.assertIn("CREATE TABLE avaliacoes", result.stdout)
        self.assertIn(
            "CREATE UNIQUE INDEX ix_locais_turisticos_slug",
            result.stdout,
        )
        self.assertIn("ix_locais_turisticos_categoria", result.stdout)
        self.assertIn("ix_locais_turisticos_cidade", result.stdout)
        self.assertIn("ix_avaliacoes_local_id", result.stdout)
        self.assertIn("ck_locais_turisticos_latitude_range", result.stdout)
        self.assertIn("ck_locais_turisticos_longitude_range", result.stdout)
        self.assertIn("ck_avaliacoes_autor_not_blank", result.stdout)
        self.assertIn("ck_avaliacoes_comentario_not_blank", result.stdout)
        self.assertIn("ck_avaliacoes_local_id_positive", result.stdout)
        self.assertIn("ck_avaliacoes_nota_range", result.stdout)
        self.assertIn(
            "fk_avaliacoes_local_id_locais_turisticos",
            result.stdout,
        )
        self.assertIn("ON DELETE CASCADE", result.stdout)
        self.assertNotIn(secret, output)

    def test_mysql_downgrade_sql_removes_child_before_parent(self):
        database_url = "mysql+pymysql://usuario:senha@localhost/db"
        result = run_alembic(
            database_url,
            "downgrade",
            f"{REVISION_ID}:base",
            "--sql",
        )
        output = result.stdout + result.stderr

        self.assertEqual(result.returncode, 0, output)
        child_position = result.stdout.index("DROP TABLE avaliacoes")
        parent_position = result.stdout.index("DROP TABLE locais_turisticos")
        self.assertLess(child_position, parent_position)
        self.assertNotIn("DROP INDEX ix_avaliacoes_local_id", result.stdout)

    def test_sqlite_smoke_upgrade_and_downgrade(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "schema.db"
            database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"

            upgrade = run_alembic(database_url, "upgrade", "head")
            self.assertEqual(
                upgrade.returncode,
                0,
                upgrade.stdout + upgrade.stderr,
            )

            engine = create_engine(database_url)
            inspector = inspect(engine)
            self.assertEqual(
                set(inspector.get_table_names()),
                {"alembic_version", "avaliacoes", "locais_turisticos"},
            )

            slug_index = next(
                index
                for index in inspector.get_indexes("locais_turisticos")
                if index["name"] == "ix_locais_turisticos_slug"
            )
            self.assertTrue(slug_index["unique"])

            foreign_key = inspector.get_foreign_keys("avaliacoes")[0]
            self.assertEqual(
                foreign_key["name"],
                "fk_avaliacoes_local_id_locais_turisticos",
            )
            self.assertEqual(foreign_key["options"]["ondelete"], "CASCADE")

            metadata_check = run_alembic(database_url, "check")
            self.assertEqual(
                metadata_check.returncode,
                0,
                metadata_check.stdout + metadata_check.stderr,
            )
            self.assertIn(
                "No new upgrade operations detected",
                metadata_check.stdout,
            )
            downgrade = run_alembic(database_url, "downgrade", "base")
            self.assertEqual(
                downgrade.returncode,
                0,
                downgrade.stdout + downgrade.stderr,
            )
            inspector.clear_cache()
            self.assertNotIn("avaliacoes", inspector.get_table_names())
            self.assertNotIn("locais_turisticos", inspector.get_table_names())
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
