"""
Step definitions para los escenarios BDD del carrito de compras.

Que es BDD y como se diferencia de TDD
---------------------------------------
BDD (Behavior-Driven Development) es una evolucion de TDD que pone el foco en
el comportamiento del sistema desde la perspectiva del usuario o del negocio.
En TDD escribes tests tecnicos ("test_calcular_total_con_un_producto"). En BDD
escribes escenarios en lenguaje casi natural que cualquier persona del equipo
puede leer y confirmar que representan lo que quiere el sistema:

    Scenario: Calcular el total del carrito
      When agrego el producto "Laptop" con precio 2500000 y cantidad 1
      And agrego el producto "Mouse" con precio 85000 y cantidad 2
      Then el total del carrito es 2670000

Un product owner puede leer ese escenario y confirmar: "si, eso es lo que quiero".
Si el test pasa, el comportamiento esta implementado. Si falla, el sistema difiere
de lo que se especifico.

La estructura Given / When / Then
----------------------------------
Cada escenario BDD tiene tres fases:

  Given (Dado): el contexto inicial. El estado del mundo antes de la accion.
                Ejemplo: "un carrito de compras vacio".
  When  (Cuando): la accion que se realiza. Lo que el usuario o el sistema hace.
                  Ejemplo: "agrego el producto 'Laptop' con precio 2500000 y cantidad 1".
  Then  (Entonces): el resultado esperado. Lo que deberia pasar despues de la accion.
                    Ejemplo: "el carrito contiene 1 producto".

And conecta pasos del mismo tipo: "When X / And Y" significa "When X y tambien Y".

Como conecta pytest-bdd este archivo con carrito.feature
---------------------------------------------------------
El archivo carrito.feature (en tests/features/) contiene los escenarios escritos
en lenguaje Gherkin. Este archivo Python contiene las "step definitions": funciones
que implementan cada paso (Given/When/Then) del feature file.

La conexion se hace en dos partes:

1. scenarios("carrito.feature") al inicio registra TODOS los escenarios del
   feature file como tests de pytest. Si el feature tiene 12 escenarios, pytest
   descubrira 12 tests en este archivo.

2. Los decoradores @given, @when, @then registran funciones como implementaciones
   de los pasos. El texto en el decorador debe coincidir EXACTAMENTE (o via
   expresiones del parser) con el texto en el feature file.

Que son los step definitions y como funciona el matching
---------------------------------------------------------
Cuando pytest-bdd ejecuta el escenario "Agregar un producto al carrito vacio",
corre los pasos en orden:
  1. Busca una funcion decorada con @given("un carrito de compras vacio") → carrito_vacio
  2. Ejecuta carrito_vacio() → devuelve el carrito
  3. Busca una funcion decorada con @when que coincida con "agrego el producto..."
     → agregar_producto (usando parsers.parse para extraer nombre, precio, cantidad)
  4. Ejecuta agregar_producto(carrito, "Laptop", 2500000, 1)
  5. Busca @then("el carrito contiene 1 producto") → verificar_cantidad_productos
  6. Ejecuta verificar_cantidad_productos(carrito, 1)

Por que los fixtures de BDD usan target_fixture
------------------------------------------------
En pytest normal, un fixture retorna un valor y otro fixture/test lo recibe
por coincidencia de nombre en el parametro. En BDD, los pasos Given/When/Then
no son fixtures convencionales, pero algunos necesitan crear un objeto y pasarlo
a los pasos siguientes del mismo escenario.

target_fixture="carrito" en un @given significa: "el valor que retorna esta
funcion debe estar disponible como si fuera un fixture llamado 'carrito' para
los pasos siguientes de este escenario".

    @given("un carrito de compras vacio", target_fixture="carrito")
    def carrito_vacio():
        return Carrito()  # el Carrito queda disponible como 'carrito'

    @when(parsers.parse('agrego el producto "{nombre}"...'))
    def agregar_producto(carrito, nombre, ...):  # recibe el 'carrito' del Given
        carrito.agregar_producto(...)

El fixture 'carrito' fluye automaticamente de Given a When a Then dentro del
mismo escenario, sin necesidad de variables globales ni de clase.
"""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.carrito.carrito import Carrito

# ──────────────────────────────────────────────────────
# Registrar todos los escenarios del feature file
# ──────────────────────────────────────────────────────

# scenarios() le dice a pytest-bdd que busque carrito.feature en el directorio
# base definido en pyproject.toml (bdd_features_base_dir = "tests/features/")
# y registre cada Scenario y Scenario Outline como un test de pytest.
scenarios("carrito.feature")


# ──────────────────────────────────────────────────────
# GIVEN: Precondiciones — el estado inicial del sistema
# ──────────────────────────────────────────────────────


@given("un carrito de compras vacío", target_fixture="carrito")
def carrito_vacio():
    """
    Crea un carrito nuevo y vacio.

    Este paso implementa el Background del feature file: todos los escenarios
    que no especifican otro Given usan este como punto de partida.
    target_fixture="carrito" hace que el Carrito retornado quede disponible
    como parametro 'carrito' para los pasos When y Then del mismo escenario.
    """
    return Carrito()


