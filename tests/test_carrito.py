"""
Tests unitarios para el carrito de compras - TDD
Cada test se escribió ANTES que el código de producción.
"""

import pytest


def test_carrito_inicia_vacio():
    """Un carrito recién creado no debe tener productos."""
    from src.carrito.carrito import Carrito

    carrito = Carrito()

    assert carrito.obtener_productos() == []
    assert carrito.cantidad_productos() == 0


def test_agregar_un_producto():
    """Al agregar un producto, debe aparecer en el carrito."""
    from src.carrito.carrito import Carrito

    carrito = Carrito()

    carrito.agregar_producto(nombre="Laptop", precio=2500000, cantidad=1)

    productos = carrito.obtener_productos()
    assert len(productos) == 1
    assert productos[0]["nombre"] == "Laptop"
    assert productos[0]["precio"] == 2500000
    assert productos[0]["cantidad"] == 1


def test_agregar_multiples_productos():
    """El carrito debe poder contener varios productos distintos."""
    from src.carrito.carrito import Carrito

    carrito = Carrito()

    carrito.agregar_producto(nombre="Laptop", precio=2500000, cantidad=1)
    carrito.agregar_producto(nombre="Mouse", precio=85000, cantidad=2)

    assert carrito.cantidad_productos() == 2


def test_agregar_producto_existente_suma_cantidad():
    """Si agrego un producto que ya existe, se suma la cantidad."""
    from src.carrito.carrito import Carrito

    carrito = Carrito()

    carrito.agregar_producto(nombre="Laptop", precio=2500000, cantidad=1)
    carrito.agregar_producto(nombre="Laptop", precio=2500000, cantidad=2)

    productos = carrito.obtener_productos()
    assert len(productos) == 1
    assert productos[0]["cantidad"] == 3


# ─────────────────────────────────────────────────────────────────────────────
# R2: Eliminar productos del carrito
# ─────────────────────────────────────────────────────────────────────────────


def test_eliminar_producto():
    """Al eliminar un producto, ya no debe estar en el carrito."""
    from src.carrito.carrito import Carrito

    carrito = Carrito()
    carrito.agregar_producto(nombre="Laptop", precio=2500000, cantidad=1)
    carrito.agregar_producto(nombre="Mouse", precio=85000, cantidad=2)

    carrito.eliminar_producto("Laptop")

    assert carrito.cantidad_productos() == 1
    nombres = [p["nombre"] for p in carrito.obtener_productos()]
    assert "Laptop" not in nombres


def test_eliminar_producto_inexistente_lanza_error():
    """Eliminar un producto que no existe debe lanzar ValueError."""
    from src.carrito.carrito import Carrito

    carrito = Carrito()

    with pytest.raises(ValueError, match="no se encuentra"):
        carrito.eliminar_producto("Tablet")


# ─────────────────────────────────────────────────────────────────────────────
# R3: Calcular el total del carrito
# ─────────────────────────────────────────────────────────────────────────────


def test_total_carrito_vacio():
    """El total de un carrito vacío debe ser 0."""
    from src.carrito.carrito import Carrito

    carrito = Carrito()

    assert carrito.calcular_total() == 0


def test_total_con_un_producto():
    """El total con un producto es precio × cantidad."""
    from src.carrito.carrito import Carrito

    carrito = Carrito()
    carrito.agregar_producto(nombre="Laptop", precio=2500000, cantidad=2)

    assert carrito.calcular_total() == 5000000


def test_total_con_multiples_productos():
    """El total es la suma de subtotales de todos los productos."""
    from src.carrito.carrito import Carrito

    carrito = Carrito()
    carrito.agregar_producto(nombre="Laptop", precio=2500000, cantidad=1)
    carrito.agregar_producto(nombre="Mouse", precio=85000, cantidad=2)

    # 2500000 × 1 + 85000 × 2 = 2500000 + 170000 = 2670000
    assert carrito.calcular_total() == 2670000


# ─────────────────────────────────────────────────────────────────────────────
# R4: Aplicar descuentos por cupón
# ─────────────────────────────────────────────────────────────────────────────


def test_descuento_porcentaje():
    """Un cupón de 10% reduce el total proporcionalmente."""
    from src.carrito.carrito import Carrito

    carrito = Carrito()
    carrito.agregar_producto(nombre="Laptop", precio=1000000, cantidad=1)

    carrito.aplicar_descuento(tipo="porcentaje", valor=10)

    # 1000000 - 10% = 900000
    assert carrito.calcular_total() == 900000


def test_descuento_fijo():
    """Un cupón de valor fijo resta la cantidad exacta."""
    from src.carrito.carrito import Carrito

    carrito = Carrito()
    carrito.agregar_producto(nombre="Laptop", precio=1000000, cantidad=1)

    carrito.aplicar_descuento(tipo="fijo", valor=150000)

    # 1000000 - 150000 = 850000
    assert carrito.calcular_total() == 850000


def test_descuento_fijo_no_genera_total_negativo():
    """Si el descuento fijo supera el total, el resultado es 0."""
    from src.carrito.carrito import Carrito

    carrito = Carrito()
    carrito.agregar_producto(nombre="Mouse", precio=50000, cantidad=1)

    carrito.aplicar_descuento(tipo="fijo", valor=100000)

    assert carrito.calcular_total() == 0


