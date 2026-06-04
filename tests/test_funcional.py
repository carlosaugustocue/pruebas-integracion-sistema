"""
Pruebas funcionales del carrito de TiendaUV.
Aplica las técnicas sistemáticas del material de la Semana 5:
  - Partición de Equivalencia
  - Análisis de Valores Límite
  - Transición de Estados
"""

import pytest

from src.carrito.carrito import Carrito

# ─────────────────────────────────────────────────────────────────────────────
# SECCIÓN 1 — Partición de Equivalencia: campo "cantidad"
#
# Particiones identificadas (rango válido 1–99):
#   P1 — Inválida baja : cantidad ≤ 0  → ValueError
#   P2 — Válida        : 1 ≤ cantidad ≤ 99 → OK
#   P3 — Inválida alta : cantidad ≥ 100 → ValueError
# ─────────────────────────────────────────────────────────────────────────────


class TestParticionEquivalenciaCantidad:
    """Un representativo por partición es suficiente para detectar el defecto."""

    def test_cantidad_negativa_rechazada(self):
        """P1 — representativo: -3 (partición inválida baja)."""
        carrito = Carrito()
        with pytest.raises(ValueError):
            carrito.agregar_producto("Laptop", 2_500_000, -3)

    def test_cantidad_cero_rechazada(self):
        """P1 — representativo: 0 (borde inferior de la partición inválida baja)."""
        carrito = Carrito()
        with pytest.raises(ValueError):
            carrito.agregar_producto("Laptop", 2_500_000, 0)

    def test_cantidad_valida_aceptada(self):
        """P2 — representativo: 50 (centro de la partición válida)."""
        carrito = Carrito()
        carrito.agregar_producto("Laptop", 2_500_000, 50)
        assert carrito.cantidad_productos() == 1

    def test_cantidad_sobre_maximo_rechazada(self):
        """P3 — representativo: 500 (partición inválida alta)."""
        carrito = Carrito()
        with pytest.raises(ValueError):
            carrito.agregar_producto("Laptop", 2_500_000, 500)


# Versión compacta con parametrize (cubre las 3 particiones):
@pytest.mark.parametrize(
    "cantidad, es_valida",
    [
        (-3, False),  # P1 inválida baja (negativo)
        (0, False),  # P1 inválida baja (cero)
        (1, True),  # P2 válida (mínimo)
        (50, True),  # P2 válida (centro)
        (99, True),  # P2 válida (máximo)
        (100, False),  # P3 inválida alta (justo fuera)
        (500, False),  # P3 inválida alta (extremo)
    ],
)
def test_particion_cantidad_parametrizado(cantidad: int, es_valida: bool):
    carrito = Carrito()
    if es_valida:
        carrito.agregar_producto("Laptop", 2_500_000, cantidad)
        assert carrito.cantidad_productos() == 1
    else:
        with pytest.raises((ValueError, Exception)):
            carrito.agregar_producto("Laptop", 2_500_000, cantidad)


# ─────────────────────────────────────────────────────────────────────────────
# SECCIÓN 2 — Análisis de Valores Límite: campo "porcentaje de descuento"
#
# Rango válido: 0 % a 100 %
# Los 6 valores críticos: -0.1, 0, 0.1, 99.9, 100, 100.1
# ─────────────────────────────────────────────────────────────────────────────


class TestValoresLimiteDescuento:
    """
    Límite inferior: 0 %
    Límite superior: 100 %

    Valores a probar: -0.1 | 0 | 0.1 | 99.9 | 100 | 100.1
    """

    def setup_method(self):
        self.carrito = Carrito()
        self.carrito.agregar_producto("Laptop", 1_000_000, 1)

    # ── Límite inferior ──────────────────────────────────────────────

    def test_descuento_negativo_0_1_falla(self):
        """Límite inferior − 0.1: justo fuera → DEBE FALLAR."""
        with pytest.raises(ValueError):
            self.carrito.aplicar_descuento("porcentaje", -0.1)

    def test_descuento_exactamente_0_pasa(self):
        """Límite inferior exacto: 0 % válido → sin descuento."""
        self.carrito.aplicar_descuento("porcentaje", 0)
        assert self.carrito.calcular_total() == 1_000_000

    def test_descuento_0_1_pasa(self):
        """Límite inferior + 0.1: justo dentro → PASA."""
        self.carrito.aplicar_descuento("porcentaje", 0.1)
        assert self.carrito.calcular_total() == pytest.approx(999_000)

    # ── Límite superior ──────────────────────────────────────────────

    def test_descuento_99_9_pasa(self):
        """Límite superior − 0.1: justo dentro → PASA."""
        self.carrito.aplicar_descuento("porcentaje", 99.9)
        assert self.carrito.calcular_total() == pytest.approx(1_000)

    def test_descuento_exactamente_100_pasa(self):
        """Límite superior exacto: 100 % válido → total cero."""
        self.carrito.aplicar_descuento("porcentaje", 100)
        assert self.carrito.calcular_total() == 0

    def test_descuento_100_1_falla(self):
        """Límite superior + 0.1: justo fuera → DEBE FALLAR."""
        with pytest.raises(ValueError):
            self.carrito.aplicar_descuento("porcentaje", 100.1)


