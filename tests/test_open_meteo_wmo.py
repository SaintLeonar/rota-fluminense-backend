import re
import unittest
from dataclasses import FrozenInstanceError

from services import open_meteo_wmo

EXPECTED_CONDITIONS = {
    0: ("Céu limpo", "ceu_limpo"),
    1: ("Predominantemente limpo", "predominantemente_limpo"),
    2: ("Parcialmente nublado", "parcialmente_nublado"),
    3: ("Encoberto", "encoberto"),
    45: ("Nevoeiro", "nevoeiro"),
    48: ("Nevoeiro com geada", "nevoeiro_com_geada"),
    51: ("Garoa fraca", "garoa_fraca"),
    53: ("Garoa moderada", "garoa_moderada"),
    55: ("Garoa intensa", "garoa_intensa"),
    56: ("Garoa congelante fraca", "garoa_congelante_fraca"),
    57: ("Garoa congelante intensa", "garoa_congelante_intensa"),
    61: ("Chuva fraca", "chuva_fraca"),
    63: ("Chuva moderada", "chuva_moderada"),
    65: ("Chuva forte", "chuva_forte"),
    66: ("Chuva congelante fraca", "chuva_congelante_fraca"),
    67: ("Chuva congelante forte", "chuva_congelante_forte"),
    71: ("Neve fraca", "neve_fraca"),
    73: ("Neve moderada", "neve_moderada"),
    75: ("Neve forte", "neve_forte"),
    77: ("Grãos de neve", "graos_de_neve"),
    80: ("Pancadas de chuva fracas", "pancadas_de_chuva_fracas"),
    81: ("Pancadas de chuva moderadas", "pancadas_de_chuva_moderadas"),
    82: ("Pancadas de chuva fortes", "pancadas_de_chuva_fortes"),
    85: ("Pancadas de neve fracas", "pancadas_de_neve_fracas"),
    86: ("Pancadas de neve fortes", "pancadas_de_neve_fortes"),
    95: ("Tempestade", "tempestade"),
    96: ("Tempestade com granizo fraco", "tempestade_com_granizo_fraco"),
    99: ("Tempestade com granizo forte", "tempestade_com_granizo_forte"),
}


class OpenMeteoWmoTestCase(unittest.TestCase):
    def test_maps_every_published_code_to_the_approved_contract(self):
        self.assertEqual(
            open_meteo_wmo.SUPPORTED_WMO_CODES,
            frozenset(EXPECTED_CONDITIONS),
        )

        for code, (description, icon) in EXPECTED_CONDITIONS.items():
            with self.subTest(code=code):
                condition = open_meteo_wmo.traduzir_codigo_wmo(code)
                self.assertEqual(condition.codigo_meteorologico, code)
                self.assertEqual(condition.descricao, description)
                self.assertEqual(condition.icone, icon)

    def test_unknown_integer_preserves_code_and_uses_stable_fallback(self):
        for code in (-999, -1, 4, 44, 100, 999):
            with self.subTest(code=code):
                condition = open_meteo_wmo.traduzir_codigo_wmo(code)
                self.assertEqual(condition.codigo_meteorologico, code)
                self.assertEqual(
                    condition.descricao,
                    open_meteo_wmo.UNKNOWN_DESCRIPTION,
                )
                self.assertEqual(condition.icone, open_meteo_wmo.UNKNOWN_ICON)

    def test_rejects_values_that_are_not_integers(self):
        for value in (None, True, False, 1.0, "1", [], {}):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    open_meteo_wmo.traduzir_codigo_wmo(value)

    def test_conditions_are_immutable_and_icons_are_semantic_keys(self):
        icon_pattern = re.compile(r"[a-z0-9]+(?:_[a-z0-9]+)*")

        for code in EXPECTED_CONDITIONS:
            with self.subTest(code=code):
                condition = open_meteo_wmo.traduzir_codigo_wmo(code)
                self.assertRegex(condition.icone, icon_pattern)
                self.assertNotIn("http", condition.icone)
                self.assertNotIn(".", condition.icone)

        condition = open_meteo_wmo.traduzir_codigo_wmo(0)
        with self.assertRaises(FrozenInstanceError):
            condition.icone = "alterado"


if __name__ == "__main__":
    unittest.main()
