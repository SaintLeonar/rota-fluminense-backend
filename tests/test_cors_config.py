import os
import subprocess
import sys
import textwrap
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from services.cors_config import (
    CORS_ALLOWED_ORIGINS_ENV_VAR,
    CorsConfigurationError,
    load_cors_settings,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class CorsConfigurationTestCase(unittest.TestCase):
    def test_normalizes_deduplicates_and_preserves_origin_order(self):
        settings = load_cors_settings(
            {
                CORS_ALLOWED_ORIGINS_ENV_VAR: (
                    " HTTP://LOCALHOST:80, https://Example.COM:443, "
                    "http://localhost:5173, http://localhost:5173 "
                )
            }
        )

        self.assertEqual(
            settings.allowed_origins,
            (
                "http://localhost",
                "https://example.com",
                "http://localhost:5173",
            ),
        )

    def test_settings_are_immutable(self):
        settings = load_cors_settings(
            {CORS_ALLOWED_ORIGINS_ENV_VAR: "http://localhost:5173"}
        )

        with self.assertRaises(FrozenInstanceError):
            settings.allowed_origins = ("https://example.com",)

    def test_missing_empty_and_unsafe_values_are_rejected_safely(self):
        invalid_values = (
            None,
            "",
            "   ",
            "*",
            "null",
            "ftp://example.com",
            "example.com",
            "http://user:password@example.com",
            "http://example.com/path",
            "http://example.com?query=secret",
            "http://example.com#fragment",
            "http://example.com,,https://example.org",
            "http://example.com:0",
            "http://example.com:65536",
            "http://*.example.com",
        )

        for received in invalid_values:
            with self.subTest(received=received):
                environment = {}
                if received is not None:
                    environment[CORS_ALLOWED_ORIGINS_ENV_VAR] = received

                with self.assertRaises(CorsConfigurationError) as caught:
                    load_cors_settings(environment)

                message = str(caught.exception)
                self.assertIn(CORS_ALLOWED_ORIGINS_ENV_VAR, message)
                if received:
                    self.assertNotIn(received, message)

    def run_app_import(self, cors_value):
        environment = os.environ.copy()
        environment["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
        environment["PYTHONUTF8"] = "1"
        environment.pop(CORS_ALLOWED_ORIGINS_ENV_VAR, None)
        if cors_value is not None:
            environment[CORS_ALLOWED_ORIGINS_ENV_VAR] = cors_value

        return subprocess.run(
            [sys.executable, "-c", textwrap.dedent("import app")],
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def test_missing_or_invalid_configuration_prevents_startup(self):
        for received in (None, "segredo-invalido.example"):
            with self.subTest(received=received):
                result = self.run_app_import(received)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(CORS_ALLOWED_ORIGINS_ENV_VAR, result.stderr)
                if received:
                    self.assertNotIn(received, result.stderr)

    def test_valid_configuration_allows_startup(self):
        result = self.run_app_import("http://localhost:5173")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
