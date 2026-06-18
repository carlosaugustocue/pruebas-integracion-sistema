"""
Pruebas funcionales del carrito de TiendaUV.

Pruebas funcionales vs pruebas unitarias
-----------------------------------------
Las pruebas unitarias de test_carrito.py verifican que el codigo funciona.
Las pruebas funcionales aplican TECNICAS DE DISENO para elegir que valores
probar de forma sistematica, maximizando la probabilidad de encontrar defectos
con el menor numero de casos posible.

Probar todos los valores posibles (cantidad puede ser cualquier entero) es
imposible. Las tecnicas de diseno resuelven este problema: en vez de probar
al azar, identifican las clases de valores que tienen el mismo comportamiento
y prueban un representativo por clase.

Las tres tecnicas aplicadas en este archivo
-------------------------------------------

1. PARTICION DE EQUIVALENCIA
   Si el sistema se comporta igual para todos los valores de un rango,
   basta probar uno de ellos. Para el campo cantidad (valido: 1-99):
     - Particion invalida baja: cualquier valor <= 0 deberia dar ValueError.
       Probar -3 detecta el defecto. Probar -100 y -50 y -1 no agrega valor.
     - Particion valida: cualquier valor entre 1 y 99 deberia funcionar.
       Probar 50 (centro) es suficiente.
     - Particion invalida alta: cualquier valor >= 100 deberia dar ValueError.
       Probar 500 detecta el defecto.

2. ANALISIS DE VALORES LIMITE (Boundary Value Analysis)
   Los bugs "off-by-one" (usar > en vez de >=) solo se revelan en los valores
   exactos del limite. Si el valido es 1-99, los limites criticos son:
     0 (justo fuera del limite inferior)
     1 (limite inferior exacto)
     99 (limite superior exacto)
     100 (justo fuera del limite superior)
   Esta tecnica complementa la particion: donde la particion prueba el centro,
   el analisis de limites prueba los bordes.

3. TRANSICION DE ESTADOS
   El carrito tiene estados implicitos. No es lo mismo un carrito vacio que
   uno con items, que uno con descuento. Algunas operaciones solo tienen
   sentido en ciertos estados (no puedes eliminar un producto de un carrito
   vacio). La tecnica de transicion de estados identifica los estados, las
   transiciones validas y las invalidas, y genera un test por transicion.

   Estados del carrito:
     VACIO → (agregar producto) → CON ITEMS
     CON ITEMS → (aplicar descuento) → CON DESCUENTO
     CON ITEMS → (eliminar ultimo producto) → VACIO
     CON DESCUENTO → (vaciar) → VACIO

Sobre la clase bajo prueba
---------------------------
Todos estos tests usan directamente src/carrito/carrito.py (la clase Carrito),
sin API, sin BD, sin fixtures. La misma clase que los tests unitarios de TDD,
pero aqui el foco es el DISENO DE LOS CASOS DE PRUEBA, no el codigo mismo.
"""

import pytest

from src.carrito.carrito import Carrito

# ─────────────────────────────────────────────────────────────────────────────
# SECCION 1 — Particion de Equivalencia: campo "cantidad"
#
# Particiones identificadas (rango valido 1-99):
#   P1 — Invalida baja : cantidad <= 0  → ValueError
#   P2 — Valida        : 1 <= cantidad <= 99 → OK
#   P3 — Invalida alta : cantidad >= 100 → ValueError
# ─────────────────────────────────────────────────────────────────────────────


class TestParticionEquivalenciaCantidad:
    """
    Un representativo por particion es suficiente para detectar el defecto.

    La clase agrupa los tests relacionados con la misma tecnica y el mismo
    campo bajo prueba. En pytest, las clases son opcionales pero utiles para
    organizar y para compartir setup via setup_method.
    """

    def test_cantidad_negativa_rechazada(self):
        """P1 — representativo: -3 (particion invalida baja)."""
        carrito = Carrito()
        with pytest.raises(ValueError):
            carrito.agregar_producto("Laptop", 2_500_000, -3)

    def test_cantidad_cero_rechazada(self):
        """P1 — representativo: 0 (borde inferior de la particion invalida baja)."""
        # 0 esta en P1 (invalida baja). Es un borde, pero sigue siendo P1.
        carrito = Carrito()
        with pytest.raises(ValueError):
            carrito.agregar_producto("Laptop", 2_500_000, 0)

    def test_cantidad_valida_aceptada(self):
        """P2 — representativo: 50 (centro de la particion valida)."""
        carrito = Carrito()
        carrito.agregar_producto("Laptop", 2_500_000, 50)
        assert carrito.cantidad_productos() == 1

    def test_cantidad_sobre_maximo_rechazada(self):
        """P3 — representativo: 500 (particion invalida alta)."""
        carrito = Carrito()
        with pytest.raises(ValueError):
            carrito.agregar_producto("Laptop", 2_500_000, 500)


