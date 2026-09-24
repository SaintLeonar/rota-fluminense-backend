import os
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ApplicationStartupTestCase(unittest.TestCase):
    def run_code(self, code, database_url):
        """Executa código em subprocesso com banco isolado."""
        environment = os.environ.copy()
        environment["DATABASE_URL"] = database_url
        environment["CORS_ALLOWED_ORIGINS"] = "http://localhost:5173"
        environment["PYTHONUTF8"] = "1"

        return subprocess.run(
            [sys.executable, "-c", textwrap.dedent(code)],
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def test_models_package_does_not_expose_schema_initialization(self):
        result = self.run_code(
            """
            import models

            assert not hasattr(models, "init_db")
            """,
            "sqlite+pysqlite:///:memory:",
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_direct_startup_does_not_create_database_schema(self):
        database_path = PROJECT_ROOT / "startup-schema-test.db"
        database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
        code = """
        import runpy
        from pathlib import Path
        from unittest.mock import patch

        database_path = Path("startup-schema-test.db").resolve()
        with patch("flask_openapi3.OpenAPI.run") as run:
            runpy.run_path("app.py", run_name="__main__")

        run.assert_called_once_with(debug=True)
        assert not database_path.exists()
        """

        try:
            result = self.run_code(code, database_url)
        finally:
            database_path.unlink(missing_ok=True)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
