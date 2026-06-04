"""
Step definitions para los escenarios BDD del carrito de compras.
Cada función implementa un paso (Given/When/Then) del feature file.
"""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.carrito.carrito import Carrito

# ──────────────────────────────────────────────────────
# Registrar todos los escenarios del feature file
# ──────────────────────────────────────────────────────
scenarios("carrito.feature")


# ──────────────────────────────────────────────────────
# GIVEN: Precondiciones
# ──────────────────────────────────────────────────────


@given("un carrito de compras vacío", target_fixture="carrito")
def carrito_vacio():
    """Crea un carrito nuevo y vacío."""
    return Carrito()


@given(
    parsers.parse(
        'el carrito tiene el producto "{nombre}" con precio {precio:d} y cantidad {cantidad:d}'
    ),
    target_fixture="carrito",
)
def carrito_con_producto(carrito, nombre, precio, cantidad):
    """Agrega un producto al carrito como precondición."""
    carrito.agregar_producto(nombre=nombre, precio=precio, cantidad=cantidad)
    return carrito


@given("un carrito con stock disponible:", target_fixture="contexto")
def carrito_con_stock(datatable):
    """
    Crea un carrito con stock limitado usando una tabla de datos.
    La tabla viene directamente del feature file.
    En pytest-bdd 8.x, datatable es una lista de listas (primera fila = headers).
    """
    headers = datatable[0]
    stock = {}
    for row in datatable[1:]:
        fila = dict(zip(headers, row))
        stock[fila["producto"]] = int(fila["stock"])

    return {"error": None, "carrito": Carrito(stock_disponible=stock)}


# ──────────────────────────────────────────────────────
# WHEN: Acciones
# ──────────────────────────────────────────────────────


@when(parsers.parse('agrego el producto "{nombre}" con precio {precio:d} y cantidad {cantidad:d}'))
def agregar_producto(carrito, nombre, precio, cantidad):
    """Ejecuta la acción de agregar un producto al carrito."""
    carrito.agregar_producto(nombre=nombre, precio=precio, cantidad=cantidad)


@when(parsers.parse('elimino el producto "{nombre}"'))
def eliminar_producto(carrito, nombre):
    """Ejecuta la acción de eliminar un producto."""
    carrito.eliminar_producto(nombre)


@when(parsers.parse('aplico un descuento de tipo "{tipo}" con valor {valor:d}'))
def aplicar_descuento(carrito, tipo, valor):
    """Aplica un descuento al carrito."""
    carrito.aplicar_descuento(tipo=tipo, valor=valor)


@when(parsers.parse('intento agregar "{nombre}" con precio {precio:d} y cantidad {cantidad:d}'))
def intentar_agregar_producto(contexto, nombre, precio, cantidad):
    """Intenta agregar un producto, capturando errores si ocurren."""
    try:
        contexto["carrito"].agregar_producto(nombre=nombre, precio=precio, cantidad=cantidad)
    except ValueError as e:
        contexto["error"] = str(e)


@when("vacío el carrito")
def vaciar_carrito(carrito):
    """Vacía completamente el carrito."""
    carrito.vaciar()


# ──────────────────────────────────────────────────────
# THEN: Verificaciones
# ──────────────────────────────────────────────────────


@then(parsers.parse("el carrito contiene {cantidad:d} producto"))
@then(parsers.parse("el carrito contiene {cantidad:d} productos"))
def verificar_cantidad_productos(carrito, cantidad):
    """Verifica cuántos productos distintos hay en el carrito."""
    assert carrito.cantidad_productos() == cantidad


@then(parsers.parse('el producto "{nombre}" está en el carrito'))
def verificar_producto_existe(carrito, nombre):
    """Verifica que un producto específico está en el carrito."""
    nombres = [p["nombre"] for p in carrito.obtener_productos()]
    assert nombre in nombres


@then(parsers.parse('el producto "{nombre}" tiene cantidad {cantidad:d}'))
def verificar_cantidad_producto(carrito, nombre, cantidad):
    """Verifica la cantidad de un producto específico."""
    for p in carrito.obtener_productos():
        if p["nombre"] == nombre:
            assert p["cantidad"] == cantidad
            return
    pytest.fail(f"Producto '{nombre}' no encontrado en el carrito")


@then(parsers.parse("el total del carrito es {total:d}"))
def verificar_total(carrito, total):
    """Verifica el total del carrito sin impuestos."""
    assert carrito.calcular_total() == total


@then(parsers.parse("el total con impuestos es {total:d}"))
def verificar_total_con_impuestos(carrito, total):
    """Verifica el total del carrito con IVA 19%."""
    assert carrito.calcular_total_con_impuestos() == total


@then(parsers.parse('se produce un error que contiene "{texto}"'))
def verificar_error(contexto, texto):
    """Verifica que se produjo un error con el texto esperado."""
    assert contexto["error"] is not None, "Se esperaba un error pero no ocurrió"
    assert texto in contexto["error"], (
        f"Error esperado con '{texto}', pero el error fue: {contexto['error']}"
    )