def test_descuento_porcentaje_invalido():
    """Un porcentaje mayor a 100 o negativo lanza error."""
    from src.carrito.carrito import Carrito

    carrito = Carrito()

    with pytest.raises(ValueError, match="porcentaje"):
        carrito.aplicar_descuento(tipo="porcentaje", valor=150)

    with pytest.raises(ValueError, match="porcentaje"):
        carrito.aplicar_descuento(tipo="porcentaje", valor=-5)


# ─────────────────────────────────────────────────────────────────────────────
# R5: Validar stock disponible
# ─────────────────────────────────────────────────────────────────────────────


def test_agregar_producto_respetando_stock():
    """No se puede agregar más cantidad que el stock disponible."""
    from src.carrito.carrito import Carrito

    stock = {"Laptop": 5, "Mouse": 10}
    carrito = Carrito(stock_disponible=stock)

    carrito.agregar_producto(nombre="Laptop", precio=2500000, cantidad=3)

    assert carrito.cantidad_productos() == 1


def test_agregar_producto_sin_stock_suficiente():
    """Agregar más unidades que el stock lanza error."""
    from src.carrito.carrito import Carrito

    stock = {"Laptop": 2}
    carrito = Carrito(stock_disponible=stock)

    with pytest.raises(ValueError, match="stock"):
        carrito.agregar_producto(nombre="Laptop", precio=2500000, cantidad=5)


def test_agregar_producto_que_no_existe_en_stock():
    """Agregar un producto sin stock definido lanza error."""
    from src.carrito.carrito import Carrito

    stock = {"Laptop": 5}
    carrito = Carrito(stock_disponible=stock)

    with pytest.raises(ValueError, match="stock"):
        carrito.agregar_producto(nombre="Tablet", precio=800000, cantidad=1)


# ─────────────────────────────────────────────────────────────────────────────
# R6: Calcular total con impuestos (IVA 19%)
# ─────────────────────────────────────────────────────────────────────────────


def test_total_con_iva():
    """El total con IVA aplica 19% sobre el subtotal."""
    from src.carrito.carrito import Carrito

    carrito = Carrito()
    carrito.agregar_producto(nombre="Laptop", precio=1000000, cantidad=1)

    total_con_iva = carrito.calcular_total_con_impuestos()

    # 1000000 × 1.19 = 1190000
    assert total_con_iva == 1190000


def test_total_con_iva_y_descuento():
    """El IVA se aplica DESPUÉS del descuento."""
    from src.carrito.carrito import Carrito

    carrito = Carrito()
    carrito.agregar_producto(nombre="Laptop", precio=1000000, cantidad=1)
    carrito.aplicar_descuento(tipo="porcentaje", valor=10)

    total_con_iva = carrito.calcular_total_con_impuestos()

    # 1000000 - 10% = 900000 → 900000 × 1.19 = 1071000
    assert total_con_iva == 1071000


def test_total_con_iva_personalizado():
    """Se puede usar una tasa de impuesto diferente."""
    from src.carrito.carrito import Carrito

    carrito = Carrito()
    carrito.agregar_producto(nombre="Laptop", precio=1000000, cantidad=1)

    # Tasa del 5% (ejemplo: productos de la canasta familiar en Colombia)
    total_con_iva = carrito.calcular_total_con_impuestos(tasa=5)

    # 1000000 × 1.05 = 1050000
    assert total_con_iva == 1050000


# ─────────────────────────────────────────────────────────────────────────────
# R7: Vaciar el carrito
# ─────────────────────────────────────────────────────────────────────────────


def test_vaciar_carrito():
    """Vaciar elimina todos los productos y descuentos."""
    from src.carrito.carrito import Carrito

    carrito = Carrito()
    carrito.agregar_producto(nombre="Laptop", precio=2500000, cantidad=1)
    carrito.agregar_producto(nombre="Mouse", precio=85000, cantidad=2)
    carrito.aplicar_descuento(tipo="porcentaje", valor=10)

    carrito.vaciar()

    assert carrito.cantidad_productos() == 0
    assert carrito.calcular_total() == 0
    assert carrito.obtener_productos() == []


# ─────────────────────────────────────────────────────────────────────────────
# R8: Comportamiento con múltiples descuentos aplicados
# ─────────────────────────────────────────────────────────────────────────────


def test_carrito_con_multiples_descuentos_aplica_el_ultimo():
    """
    Si se aplican dos descuentos seguidos, debe quedar activo solo el último.
    El nuevo descuento reemplaza al anterior, no se acumulan.
    """
    from src.carrito.carrito import Carrito

    carrito = Carrito()
    carrito.agregar_producto("Laptop", 1_000_000, 1)

    carrito.aplicar_descuento("porcentaje", 10)  # Primer descuento
    carrito.aplicar_descuento("porcentaje", 20)  # Segundo descuento (reemplaza)

    # Solo debe aplicarse el 20%, no el 10% + 20%
    assert carrito.calcular_total() == 800_000
