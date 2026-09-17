import os
import subprocess
import sys
import unittest
from pathlib import Path

from alembic.config import Config

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_CONFIG = PROJECT_ROOT / "alembic.ini"
ALEMBIC_ENV = PROJECT_ROOT / "migrations" / "env.py"


def run_alembic(database_url=None):
    """Executa o Alembic em subprocesso com ambiente controlado."""
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    if database_url is None:
        environment.pop("DATABASE_URL", None)
    else:
        environment["DATABASE_URL"] = database_url

    return subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(ALEMBIC_CONFIG),
            "upgrade",
            "head",
            "--sql",
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


class AlembicConfigurationTestCase(unittest.TestCase):
    def test_ini_has_no_database_url_or_credentials(self):
        config = Config(ALEMBIC_CONFIG)
        contents = ALEMBIC_CONFIG.read_text(encoding="utf-8")

        self.assertIsNone(config.get_main_option("sqlalchemy.url"))
        self.assertNotIn("driver://", contents)
        self.assertNotIn("senha_exemplo", contents)
        self.assertNotIn("usuario_exemplo", contents)

    def test_environment_uses_application_metadata_and_engine(self):
        contents = ALEMBIC_ENV.read_text(encoding="utf-8")

        self.assertIn("from models.avaliacao import Avaliacao", contents)
        self.assertIn(
            "from models.local_turistico import LocalTuristico",
            contents,
        )
        self.assertIn("target_metadata = Base.metadata", contents)
        self.assertIn("url=DATABASE_URL", contents)
        self.assertIn("with engine.connect() as connection", contents)

    def test_offline_migration_uses_database_url_without_exposing_secret(self):
        secret = "segredo_nao_deve_aparecer"
        database_url = "".join(
            (
                "mysql+pymysql://usuario:",
                secret,
                "@localhost:3306/rota_fluminense",
            )
        )
        result = run_alembic(database_url)
        output = result.stdout + result.stderr

        self.assertEqual(result.returncode, 0, output)
        self.assertIn("Context impl MySQLImpl", output)
        self.assertNotIn(secret, output)

    def test_missing_database_url_fails_with_application_message(self):
        result = run_alembic()
        output = result.stdout + result.stderr

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DATABASE_URL é obrigatória", output)


if __name__ == "__main__":
    unittest.main()
