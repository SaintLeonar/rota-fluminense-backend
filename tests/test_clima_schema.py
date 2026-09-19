import math
import unittest
from copy import deepcopy

from pydantic import ValidationError

from schemas import clima_schema, openapi_examples


def climate_payload():
    return deepcopy(openapi_examples.CLIMATE_RESPONSE_EXAMPLE)


class ClimaSchemaTestCase(unittest.TestCase):
    def assert_invalid(self, payload):
        with self.assertRaises(ValidationError):
            clima_schema.ClimaResponseSchema.model_validate(payload)

    def test_complete_response_exposes_only_the_approved_contract(self):
        response = clima_schema.ClimaResponseSchema.model_validate(
            climate_payload()
        )

        self.assertEqual(
            set(response.model_dump()),
            {
                "local",
                "timezone",
                "atual",
                "previsao",
                "atualizado_em",
                "cache",
            },
        )
        self.assertEqual(set(response.local.model_dump()), {"slug", "nome"})
        self.assertEqual(len(response.previsao), 3)
        self.assertEqual(response.timezone, "America/Sao_Paulo")
        self.assertEqual(
            response.model_dump(mode="json"),
            openapi_examples.CLIMATE_RESPONSE_EXAMPLE,
        )

    def test_every_climate_schema_rejects_extra_fields(self):
        cases = (
            (
                clima_schema.ClimaLocalSchema,
                openapi_examples.CLIMATE_LOCAL_EXAMPLE,
            ),
            (
                clima_schema.ClimaAtualSchema,
                openapi_examples.CLIMATE_CURRENT_EXAMPLE,
            ),
            (
                clima_schema.ClimaPrevisaoDiariaSchema,
                openapi_examples.CLIMATE_DAILY_EXAMPLES[0],
            ),
            (
                clima_schema.ClimaCacheSchema,
                openapi_examples.CLIMATE_CACHE_EXAMPLE,
            ),
            (
                clima_schema.ClimaResponseSchema,
                openapi_examples.CLIMATE_RESPONSE_EXAMPLE,
            ),
        )

        for model, example in cases:
            with self.subTest(model=model.__name__):
                payload = deepcopy(example)
                payload["campo_extra"] = "não permitido"
                with self.assertRaises(ValidationError):
                    model.model_validate(payload)

    def test_forecast_requires_exactly_three_unique_increasing_dates(self):
        for forecast in (
            climate_payload()["previsao"][:2],
            climate_payload()["previsao"]
            + [deepcopy(climate_payload()["previsao"][-1])],
            list(reversed(climate_payload()["previsao"])),
        ):
            with self.subTest(size=len(forecast)):
                payload = climate_payload()
                payload["previsao"] = forecast
                self.assert_invalid(payload)

        payload = climate_payload()
        payload["previsao"][1]["data"] = payload["previsao"][0]["data"]
        self.assert_invalid(payload)

    def test_timezone_and_cache_instants_are_strictly_coherent(self):
        mutations = (
            ("timezone", "UTC"),
            ("observado_em", "2026-09-09T17:15:00"),
            ("observado_em", "2026-09-09T20:15:00Z"),
            ("atualizado_em", "2026-09-09T17:16:00-03:00"),
            ("expira_em", "2026-09-09T20:46:00"),
            ("expira_em", "2026-09-09T20:16:00Z"),
        )

        for field, value in mutations:
            with self.subTest(field=field, value=value):
                payload = climate_payload()
                if field == "observado_em":
                    payload["atual"][field] = value
                elif field == "expira_em":
                    payload["cache"][field] = value
                else:
                    payload[field] = value
                self.assert_invalid(payload)

    def test_numbers_reject_coercion_non_finite_and_invalid_ranges(self):
        mutations = (
            ("temperatura_c", "24.3"),
            ("sensacao_termica_c", True),
            ("precipitacao_mm", -0.1),
            ("velocidade_vento_kmh", math.inf),
            ("codigo_meteorologico", 1.0),
        )
        for field, value in mutations:
            with self.subTest(field=field, value=value):
                payload = climate_payload()
                payload["atual"][field] = value
                self.assert_invalid(payload)

        for value in (-0.1, 100.1, math.nan, "10"):
            with self.subTest(probability=value):
                payload = climate_payload()
                payload["previsao"][0][
                    "probabilidade_precipitacao_max_pct"
                ] = value
                self.assert_invalid(payload)

        for value in (0, 1, "false"):
            with self.subTest(cache_used=value):
                payload = climate_payload()
                payload["cache"]["utilizado"] = value
                self.assert_invalid(payload)

    def test_semantic_condition_accepts_unknown_integer_but_rejects_bad_icon(
        self,
    ):
        payload = climate_payload()
        payload["atual"].update(
            codigo_meteorologico=1234,
            descricao="Condição meteorológica desconhecida",
            icone="condicao_desconhecida",
        )
        response = clima_schema.ClimaResponseSchema.model_validate(payload)
        self.assertEqual(response.atual.codigo_meteorologico, 1234)

        for icon in ("Chuva Fraca", "chuva-fraca", "chuva.png", ""):
            with self.subTest(icon=icon):
                invalid = climate_payload()
                invalid["atual"]["icone"] = icon
                self.assert_invalid(invalid)

    def test_generated_schema_has_examples_descriptions_and_closed_objects(
        self,
    ):
        schema = clima_schema.ClimaResponseSchema.model_json_schema()

        self.assertEqual(
            schema["example"], openapi_examples.CLIMATE_RESPONSE_EXAMPLE
        )
        self.assertIs(schema["additionalProperties"], False)
        self.assertEqual(set(schema["required"]), set(schema["properties"]))
        self.assertEqual(schema["properties"]["previsao"]["minItems"], 3)
        self.assertEqual(schema["properties"]["previsao"]["maxItems"], 3)
        for field in schema["properties"].values():
            self.assertTrue(field["description"])

        expected_definitions = {
            "ClimaLocalSchema",
            "ClimaAtualSchema",
            "ClimaPrevisaoDiariaSchema",
            "ClimaCacheSchema",
        }
        self.assertEqual(set(schema["$defs"]), expected_definitions)
        for definition in schema["$defs"].values():
            self.assertIs(definition["additionalProperties"], False)
            self.assertTrue(definition["example"])
            self.assertEqual(
                set(definition["required"]),
                set(definition["properties"]),
            )
            for field in definition["properties"].values():
                self.assertTrue(field["description"])


if __name__ == "__main__":
    unittest.main()
