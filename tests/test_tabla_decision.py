"""
Pruebas basadas en tabla de decision para el sistema de envios de TiendaUV.

Que es una tabla de decision y cuando usarla
---------------------------------------------
Una tabla de decision es una tecnica de diseno de pruebas para sistemas que
tienen MULTIPLES condiciones que se combinan para producir diferentes acciones.
Es especialmente util cuando:

  - Hay 2 o mas condiciones booleanas (si/no) o categoricas.
  - Cada combinacion de condiciones lleva a una accion diferente.
  - El numero de combinaciones es manejable (2 condiciones = 4 combinaciones,
    3 condiciones = 8 combinaciones, etc.).

El sistema de envios tiene dos condiciones:
  C1: ¿El cliente es premium?   (si o no)
  C2: ¿El total es mayor a $500.000?  (si o no)

Con 2 condiciones binarias hay exactamente 4 combinaciones posibles.

Como se construye la tabla paso a paso
----------------------------------------

Paso 1: Listar las condiciones
  C1: ¿Es premium?
  C2: Total > $500k?

Paso 2: Listar todas las combinaciones (2^n donde n = numero de condiciones)
  Con 2 condiciones: 2^2 = 4 combinaciones.

Paso 3: Para cada combinacion, determinar la accion del sistema
  Resultado de aplicar las reglas de negocio:

  | C1: Premium | C2: Total>$500k | Accion                |
  |:-----------:|:---------------:|:---------------------:|
  | SÍ          | SÍ              | express_gratis (Col1) |
  | SÍ          | NO              | normal_gratis  (Col2) |
  | NO          | SÍ              | normal_gratis  (Col3) |
  | NO          | NO              | cliente_paga   (Col4) |

Paso 4: Cada columna se convierte en exactamente un test.
  4 combinaciones → 4 tests base. Luego se agregan tests de valores limite
  alrededor del umbral $500.000.

Por que exactamente un test por columna
-----------------------------------------
Si se testea mas de una columna por test, cuando falle no se sabe cual
combinacion fallo. Si se agrupa por accion ("todos los que dan normal_gratis"),
se pierde la trazabilidad hacia la regla de negocio especifica que genero el caso.
La correspondencia 1 a 1 entre columna y test hace el diagnostico inmediato.

Tabla de decision (representacion en el formato del docstring original):

+--------------------+---------+---------+---------+---------+
| C1: Es premium?    |   SI    |   SI    |   NO    |   NO    |
| C2: Total > $500k? |   SI    |   NO    |   SI    |   NO    |
+--------------------+---------+---------+---------+---------+
| Envio express gratis|   v    |         |         |         |
| Envio normal gratis |        |   v     |   v     |         |
| Cliente paga envio  |        |         |         |   v     |
+--------------------+---------+---------+---------+---------+
"""

import pytest

from src.envios.calculadora_envio import CalculadoraEnvio


class TestTablaDecisionEnvios:
    def setup_method(self):
        self.calc = CalculadoraEnvio()

    def test_columna_1_premium_y_total_alto(self):
        """Col 1: Premium=SI + Total > $500k → express gratis."""
        resultado = self.calc.calcular_envio(es_premium=True, total=600_000)
        assert resultado == "express_gratis"

    def test_columna_2_premium_y_total_bajo(self):
        """Col 2: Premium=SI + Total <= $500k → normal gratis."""
        resultado = self.calc.calcular_envio(es_premium=True, total=200_000)
        assert resultado == "normal_gratis"

    def test_columna_3_no_premium_y_total_alto(self):
        """Col 3: Premium=NO + Total > $500k → normal gratis."""
        resultado = self.calc.calcular_envio(es_premium=False, total=700_000)
        assert resultado == "normal_gratis"

    def test_columna_4_no_premium_y_total_bajo(self):
        """Col 4: Premium=NO + Total <= $500k → cliente paga."""
        resultado = self.calc.calcular_envio(es_premium=False, total=100_000)
        assert resultado == "cliente_paga"

    # ── Casos de valores limite en el umbral ────────────────────────
    # La tabla de decision identifica las reglas, pero no especifica
    # el comportamiento exactamente EN el limite. El analisis de valores
    # limite complementa la tabla para verificar ese caso.

    def test_total_exactamente_en_umbral_premium(self):
        """Valor limite: $500.000 exactos + premium → normal gratis (no supera el umbral)."""
        # La regla es "total > 500000", entonces 500000 exacto NO supera el umbral
        resultado = self.calc.calcular_envio(es_premium=True, total=500_000)
        assert resultado == "normal_gratis"

    def test_total_exactamente_en_umbral_no_premium(self):
        """Valor limite: $500.000 exactos + no premium → cliente paga."""
        resultado = self.calc.calcular_envio(es_premium=False, total=500_000)
        assert resultado == "cliente_paga"

    def test_total_negativo_lanza_error(self):
        """Guardia: total negativo es un dato invalido que no cabe en la tabla."""
        with pytest.raises(ValueError, match="negativo"):
            self.calc.calcular_envio(es_premium=False, total=-1)


# Version compacta con parametrize (cubre las 4 columnas + bordes):
# Cada tupla es (es_premium, total, resultado_esperado) y corresponde
# a una columna de la tabla o a un caso de limite.
@pytest.mark.parametrize(
    "es_premium, total, resultado_esperado",
    [
        (True, 600_000, "express_gratis"),  # Col 1: premium + alto
        (True, 200_000, "normal_gratis"),  # Col 2: premium + bajo
        (False, 700_000, "normal_gratis"),  # Col 3: no premium + alto
        (False, 100_000, "cliente_paga"),  # Col 4: no premium + bajo
        (True, 500_000, "normal_gratis"),  # Limite exacto + premium
        (False, 500_000, "cliente_paga"),  # Limite exacto + no premium
        (True, 500_001, "express_gratis"),  # Un peso sobre el umbral + premium
        (False, 500_001, "normal_gratis"),  # Un peso sobre el umbral + no premium
    ],
)
def test_tabla_decision_parametrizado(es_premium, total, resultado_esperado):
    calc = CalculadoraEnvio()
    assert calc.calcular_envio(es_premium, total) == resultado_esperado
