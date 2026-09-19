import os
import subprocess
import sys
import textwrap
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from services import open_meteo_config

CACHE_TTL_ENV_VAR = open_meteo_config.CACHE_TTL_ENV_VAR
DEFAULT_CACHE_TTL_SECONDS = open_meteo_config.DEFAULT_CACHE_TTL_SECONDS
DEFAULT_TIMEOUT_SECONDS = open_meteo_config.DEFAULT_TIMEOUT_SECONDS
TIMEOUT_ENV_VAR = open_meteo_config.TIMEOUT_ENV_VAR
OpenMeteoConfigurationError = open_meteo_config.OpenMeteoConfigurationError
load_open_meteo_settings = open_meteo_config.load_open_meteo_settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MISSING = object()


class OpenMeteoConfigurationTestCase(unittest.TestCase):
    def test_missing_values_use_safe_defaults(self):
        settings = load_open_meteo_settings({})

        self.assertEqual(settings.timeout_seconds, DEFAULT_TIMEOUT_SECONDS)
        self.assertEqual(
            settings.cache_ttl_seconds,
            DEFAULT_CACHE_TTL_SECONDS,
        )

    def test_valid_values_are_normalized(self):
        settings = load_open_meteo_settings(
            {
                TIMEOUT_ENV_VAR: " 2.50 ",
                CACHE_TTL_ENV_VAR: " 3600 ",
            }
        )

        self.assertEqual(settings.timeout_seconds, 2.5)
        self.assertEqual(settings.cache_ttl_seconds, 3600)

    def test_inclusive_boundaries_are_accepted(self):
        for timeout in ("0.1", "30.0"):
            with self.subTest(timeout=timeout):
                settings = load_open_meteo_settings({TIMEOUT_ENV_VAR: timeout})
                self.assertEqual(settings.timeout_seconds, float(timeout))

        for ttl in ("1", "86400"):
            with self.subTest(ttl=ttl):
                settings = load_open_meteo_settings({CACHE_TTL_ENV_VAR: ttl})
                self.assertEqual(settings.cache_ttl_seconds, int(ttl))

    def test_settings_are_immutable(self):
        settings = load_open_meteo_settings({})

        with self.assertRaises(FrozenInstanceError):
            settings.timeout_seconds = 10.0

    def test_invalid_timeout_values_are_rejected(self):
        invalid_values = (
            "",
            "   ",
            "true",
            "NaN",
            "Infinity",
            "+1",
            ".5",
            "1e1",
            "1_0",
            "1,5",
            "0",
            "0.09",
            "30.01",
            "valor-invalido",
        )

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(OpenMeteoConfigurationError):
                    load_open_meteo_settings({TIMEOUT_ENV_VAR: value})

    def test_invalid_cache_ttl_values_are_rejected(self):
        invalid_values = (
            "",
            "   ",
            "true",
            "1.0",
            "-1",
            "0",
            "86401",
            "valor-invalido",
        )

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(OpenMeteoConfigurationError):
                    load_open_meteo_settings({CACHE_TTL_ENV_VAR: value})

    def test_error_does_not_expose_received_value(self):
        received_value = "valor-sensivel-de-configuracao"

        with self.assertRaises(OpenMeteoConfigurationError) as context:
            load_open_meteo_settings({TIMEOUT_ENV_VAR: received_value})

        message = str(context.exception)
        self.assertIn(TIMEOUT_ENV_VAR, message)
        self.assertNotIn(received_value, message)


class OpenMeteoStartupTestCase(unittest.TestCase):
    def run_import(
        self,
        timeout=MISSING,
        cache_ttl=MISSING,
        code="import app",
    ):
        environment = os.environ.copy()
        environment["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
        environment["PYTHONUTF8"] = "1"
        environment.pop(TIMEOUT_ENV_VAR, None)
        environment.pop(CACHE_TTL_ENV_VAR, None)

        if timeout is not MISSING:
            environment[TIMEOUT_ENV_VAR] = timeout
        if cache_ttl is not MISSING:
            environment[CACHE_TTL_ENV_VAR] = cache_ttl

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

    def test_app_exposes_default_settings(self):
        result = self.run_import(code="""
            from app import app

            settings = app.config["OPEN_METEO_SETTINGS"]
            assert settings.timeout_seconds == 5.0
            assert settings.cache_ttl_seconds == 1800
            """)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_app_exposes_validated_environment_settings(self):
        result = self.run_import(
            timeout="3.5",
            cache_ttl="600",
            code="""
            from app import app

            settings = app.config["OPEN_METEO_SETTINGS"]
            assert settings.timeout_seconds == 3.5
            assert settings.cache_ttl_seconds == 600
            """,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_timeout_prevents_startup_without_exposing_value(self):
        received_value = "segredo-timeout-invalido"
        result = self.run_import(timeout=received_value)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(TIMEOUT_ENV_VAR, result.stderr)
        self.assertNotIn(received_value, result.stderr)

    def test_invalid_cache_ttl_prevents_startup_without_exposing_value(self):
        received_value = "segredo-ttl-invalido"
        result = self.run_import(cache_ttl=received_value)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(CACHE_TTL_ENV_VAR, result.stderr)
        self.assertNotIn(received_value, result.stderr)


if __name__ == "__main__":
    unittest.main()
