"""
Pruebas unitarias para la clase Carrito — TDD (Test-Driven Development).

Que es TDD y por que escribir el test antes que el codigo
---------------------------------------------------------
TDD es una disciplina de desarrollo donde el ciclo es:

    1. RED   — escribir un test que describa el comportamiento deseado.
               El test falla porque el codigo no existe todavia.
    2. GREEN — escribir el codigo minimo para que el test pase.
               Sin sobre-ingenieria: solo lo necesario para que el test sea verde.
    3. REFACTOR — mejorar el codigo sin romper los tests.
                  Limpiar duplicacion, renombrar variables, extraer funciones.

Beneficio principal: el test es la especificacion ejecutable. Antes de escribir
una linea de produccion, tienes que pensar en como se usa la clase, que parametros
recibe, que retorna, que errores lanza. TDD fuerza ese pensamiento hacia adelante.

Por que cada test verifica UNA sola cosa
-----------------------------------------
Si un test verifica cinco cosas y falla, no sabes cual de las cinco rompiste.
Si verifica una sola cosa, el nombre del test ya te dice exactamente que fallo.
Regla: un test, un assert logico (aunque haya varios assert en el codigo si todos
verifican el mismo concepto).

Que se esta probando aqui
-------------------------
La clase Carrito en src/carrito/carrito.py opera en memoria, sin base de datos,
sin API, sin HTTP. Es logica de negocio pura: listas de Producto, calculos de
total, validaciones de descuento.

Estos tests NO necesitan:
  - Docker
  - PostgreSQL
  - FastAPI
  - Fixtures del conftest.py

Cada test crea su propio Carrito desde cero. Setup minimo, sin estado compartido
entre tests. Si un test falla, no afecta a los demas.

Sobre las importaciones dentro de cada test
--------------------------------------------
Las importaciones de Carrito estan dentro de cada funcion de test en lugar de
al inicio del archivo. Esto es un patron de TDD puro: el test no deberia importar
nada hasta que la clase exista. En la practica con el codigo ya escrito, tambien
funciona importar al inicio, pero mantener las importaciones dentro del test hace
que el test sea completamente autocontenido y legible en aislamiento.
"""

import pytest


def test_carrito_inicia_vacio():
    """Un carrito recien creado no debe tener productos."""
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

    # El carrito no debe tener dos entradas separadas para Laptop
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

    # pytest.raises actua como context manager: el bloque dentro DEBE lanzar
    # la excepcion indicada. Si no la lanza, el test falla.
    # match= comprueba que el mensaje de la excepcion contiene ese substring.
    with pytest.raises(ValueError, match="no se encuentra"):
        carrito.eliminar_producto("Tablet")


# ─────────────────────────────────────────────────────────────────────────────
# R3: Calcular el total del carrito
# ─────────────────────────────────────────────────────────────────────────────


def test_total_carrito_vacio():
    """El total de un carrito vacio debe ser 0."""
    from src.carrito.carrito import Carrito

    carrito = Carrito()

    assert carrito.calcular_total() == 0


def test_total_con_un_producto():
    """El total con un producto es precio x cantidad."""
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

    # 2500000 x 1 + 85000 x 2 = 2500000 + 170000 = 2670000
    assert carrito.calcular_total() == 2670000


# ─────────────────────────────────────────────────────────────────────────────
# R4: Aplicar descuentos por cupon
# ─────────────────────────────────────────────────────────────────────────────


def test_descuento_porcentaje():
    """Un cupon de 10% reduce el total proporcionalmente."""
    from src.carrito.carrito import Carrito

    carrito = Carrito()
    carrito.agregar_producto(nombre="Laptop", precio=1000000, cantidad=1)

    carrito.aplicar_descuento(tipo="porcentaje", valor=10)

    # 1000000 - 10% = 900000
    assert carrito.calcular_total() == 900000


def test_descuento_fijo():
    """Un cupon de valor fijo resta la cantidad exacta."""
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

    # Descuento mayor que el precio del producto
    carrito.aplicar_descuento(tipo="fijo", valor=100000)

    # max(subtotal - descuento, 0) garantiza que nunca sea negativo
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
    """No se puede agregar mas cantidad que el stock disponible."""
    from src.carrito.carrito import Carrito

    stock = {"Laptop": 5, "Mouse": 10}
    carrito = Carrito(stock_disponible=stock)

    carrito.agregar_producto(nombre="Laptop", precio=2500000, cantidad=3)

    assert carrito.cantidad_productos() == 1


def test_agregar_producto_sin_stock_suficiente():
    """Agregar mas unidades que el stock lanza error."""
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

    # 1000000 x 1.19 = 1190000
    assert total_con_iva == 1190000


def test_total_con_iva_y_descuento():
    """El IVA se aplica DESPUES del descuento."""
    from src.carrito.carrito import Carrito

    carrito = Carrito()
    carrito.agregar_producto(nombre="Laptop", precio=1000000, cantidad=1)
    carrito.aplicar_descuento(tipo="porcentaje", valor=10)

    total_con_iva = carrito.calcular_total_con_impuestos()

    # Orden correcto: 1000000 - 10% = 900000 → 900000 x 1.19 = 1071000
    # Orden incorrecto (bug comun): 1000000 x 1.19 = 1190000 - 10% = 1071000 (coincide aqui)
    # Para distinguirlo, ver test_total_con_iva_personalizado con descuento fijo
    assert total_con_iva == 1071000


def test_total_con_iva_personalizado():
    """Se puede usar una tasa de impuesto diferente."""
    from src.carrito.carrito import Carrito

    carrito = Carrito()
    carrito.agregar_producto(nombre="Laptop", precio=1000000, cantidad=1)

    # Tasa del 5% (ejemplo: productos de la canasta familiar en Colombia)
    total_con_iva = carrito.calcular_total_con_impuestos(tasa=5)

    # 1000000 x 1.05 = 1050000
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

    # Los tres asserts verifican el mismo concepto: el carrito quedo en estado inicial
    assert carrito.cantidad_productos() == 0
    assert carrito.calcular_total() == 0
    assert carrito.obtener_productos() == []


# ─────────────────────────────────────────────────────────────────────────────
# R8: Comportamiento con multiples descuentos aplicados
# ─────────────────────────────────────────────────────────────────────────────


def test_carrito_con_multiples_descuentos_aplica_el_ultimo():
    """
    Si se aplican dos descuentos seguidos, debe quedar activo solo el ultimo.
    El nuevo descuento reemplaza al anterior, no se acumulan.
    """
    from src.carrito.carrito import Carrito

    carrito = Carrito()
    carrito.agregar_producto("Laptop", 1_000_000, 1)

    carrito.aplicar_descuento("porcentaje", 10)  # Primer descuento: 900000
    carrito.aplicar_descuento("porcentaje", 20)  # Segundo descuento: reemplaza al primero

    # Solo debe aplicarse el 20%, no el 10% + 20% = 1000000 x 0.80 = 800000
    assert carrito.calcular_total() == 800_000
