"""
Pruebas basadas en tabla de decisión para el sistema de envíos de TiendaUV.
Técnica: cada columna de la tabla = un caso de prueba.

Tabla de decisión:
┌────────────────────┬─────────┬─────────┬─────────┬─────────┐
│ C1: ¿Es premium?   │   SÍ    │   SÍ    │   NO    │   NO    │
│ C2: Total > $500k? │   SÍ    │   NO    │   SÍ    │   NO    │
├────────────────────┼─────────┼─────────┼─────────┼─────────┤
│ Envío express gratis│   ✓    │         │         │         │
│ Envío normal gratis │        │   ✓     │   ✓     │         │
│ Cliente paga envío  │        │         │         │   ✓     │
└────────────────────┴─────────┴─────────┴─────────┴─────────┘
"""

import pytest

from src.envios.calculadora_envio import CalculadoraEnvio


class TestTablaDecisionEnvios:
    def setup_method(self):
        self.calc = CalculadoraEnvio()

    def test_columna_1_premium_y_total_alto(self):
        """Col 1: Premium=SÍ + Total > $500k → express gratis."""
        resultado = self.calc.calcular_envio(es_premium=True, total=600_000)
        assert resultado == "express_gratis"

    def test_columna_2_premium_y_total_bajo(self):
        """Col 2: Premium=SÍ + Total ≤ $500k → normal gratis."""
        resultado = self.calc.calcular_envio(es_premium=True, total=200_000)
        assert resultado == "normal_gratis"

    def test_columna_3_no_premium_y_total_alto(self):
        """Col 3: Premium=NO + Total > $500k → normal gratis."""
        resultado = self.calc.calcular_envio(es_premium=False, total=700_000)
        assert resultado == "normal_gratis"

    def test_columna_4_no_premium_y_total_bajo(self):
        """Col 4: Premium=NO + Total ≤ $500k → cliente paga."""
        resultado = self.calc.calcular_envio(es_premium=False, total=100_000)
        assert resultado == "cliente_paga"

    # ── Casos de valores límite en el umbral ────────────────────────

    def test_total_exactamente_en_umbral_premium(self):
        """Valor límite: $500.000 exactos + premium → normal gratis (no supera el umbral)."""
        resultado = self.calc.calcular_envio(es_premium=True, total=500_000)
        assert resultado == "normal_gratis"

    def test_total_exactamente_en_umbral_no_premium(self):
        """Valor límite: $500.000 exactos + no premium → cliente paga."""
        resultado = self.calc.calcular_envio(es_premium=False, total=500_000)
        assert resultado == "cliente_paga"

    def test_total_negativo_lanza_error(self):
        """Guardia: total negativo es un dato inválido."""
        with pytest.raises(ValueError, match="negativo"):
            self.calc.calcular_envio(es_premium=False, total=-1)


# Versión compacta con parametrize (cubre las 4 columnas + bordes):
@pytest.mark.parametrize(
    "es_premium, total, resultado_esperado",
    [
        (True, 600_000, "express_gratis"),  # Col 1
        (True, 200_000, "normal_gratis"),  # Col 2
        (False, 700_000, "normal_gratis"),  # Col 3
        (False, 100_000, "cliente_paga"),  # Col 4
        (True, 500_000, "normal_gratis"),  # Límite exacto + premium
        (False, 500_000, "cliente_paga"),  # Límite exacto + no premium
        (True, 500_001, "express_gratis"),  # Un peso sobre el umbral + premium
        (False, 500_001, "normal_gratis"),  # Un peso sobre el umbral + no premium
    ],
)
def test_tabla_decision_parametrizado(es_premium, total, resultado_esperado):
    calc = CalculadoraEnvio()
    assert calc.calcular_envio(es_premium, total) == resultado_esperado
