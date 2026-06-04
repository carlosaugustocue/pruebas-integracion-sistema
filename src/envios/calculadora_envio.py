"""
Calculadora de envíos de TiendaUV.

Reglas de negocio (tabla de decisión):
  Premium + Total > $500k  → express gratis
  Premium + Total ≤ $500k  → normal gratis
  No premium + Total > $500k → normal gratis
  No premium + Total ≤ $500k → cliente paga
"""


class CalculadoraEnvio:
    UMBRAL_TOTAL = 500_000

    def calcular_envio(self, es_premium: bool, total: float) -> str:
        if total < 0:
            raise ValueError(f"El total no puede ser negativo: {total}")

        if es_premium and total > self.UMBRAL_TOTAL:
            return "express_gratis"
        elif es_premium and total <= self.UMBRAL_TOTAL:
            return "normal_gratis"
        elif not es_premium and total > self.UMBRAL_TOTAL:
            return "normal_gratis"
        else:
            return "cliente_paga"