# Version compacta con parametrize (cubre las 3 particiones mas los bordes):
# @pytest.mark.parametrize permite correr el mismo test con diferentes entradas
# sin duplicar codigo. Cada tupla (cantidad, es_valida) genera un test separado
# en el reporte de pytest con el nombre test_particion_cantidad_parametrizado[...].
@pytest.mark.parametrize(
    "cantidad, es_valida",
    [
        (-3, False),  # P1 invalida baja (negativo)
        (0, False),  # P1 invalida baja (cero)
        (1, True),  # P2 valida (minimo, es un limite pero esta en P2)
        (50, True),  # P2 valida (centro)
        (99, True),  # P2 valida (maximo, limite superior de P2)
        (100, False),  # P3 invalida alta (justo fuera)
        (500, False),  # P3 invalida alta (extremo)
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
# SECCION 2 — Analisis de Valores Limite: campo "porcentaje de descuento"
#
# Rango valido: 0 % a 100 %
# Los 6 valores criticos: -0.1, 0, 0.1, 99.9, 100, 100.1
#
# Por que 6 valores? Cada limite tiene 3 valores: justo afuera, exactamente
# en el limite, y justo adentro. Con 2 limites: 2 x 3 = 6 valores.
# ─────────────────────────────────────────────────────────────────────────────


class TestValoresLimiteDescuento:
    """
    Limite inferior: 0 %
    Limite superior: 100 %

    Valores a probar: -0.1 | 0 | 0.1 | 99.9 | 100 | 100.1

    setup_method es el equivalente de un @pytest.fixture scope="function"
    pero dentro de una clase. Se ejecuta antes de cada metodo test_ de la clase.
    Aqui crea un carrito con un Laptop de $1M para poder aplicar descuentos.
    """

    def setup_method(self):
        self.carrito = Carrito()
        self.carrito.agregar_producto("Laptop", 1_000_000, 1)

    # ── Limite inferior ──────────────────────────────────────────────

    def test_descuento_negativo_0_1_falla(self):
        """Limite inferior - 0.1: justo fuera → DEBE FALLAR."""
        with pytest.raises(ValueError):
            self.carrito.aplicar_descuento("porcentaje", -0.1)

    def test_descuento_exactamente_0_pasa(self):
        """Limite inferior exacto: 0 % valido → sin descuento."""
        self.carrito.aplicar_descuento("porcentaje", 0)
        assert self.carrito.calcular_total() == 1_000_000

    def test_descuento_0_1_pasa(self):
        """Limite inferior + 0.1: justo dentro → PASA."""
        self.carrito.aplicar_descuento("porcentaje", 0.1)
        # pytest.approx maneja la imprecision de punto flotante
        assert self.carrito.calcular_total() == pytest.approx(999_000)

    # ── Limite superior ──────────────────────────────────────────────

    def test_descuento_99_9_pasa(self):
        """Limite superior - 0.1: justo dentro → PASA."""
        self.carrito.aplicar_descuento("porcentaje", 99.9)
        assert self.carrito.calcular_total() == pytest.approx(1_000)

    def test_descuento_exactamente_100_pasa(self):
        """Limite superior exacto: 100 % valido → total cero."""
        self.carrito.aplicar_descuento("porcentaje", 100)
        assert self.carrito.calcular_total() == 0

    def test_descuento_100_1_falla(self):
        """Limite superior + 0.1: justo fuera → DEBE FALLAR."""
        with pytest.raises(ValueError):
            self.carrito.aplicar_descuento("porcentaje", 100.1)


# Version compacta con parametrize:
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
# SECCION 3 — Transicion de Estados
#
# Estados del carrito identificados:
#   VACIO: cantidad_productos() == 0
#   CON ITEMS: cantidad_productos() >= 1
#   CON DESCUENTO: CON ITEMS + descuento activo
#
# El carrito no tiene un atributo "estado" explicito. Los estados son
# propiedades emergentes: se deducen de la combinacion de _productos y
# _descuento_tipo. La tecnica de transicion de estados los hace explicitos.
#
# Diagrama de transiciones:
#   VACIO --(agregar_producto)--> CON ITEMS
#   CON ITEMS --(agregar_producto mas)--> CON ITEMS (se mantiene en el estado)
#   CON ITEMS --(eliminar ultimo producto)--> VACIO
#   CON ITEMS --(aplicar_descuento)--> CON DESCUENTO
#   CON DESCUENTO --(agregar_producto)--> CON DESCUENTO (el descuento persiste)
#   CON DESCUENTO --(vaciar)--> VACIO
#   VACIO --(vaciar)--> VACIO (idempotente: no falla)
# ─────────────────────────────────────────────────────────────────────────────


class TestTransicionesValidas:
    """Transiciones que deben funcionar correctamente."""

    def test_estado_inicial_es_vacio(self):
        """Todo carrito nuevo nace en estado VACIO."""
        carrito = Carrito()
        assert carrito.cantidad_productos() == 0
        assert carrito.calcular_total() == 0

    def test_vacio_mas_producto_da_con_items(self):
        """VACIO + agregar_producto() → CON ITEMS."""
        carrito = Carrito()
        carrito.agregar_producto("Laptop", 2_500_000, 1)
        assert carrito.cantidad_productos() == 1

    def test_con_items_mas_descuento_da_con_descuento(self):
        """CON ITEMS + aplicar_descuento() → CON DESCUENTO."""
        carrito = Carrito()
        carrito.agregar_producto("Laptop", 1_000_000, 1)
        carrito.aplicar_descuento("porcentaje", 10)
        # El estado CON DESCUENTO se evidencia en que el total es diferente al subtotal
        assert carrito.calcular_total() == pytest.approx(900_000)

    def test_con_items_menos_ultimo_producto_da_vacio(self):
        """CON ITEMS (1 producto) + eliminar_producto() → VACIO."""
        carrito = Carrito()
        carrito.agregar_producto("Laptop", 2_500_000, 1)
        carrito.eliminar_producto("Laptop")
        assert carrito.cantidad_productos() == 0

    def test_vaciar_desde_con_descuento_da_vacio(self):
        """CON DESCUENTO + vaciar() → VACIO limpio."""
        carrito = Carrito()
        carrito.agregar_producto("Laptop", 1_000_000, 1)
        carrito.aplicar_descuento("porcentaje", 10)
        carrito.vaciar()
        # Verificar que el descuento tambien se elimino (no solo los productos)
        assert carrito.cantidad_productos() == 0
        assert carrito.calcular_total() == 0

    def test_descuento_persiste_al_agregar_mas_productos(self):
        """En CON DESCUENTO, agregar mas items mantiene el descuento activo."""
        carrito = Carrito()
        carrito.agregar_producto("Laptop", 1_000_000, 1)
        carrito.aplicar_descuento("porcentaje", 10)
        carrito.agregar_producto("Mouse", 100_000, 1)
        # El descuento del 10% se aplica sobre el nuevo subtotal total
        # (1_000_000 + 100_000) x 0.90 = 990_000
        assert carrito.calcular_total() == pytest.approx(990_000)


class TestTransicionesInvalidas:
    """Transiciones que deben rechazarse o manejarse con cuidado."""

    def test_eliminar_producto_inexistente_lanza_error(self):
        """VACIO + eliminar_producto() → ValueError."""
        carrito = Carrito()
        with pytest.raises(ValueError, match="no se encuentra"):
            carrito.eliminar_producto("ProductoFantasma")

    def test_descuento_invalido_falla_en_cualquier_estado(self):
        """Descuento fuera de rango falla sin importar el estado del carrito."""
        # Estado VACIO: el descuento invalido igual debe rechazarse
        carrito_vacio = Carrito()
        with pytest.raises(ValueError):
            carrito_vacio.aplicar_descuento("porcentaje", 200)

        # Estado CON ITEMS: igual debe rechazarse
        carrito_con_items = Carrito()
        carrito_con_items.agregar_producto("Laptop", 1_000_000, 1)
        with pytest.raises(ValueError):
            carrito_con_items.aplicar_descuento("porcentaje", 200)

    def test_vaciar_carrito_ya_vacio_no_lanza_error(self):
        """VACIO + vaciar() → sigue VACIO (operacion idempotente)."""
        # Una operacion idempotente puede aplicarse multiples veces sin efectos adicionales.
        # vaciar() en un carrito ya vacio no deberia lanzar error: ya esta vacio, objetivo cumplido.
        carrito = Carrito()
        carrito.vaciar()
        assert carrito.cantidad_productos() == 0
