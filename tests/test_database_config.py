import os
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MISSING = object()


class DatabaseConfigurationTestCase(unittest.TestCase):
    def run_import(self, database_url=MISSING, code="import models.base"):
        environment = os.environ.copy()
        environment["PYTHONUTF8"] = "1"
        environment.pop("DATABASE_URL", None)

        if database_url is not MISSING:
            environment["DATABASE_URL"] = database_url

        return subprocess.run(
            [sys.executable, "-c", textwrap.dedent(code)],
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )

    def test_database_url_ausente_falha_com_mensagem_clara(self):
        result = self.run_import()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DATABASE_URL é obrigatória", result.stderr)
        self.assertNotIn("sqlite:///database.db", result.stderr)

    def test_database_url_vazia_falha_com_mensagem_clara(self):
        result = self.run_import("   ")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DATABASE_URL é obrigatória", result.stderr)

    def test_database_url_invalida_nao_expoe_o_valor(self):
        invalid_url = "valor secreto que nao e uma url"
        result = self.run_import(invalid_url)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("deve conter uma URL SQLAlchemy válida", result.stderr)
        self.assertNotIn(invalid_url, result.stderr)

    def test_database_url_sem_banco_falha_antes_de_criar_engine(self):
        result = self.run_import("mysql+pymysql://usuario:senha@mysql")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("deve conter uma URL SQLAlchemy válida", result.stderr)
        self.assertNotIn("senha", result.stderr)

    def test_url_explicita_cria_engine_e_fabrica_de_sessoes(self):
        result = self.run_import(
            "sqlite:///:memory:",
            """
            import models.base as base

            assert base.engine.url.database == ":memory:"
            assert base.engine.pool._pre_ping is True
            assert base.SessionLocal.kw["bind"] is base.engine
            assert base.SessionLocal.kw["autoflush"] is False
            assert base.SessionLocal.kw["autocommit"] is False
            """,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_url_mysql_configura_engine_sem_opcoes_especificas_de_sqlite(self):
        result = self.run_import(
            "mysql+pymysql://usuario:senha_teste@mysql/rota_fluminense",
            """
            from unittest.mock import patch

            with patch("sqlalchemy.create_engine") as create_engine:
                import models.base

            database_url = create_engine.call_args.args[0]
            options = create_engine.call_args.kwargs

            assert database_url.get_backend_name() == "mysql"
            assert database_url.get_driver_name() == "pymysql"
            assert database_url.host == "mysql"
            assert database_url.database == "rota_fluminense"
            assert options == {"pool_pre_ping": True}
            """,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_driver_inexistente_falha_sem_expor_credencial(self):
        result = self.run_import(
            "mysql+driver_inexistente://usuario:senha_teste@mysql/banco"
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Não foi possível inicializar", result.stderr)
        self.assertNotIn("senha_teste", result.stderr)


if __name__ == "__main__":
    unittest.main()
