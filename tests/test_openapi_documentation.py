import os
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}

EXPECTED_OPERATIONS = {
    ("GET", "/locais"): ("listar_locais", "Locais"),
    ("POST", "/locais"): ("criar_local", "Locais"),
    ("GET", "/locais/{slug}"): ("consultar_local", "Locais"),
    (
        "GET",
        "/locais/{slug}/clima",
    ): ("consultar_clima_local", "Locais"),
    ("PUT", "/locais/{slug}"): ("substituir_local", "Locais"),
    ("DELETE", "/locais/{slug}"): ("excluir_local", "Locais"),
    (
        "GET",
        "/locais/{slug}/avaliacoes",
    ): ("listar_avaliacoes", "Avaliações"),
    (
        "POST",
        "/locais/{slug}/avaliacoes",
    ): ("criar_avaliacao", "Avaliações"),
    (
        "PATCH",
        "/avaliacoes/{avaliacao_id}",
    ): ("atualizar_avaliacao", "Avaliações"),
    (
        "DELETE",
        "/avaliacoes/{avaliacao_id}",
    ): ("excluir_avaliacao", "Avaliações"),
}

EXPECTED_RESPONSES = {
    ("GET", "/locais"): {"200", "400", "500", "503"},
    ("POST", "/locais"): {"201", "400", "409", "500", "503"},
    ("GET", "/locais/{slug}"): {"200", "400", "404", "500", "503"},
    ("GET", "/locais/{slug}/clima"): {
        "200",
        "400",
        "404",
        "500",
        "503",
    },
    ("PUT", "/locais/{slug}"): {"200", "400", "404", "500", "503"},
    ("DELETE", "/locais/{slug}"): {"204", "400", "404", "500", "503"},
    ("GET", "/locais/{slug}/avaliacoes"): {
        "200",
        "400",
        "404",
        "500",
        "503",
    },
    ("POST", "/locais/{slug}/avaliacoes"): {
        "201",
        "400",
        "404",
        "500",
        "503",
    },
    ("PATCH", "/avaliacoes/{avaliacao_id}"): {
        "200",
        "400",
        "404",
        "500",
        "503",
    },
    ("DELETE", "/avaliacoes/{avaliacao_id}"): {
        "204",
        "400",
        "404",
        "500",
        "503",
    },
}

EXPECTED_SUCCESS_SCHEMAS = {
    ("GET", "/locais"): ("200", "LocalListSchema"),
    ("POST", "/locais"): ("201", "LocalSchema"),
    ("GET", "/locais/{slug}"): ("200", "LocalDetalhadoSchema"),
    ("GET", "/locais/{slug}/clima"): ("200", "ClimaResponseSchema"),
    ("PUT", "/locais/{slug}"): ("200", "LocalSchema"),
    ("GET", "/locais/{slug}/avaliacoes"): ("200", "AvaliacaoListSchema"),
    ("POST", "/locais/{slug}/avaliacoes"): ("201", "AvaliacaoSchema"),
    ("PATCH", "/avaliacoes/{avaliacao_id}"): ("200", "AvaliacaoSchema"),
}

EXPECTED_REQUEST_SCHEMAS = {
    ("POST", "/locais"): "LocalInputSchema",
    ("PUT", "/locais/{slug}"): "LocalUpdateSchema",
    ("POST", "/locais/{slug}/avaliacoes"): "AvaliacaoInputSchema",
    ("PATCH", "/avaliacoes/{avaliacao_id}"): "AvaliacaoUpdateSchema",
}

DOCUMENTED_SCHEMAS = {
    "LocalInputSchema",
    "LocalUpdateSchema",
    "LocalSchema",
    "LocalDetalhadoSchema",
    "PaginacaoSchema",
    "LocalListSchema",
    "AvaliacaoInputSchema",
    "AvaliacaoUpdateSchema",
    "AvaliacaoSchema",
    "AvaliacaoListSchema",
    "ErrorSchema",
    "ClimaLocalSchema",
    "ClimaAtualSchema",
    "ClimaPrevisaoDiariaSchema",
    "ClimaCacheSchema",
    "ClimaResponseSchema",
}

ERROR_EXAMPLES = {
    "requisicaoInvalida",
    "recursoNaoEncontrado",
    "slugJaExistente",
    "bancoIndisponivel",
    "erroInterno",
}

CLIMATE_SUCCESS_EXAMPLES = {"provedor", "cacheValido"}
CLIMATE_SERVICE_ERROR_EXAMPLES = {
    "bancoIndisponivel",
    "coordenadasIndisponiveis",
    "climaIndisponivel",
}
CLIMATE_OPERATION = ("GET", "/locais/{slug}/clima")


def _schema_name(container):
    reference = container["content"]["application/json"]["schema"]["$ref"]
    return reference.rsplit("/", 1)[-1]


class OpenAPIDocumentationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app import app

        response = app.test_client().get("/openapi/openapi.json")
        cls.response = response
        cls.specification = response.get_json()
        cls.operations = {
            (method.upper(), path): operation
            for path, path_item in cls.specification["paths"].items()
            if path != "/"
            for method, operation in path_item.items()
            if method in HTTP_METHODS
        }

    def test_openapi_endpoint_and_api_metadata_are_documented(self):
        self.assertEqual(self.response.status_code, 200)
        self.assertEqual(self.response.content_type, "application/json")

        info = self.specification["info"]
        self.assertEqual(info["title"], "Rota Fluminense API")
        self.assertEqual(info["version"], "1.0.0")
        self.assertTrue(info["summary"])
        self.assertIn("não possuem autenticação", info["description"])

    def test_canonical_operations_have_stable_human_readable_metadata(self):
        self.assertEqual(set(self.operations), set(EXPECTED_OPERATIONS))

        operation_ids = []
        for key, (operation_id, tag) in EXPECTED_OPERATIONS.items():
            with self.subTest(operation=key):
                operation = self.operations[key]
                self.assertEqual(operation["operationId"], operation_id)
                self.assertEqual(operation["tags"], [tag])
                self.assertTrue(operation["summary"])
                self.assertTrue(operation["description"])
                operation_ids.append(operation["operationId"])

        self.assertEqual(len(operation_ids), len(set(operation_ids)))

    def test_reusable_schemas_have_descriptions_and_examples(self):
        schemas = self.specification["components"]["schemas"]
        self.assertTrue(DOCUMENTED_SCHEMAS.issubset(schemas))

        for name in DOCUMENTED_SCHEMAS:
            with self.subTest(schema=name):
                schema = schemas[name]
                self.assertIn("example", schema)
                self.assertTrue(schema["example"])
                for field in schema.get("properties", {}).values():
                    self.assertTrue(field.get("description"))

    def test_parameters_and_request_bodies_reference_documented_contracts(
        self,
    ):
        query_parameters = self.operations[("GET", "/locais")]["parameters"]
        self.assertEqual(
            {parameter["name"] for parameter in query_parameters},
            {
                "cidade",
                "categoria",
                "destaque",
                "pagina",
                "por_pagina",
                "ordenar_por",
            },
        )

        for operation in self.operations.values():
            for parameter in operation.get("parameters", []):
                with self.subTest(parameter=parameter["name"]):
                    self.assertTrue(parameter["description"])
                    self.assertIn("example", parameter)

        ordering = next(
            parameter
            for parameter in query_parameters
            if parameter["name"] == "ordenar_por"
        )
        self.assertEqual(ordering["schema"]["default"], "nome_asc")
        self.assertEqual(len(ordering["schema"]["enum"]), 5)

        for key, expected_schema in EXPECTED_REQUEST_SCHEMAS.items():
            with self.subTest(request=key):
                request_body = self.operations[key]["requestBody"]
                self.assertTrue(request_body["required"])
                self.assertEqual(_schema_name(request_body), expected_schema)

    def test_success_and_error_responses_are_complete_and_exemplified(self):
        for key, expected_statuses in EXPECTED_RESPONSES.items():
            with self.subTest(operation=key):
                responses = self.operations[key]["responses"]
                self.assertEqual(set(responses), expected_statuses)

                for status, response in responses.items():
                    if status.startswith(("4", "5")):
                        self.assertEqual(_schema_name(response), "ErrorSchema")
                        media = response["content"]["application/json"]
                        expected_examples = ERROR_EXAMPLES
                        if key == CLIMATE_OPERATION and status == "503":
                            expected_examples = CLIMATE_SERVICE_ERROR_EXAMPLES
                        self.assertEqual(
                            set(media["examples"]),
                            expected_examples,
                        )

        for key, (status, expected_schema) in EXPECTED_SUCCESS_SCHEMAS.items():
            with self.subTest(success=key):
                response = self.operations[key]["responses"][status]
                self.assertEqual(_schema_name(response), expected_schema)
                media = response["content"]["application/json"]
                if key == CLIMATE_OPERATION:
                    self.assertEqual(
                        set(media["examples"]),
                        CLIMATE_SUCCESS_EXAMPLES,
                    )
                    self.assertNotIn("example", media)
                else:
                    self.assertTrue(media["example"])

        for key in (
            ("DELETE", "/locais/{slug}"),
            ("DELETE", "/avaliacoes/{avaliacao_id}"),
        ):
            self.assertNotIn(
                "content", self.operations[key]["responses"]["204"]
            )

    def test_climate_examples_are_reusable_valid_and_semantic(self):
        from schemas import clima_schema
        from schemas.error import ErrorSchema

        responses = self.operations[CLIMATE_OPERATION]["responses"]
        success_examples = responses["200"]["content"]["application/json"][
            "examples"
        ]

        for name, example in success_examples.items():
            with self.subTest(success_example=name):
                self.assertTrue(example["summary"])
                self.assertTrue(example["description"])
                clima_schema.ClimaResponseSchema.model_validate(
                    example["value"]
                )

        provider = success_examples["provedor"]["value"]
        cached = success_examples["cacheValido"]["value"]
        self.assertFalse(provider["cache"]["utilizado"])
        self.assertTrue(cached["cache"]["utilizado"])
        self.assertEqual(provider["atual"], cached["atual"])
        self.assertEqual(provider["previsao"], cached["previsao"])
        self.assertEqual(
            provider["atualizado_em"],
            cached["atualizado_em"],
        )
        self.assertEqual(
            provider["cache"]["expira_em"],
            cached["cache"]["expira_em"],
        )

        error_examples = responses["503"]["content"]["application/json"][
            "examples"
        ]
        expected_codes = {
            "bancoIndisponivel": "banco_indisponivel",
            "coordenadasIndisponiveis": ("coordenadas_indisponiveis"),
            "climaIndisponivel": "clima_indisponivel",
        }
        for name, code in expected_codes.items():
            with self.subTest(error_example=name):
                example = error_examples[name]
                self.assertTrue(example["summary"])
                ErrorSchema.model_validate(example["value"])
                error = example["value"]["erro"]
                self.assertEqual(error["codigo"], code)
                self.assertEqual(error["detalhes"], [])
                self.assertNotIn("cache", example["value"])

        coordinates = error_examples["coordenadasIndisponiveis"]
        self.assertEqual(
            coordinates["value"]["erro"]["mensagem"],
            (
                "As coordenadas deste local não estão disponíveis para "
                "consulta meteorológica."
            ),
        )


if __name__ == "__main__":
    unittest.main()
