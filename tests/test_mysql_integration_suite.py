"""Testa o núcleo reutilizável da validação integrada MySQL."""

import io
import unittest
from contextlib import redirect_stdout

from scripts import mysql_integration_suite


class MysqlIntegrationSuiteTestCase(unittest.TestCase):
    def test_cases_run_once_in_declared_order_with_stable_results(self):
        executions = []
        cases = (
            mysql_integration_suite.ValidationCase(
                "primeiro", lambda: executions.append("primeiro")
            ),
            mysql_integration_suite.ValidationCase(
                "segundo", lambda: executions.append("segundo")
            ),
        )

        results = mysql_integration_suite.run_validation_cases(cases)

        self.assertEqual(executions, ["primeiro", "segundo"])
        self.assertEqual(
            results,
            [
                {"nome": "primeiro", "status": "ok"},
                {"nome": "segundo", "status": "ok"},
            ],
        )

    def test_case_names_must_be_canonical_and_unique(self):
        validation_case = mysql_integration_suite.ValidationCase
        with self.assertRaisesRegex(ValueError, "não é canônico"):
            validation_case("Nome inválido", lambda: None)

        duplicate_cases = (
            mysql_integration_suite.ValidationCase("duplicado", lambda: None),
            mysql_integration_suite.ValidationCase("duplicado", lambda: None),
        )
        with self.assertRaisesRegex(ValueError, "devem ser únicos"):
            mysql_integration_suite.run_validation_cases(duplicate_cases)

    def test_report_is_formatted_deterministically(self):
        report = {
            "status": "ok",
            "casos": [{"status": "ok", "nome": "ordenacao"}],
        }

        first = mysql_integration_suite.serialize_validation_report(report)
        second = mysql_integration_suite.serialize_validation_report(report)
        output = io.StringIO()
        with redirect_stdout(output):
            mysql_integration_suite.print_validation_report(report)

        self.assertEqual(first, second)
        self.assertEqual(output.getvalue(), first + "\n")
        self.assertLess(first.index('"casos"'), first.index('"status"'))

    def test_report_rejects_sensitive_keys_at_any_depth(self):
        unsafe_reports = (
            {"database_url": "valor"},
            {"configuracao": {"senha": "valor"}},
            {"itens": [{"access_token": "valor"}]},
        )

        for report in unsafe_reports:
            with self.subTest(report=report):
                with self.assertRaisesRegex(
                    ValueError,
                    "potencialmente sensível",
                ):
                    mysql_integration_suite.serialize_validation_report(report)