@given(
    parsers.parse(
        'el carrito tiene el producto "{nombre}" con precio {precio:d} y cantidad {cantidad:d}'
    ),
    target_fixture="carrito",
)
def carrito_con_producto(carrito, nombre, precio, cantidad):
    """
    Agrega un producto al carrito como precondicion.

    parsers.parse extrae los valores del texto del paso. El formato {nombre}
    captura cualquier string entre comillas. El formato {precio:d} captura
    un entero. Si el feature dice 'precio 2500000', precio valdra 2500000 (int).

    Este paso TAMBIEN usa target_fixture="carrito" y retorna el carrito modificado.
    Si el escenario tiene dos Given de este tipo (dos productos como precondicion),
    el segundo recibe el carrito del primero como parametro y lo retorna con ambos
    productos. La cadena de target_fixture mantiene el estado entre pasos Given.
    """
    carrito.agregar_producto(nombre=nombre, precio=precio, cantidad=cantidad)
    return carrito


@given("un carrito con stock disponible:", target_fixture="contexto")
def carrito_con_stock(datatable):
    """
    Crea un carrito con stock limitado usando una tabla de datos del feature.

    Las tablas de datos (datatables) en Gherkin son tablas Markdown en el feature:

        Given un carrito con stock disponible:
          | producto | stock |
          | Laptop   | 2     |

    pytest-bdd las convierte en una lista de listas. La primera lista es la
    fila de cabeceras: ["producto", "stock"]. Las siguientes son filas de datos.

    Este paso retorna un diccionario 'contexto' en vez de solo 'carrito' porque
    el escenario de stock tambien necesita capturar el error que ocurre cuando
    se supera el stock. El contexto lleva el carrito Y el posible error.
    """
    # datatable[0] es la fila de cabeceras: ["producto", "stock"]
    headers = datatable[0]
    stock = {}
    # datatable[1:] son las filas de datos, una por producto
    for row in datatable[1:]:
        fila = dict(zip(headers, row))
        stock[fila["producto"]] = int(fila["stock"])

    return {"error": None, "carrito": Carrito(stock_disponible=stock)}


# ──────────────────────────────────────────────────────
# WHEN: Acciones — lo que el usuario o sistema hace
# ──────────────────────────────────────────────────────


@when(parsers.parse('agrego el producto "{nombre}" con precio {precio:d} y cantidad {cantidad:d}'))
def agregar_producto(carrito, nombre, precio, cantidad):
    """
    Ejecuta la accion de agregar un producto al carrito.

    El parametro 'carrito' no viene de ninguna importacion: pytest-bdd lo
    inyecta automaticamente porque un paso Given anterior lo definio como
    target_fixture="carrito". Es el mismo mecanismo de inyeccion de pytest.
    """
    carrito.agregar_producto(nombre=nombre, precio=precio, cantidad=cantidad)


@when(parsers.parse('elimino el producto "{nombre}"'))
def eliminar_producto(carrito, nombre):
    """Ejecuta la accion de eliminar un producto."""
    carrito.eliminar_producto(nombre)


@when(parsers.parse('aplico un descuento de tipo "{tipo}" con valor {valor:d}'))
def aplicar_descuento(carrito, tipo, valor):
    """Aplica un descuento al carrito."""
    carrito.aplicar_descuento(tipo=tipo, valor=valor)


@when(parsers.parse('intento agregar "{nombre}" con precio {precio:d} y cantidad {cantidad:d}'))
def intentar_agregar_producto(contexto, nombre, precio, cantidad):
    """
    Intenta agregar un producto, capturando el error si ocurre.

    Nota el parametro 'contexto' en vez de 'carrito': este paso corresponde
    al escenario de stock, donde el Given creo un 'contexto' (no un 'carrito').
    pytest-bdd inyecta el fixture que coincide con el nombre del parametro.

    Se usa un try/except en vez de pytest.raises porque en BDD el error es
    parte del flujo narrativo, no una excepcion tecnica del test. El Then
    posterior verificara que el error ocurrio con el texto correcto.
    """
    try:
        contexto["carrito"].agregar_producto(nombre=nombre, precio=precio, cantidad=cantidad)
    except ValueError as e:
        contexto["error"] = str(e)


@when("vacío el carrito")
def vaciar_carrito(carrito):
    """Vacia completamente el carrito."""
    carrito.vaciar()


# ──────────────────────────────────────────────────────
# THEN: Verificaciones — el resultado esperado
# ──────────────────────────────────────────────────────


@then(parsers.parse("el carrito contiene {cantidad:d} producto"))
@then(parsers.parse("el carrito contiene {cantidad:d} productos"))
def verificar_cantidad_productos(carrito, cantidad):
    """
    Verifica cuantos productos distintos hay en el carrito.

    Dos decoradores para manejar singular y plural: "1 producto" vs "2 productos".
    pytest-bdd intentara hacer match con cualquiera de los dos patrones.
    """
    assert carrito.cantidad_productos() == cantidad


@then(parsers.parse('el producto "{nombre}" está en el carrito'))
def verificar_producto_existe(carrito, nombre):
    """Verifica que un producto especifico esta en el carrito."""
    nombres = [p["nombre"] for p in carrito.obtener_productos()]
    assert nombre in nombres


@then(parsers.parse('el producto "{nombre}" tiene cantidad {cantidad:d}'))
def verificar_cantidad_producto(carrito, nombre, cantidad):
    """Verifica la cantidad de un producto especifico."""
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
    """
    Verifica que se produjo un error con el texto esperado.

    El parametro 'contexto' viene del Given 'un carrito con stock disponible'.
    intentar_agregar_producto capturo el ValueError y lo guardo en contexto["error"].
    Este Then verifica que efectivamente ocurrio un error y que el mensaje
    contiene el texto esperado (en este caso, "stock").
    """
    assert contexto["error"] is not None, "Se esperaba un error pero no ocurrio"
    assert texto in contexto["error"], (
        f"Error esperado con '{texto}', pero el error fue: {contexto['error']}"
    )