# Versión compacta con parametrize:
@pytest.mark.parametrize(
    "descuento, debe_pasar, total_esperado",
    [
        (-0.1, False, None),
        (0, True, 1_000_000),
        (0.1, True, 999_000),
        (99.9, True, 1_000),
        (100, True, 0),
        (100.1, False, None),
    ],
)
def test_valores_limite_descuento_parametrizado(descuento, debe_pasar, total_esperado):
    carrito = Carrito()
    carrito.agregar_producto("Laptop", 1_000_000, 1)

    if debe_pasar:
        carrito.aplicar_descuento("porcentaje", descuento)
        assert carrito.calcular_total() == pytest.approx(total_esperado, rel=1e-3)
    else:
        with pytest.raises(ValueError):
            carrito.aplicar_descuento("porcentaje", descuento)


# ─────────────────────────────────────────────────────────────────────────────
# SECCIÓN 3 — Transición de Estados
#
# Estados del carrito:
#   VACÍO → CON ITEMS → CON DESCUENTO → VACÍO (via vaciar)
# ─────────────────────────────────────────────────────────────────────────────


class TestTransicionesValidas:
    """Transiciones que deben funcionar correctamente."""

    def test_estado_inicial_es_vacio(self):
        """Todo carrito nuevo nace en estado VACÍO."""
        carrito = Carrito()
        assert carrito.cantidad_productos() == 0
        assert carrito.calcular_total() == 0

    def test_vacio_mas_producto_da_con_items(self):
        """VACÍO + agregar_producto() → CON ITEMS."""
        carrito = Carrito()
        carrito.agregar_producto("Laptop", 2_500_000, 1)
        assert carrito.cantidad_productos() == 1

    def test_con_items_mas_descuento_da_con_descuento(self):
        """CON ITEMS + aplicar_descuento() → CON DESCUENTO."""
        carrito = Carrito()
        carrito.agregar_producto("Laptop", 1_000_000, 1)
        carrito.aplicar_descuento("porcentaje", 10)
        assert carrito.calcular_total() == pytest.approx(900_000)

    def test_con_items_menos_ultimo_producto_da_vacio(self):
        """CON ITEMS (1 producto) + eliminar_producto() → VACÍO."""
        carrito = Carrito()
        carrito.agregar_producto("Laptop", 2_500_000, 1)
        carrito.eliminar_producto("Laptop")
        assert carrito.cantidad_productos() == 0

    def test_vaciar_desde_con_descuento_da_vacio(self):
        """CON DESCUENTO + vaciar() → VACÍO limpio."""
        carrito = Carrito()
        carrito.agregar_producto("Laptop", 1_000_000, 1)
        carrito.aplicar_descuento("porcentaje", 10)
        carrito.vaciar()
        assert carrito.cantidad_productos() == 0
        assert carrito.calcular_total() == 0

    def test_descuento_persiste_al_agregar_mas_productos(self):
        """En CON DESCUENTO, agregar más items mantiene el descuento activo."""
        carrito = Carrito()
        carrito.agregar_producto("Laptop", 1_000_000, 1)
        carrito.aplicar_descuento("porcentaje", 10)
        carrito.agregar_producto("Mouse", 100_000, 1)
        # (1_000_000 + 100_000) × 0.90 = 990_000
        assert carrito.calcular_total() == pytest.approx(990_000)


class TestTransicionesInvalidas:
    """Transiciones que deben rechazarse o manejarse con cuidado."""

    def test_eliminar_producto_inexistente_lanza_error(self):
        """VACÍO + eliminar_producto() → ValueError."""
        carrito = Carrito()
        with pytest.raises(ValueError, match="no se encuentra"):
            carrito.eliminar_producto("ProductoFantasma")

    def test_descuento_invalido_falla_en_cualquier_estado(self):
        """Descuento fuera de rango falla sin importar el estado del carrito."""
        carrito_vacio = Carrito()
        with pytest.raises(ValueError):
            carrito_vacio.aplicar_descuento("porcentaje", 200)

        carrito_con_items = Carrito()
        carrito_con_items.agregar_producto("Laptop", 1_000_000, 1)
        with pytest.raises(ValueError):
            carrito_con_items.aplicar_descuento("porcentaje", 200)

    def test_vaciar_carrito_ya_vacio_no_lanza_error(self):
        """VACÍO + vaciar() → sigue VACÍO (operación idempotente)."""
        carrito = Carrito()
        carrito.vaciar()
        assert carrito.cantidad_productos() == 0
