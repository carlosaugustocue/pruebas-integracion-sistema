"""
Tests de sistema end-to-end.

Que son las pruebas de sistema y donde estan en la piramide de pruebas
-----------------------------------------------------------------------
Las pruebas de sistema (o E2E, end-to-end) verifican el sistema completo
desde el exterior, tal como lo haria un usuario o cliente real. Estan en
la cima de la piramide de pruebas:

  - Pruebas unitarias (base): rapidas, muchas, aisladas, sin infraestructura.
  - Pruebas de integracion (medio): BD real, pero en proceso controlado.
  - Pruebas de sistema (cima): el sistema completo desplegado, accedido por red.

Las pruebas de sistema son las mas lentas y costosas de mantener, pero son
las que mas se parecen a como el sistema funciona en produccion. Su valor
es verificar que el despliegue completo funciona, no solo que el codigo es correcto.

Por que usan httpx.Client real (con red TCP real)
-------------------------------------------------
httpx.Client abre conexiones TCP reales hacia la URL especificada. Cuando el
test hace cliente_http.get("/carrito/health-check"), ocurre:
  1. DNS o IP directa resuelve localhost:8000 (o el puerto configurado).
  2. Se abre un socket TCP.
  3. Se serializa el HTTP request y se envia por el socket.
  4. Se espera la respuesta HTTP del servidor.
  5. Se deserializa la respuesta.

Esto es exactamente lo mismo que hace un browser o un cliente de produccion.
No hay shortcuts, no hay ASGI directo en memoria.

Por que necesitan la API corriendo externamente
----------------------------------------------
A diferencia de los tests de integracion (que usan TestClient en proceso),
estos tests no tienen acceso al proceso de la API. No pueden inyectar la
sesion de BD, no pueden hacer dependency_overrides, no pueden ver el estado
interno del servidor.

La API debe estar corriendo como un proceso separado, escuchando en un puerto
de red. Para los tests de CI, se usa docker-compose.test.yml que levanta
PostgreSQL + la API en el puerto 8001.

Por que se usan UUIDs para los sesion_id
-----------------------------------------
Cada test genera un sesion_id unico:

    def sesion_unica() -> str:
        return f"e2e-{uuid.uuid4().hex[:8]}"

Si todos los tests usaran el mismo sesion_id (por ejemplo, "test-session"),
los datos de un test contaminarian a los otros. Como la BD del sistema de
tests persiste entre requests (no hay rollback como en los tests de integracion),
cada test debe crear su propio carrito en su propia sesion unica.

El prefijo "e2e-" facilita identificar en la BD los datos creados por estos
tests (vs datos de prueba manuales o datos de otros tests).

Como ejecutar estos tests localmente
--------------------------------------
Con el stack de desarrollo (API en puerto 8000):

    docker compose up -d
    # Esperar que la API responda
    curl http://localhost:8000/carrito/health-check
    # Correr los tests
    API_URL=http://localhost:8000 uv run pytest tests/system/ -v -m system
    docker compose down

Con el stack de tests (API en puerto 8001, BD en RAM):

    docker compose -f docker-compose.test.yml up -d --build
    API_URL=http://localhost:8001 uv run pytest tests/system/ -v -m system
    docker compose -f docker-compose.test.yml down -v

Si API_URL no esta definida, los tests intentan conectar a localhost:8000.

Diferencia vs los tests de integracion: proceso separado, sin acceso interno a BD
----------------------------------------------------------------------------------
Tests de integracion (test_api_integracion.py):
  - TestClient: llamada ASGI en memoria, sin red.
  - db_session: misma sesion del test, mismo proceso.
  - Pueden verificar directamente en la BD lo que guardo la API.
  - No necesitan Docker (TestContainers lo maneja).

Tests de sistema (este archivo):
  - httpx.Client: conexion TCP real, proceso separado.
  - Sin acceso a la sesion de BD de la API.
  - Solo pueden verificar lo que la API retorna en sus respuestas HTTP.
  - Necesitan la API corriendo externamente (docker compose).

La frontera es: si puedes meter la mano dentro del proceso de la API, son
tests de integracion. Si solo puedes hablarle por HTTP, son tests de sistema.
"""

import os
import time
import uuid

import httpx
import pytest

# La URL de la API viene de la variable de entorno API_URL.
# El pipeline de CI la define como http://localhost:8001 (stack de test).
# En desarrollo local se puede definir manualmente o usar el valor por defecto.
API_URL = os.getenv("API_URL", "http://localhost:8000")


@pytest.fixture(scope="module")
def cliente_http():
    """
    Cliente HTTP compartido para todos los tests del modulo.

    scope="module" significa que el cliente se crea una vez para todos los
    tests del archivo y se cierra al terminar el archivo. Esto reutiliza la
    conexion TCP subyacente (connection pooling de httpx), lo que es mas
    eficiente que abrir y cerrar una conexion por test.

    timeout=10.0 es un timeout generoso para dar tiempo a la API a responder.
    En un sistema local saludable, las respuestas llegan en < 100ms. El timeout
    de 10 segundos es para dar margen en CI con recursos limitados.
    """
    with httpx.Client(base_url=API_URL, timeout=10.0) as client:
        yield client


def sesion_unica() -> str:
    """
    Genera un sesion_id unico para que cada test use su propio carrito.

    uuid4() genera un UUID aleatorio de 128 bits. Tomamos los primeros 8
    caracteres hexadecimales (32 bits) que dan 4 millardos de combinaciones
    posibles. Suficiente para que dos tests no colisionen en una misma ejecucion.
    Ejemplo de resultado: "e2e-a3f9b2c1"
    """
    return f"e2e-{uuid.uuid4().hex[:8]}"


@pytest.mark.system
def test_health_check_sistema(cliente_http):
    """
    Verifica que el servidor esta respondiendo.

    Este es el test mas basico posible: un GET a /health-check. Si este test
    falla, el servidor no esta corriendo o no es accesible. Todos los demas
    tests de sistema tambien fallarian. Es el "smoke test" de la suite E2E.

    En el pipeline de CI, este endpoint tambien lo usa el bucle de espera
    que verifica cuando la API esta lista antes de correr los tests.
    """
    response = cliente_http.get("/carrito/health-check")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.system
def test_flujo_compra_normal_completo(cliente_http):
    """
    Flujo de compra tipico: agregar dos productos y verificar el total.

    Este test simula lo que haria un usuario real al hacer una compra:
    agregar varios productos al carrito y consultar el total antes de
    proceder al pago.

    El sesion_id unico garantiza que este test no interfiere con otros tests
    que corren en paralelo o que dejaron datos en la BD de sesiones anteriores.
    """
    sesion = sesion_unica()
    cliente_http.post(
        f"/carrito/{sesion}/productos",
        json={"nombre": "Laptop", "precio": 2_500_000, "cantidad": 1},
    )
    cliente_http.post(
        f"/carrito/{sesion}/productos",
        json={"nombre": "Mouse", "precio": 85_000, "cantidad": 2},
    )

    data = cliente_http.get(f"/carrito/{sesion}").json()
    # Laptop x1 = $2.5M, Mouse x2 = $170k, total = $2.67M
    assert data["total"] == pytest.approx(2_670_000)
    assert len(data["productos"]) == 2


@pytest.mark.system
def test_flujo_con_descuento_porcentaje(cliente_http):
    """
    Flujo con cupon de descuento: agregar producto, aplicar descuento, verificar total y total con IVA.

    El total_con_iva = total * 1.19. Con descuento del 15% sobre $1M:
    total = 1_000_000 * 0.85 = 850_000
    total_con_iva = 850_000 * 1.19 = 1_011_500
    """
    sesion = sesion_unica()
    cliente_http.post(
        f"/carrito/{sesion}/productos",
        json={"nombre": "Laptop", "precio": 1_000_000, "cantidad": 1},
    )
    cliente_http.post(
        f"/carrito/{sesion}/descuento",
        json={"tipo": "porcentaje", "valor": 15},
    )

    data = cliente_http.get(f"/carrito/{sesion}").json()
    assert data["total"] == pytest.approx(850_000)
    assert data["total_con_iva"] == pytest.approx(1_011_500)


@pytest.mark.system
def test_sesiones_independientes(cliente_http):
    """
    Verifica que dos carritos de diferentes sesiones son completamente independientes.

    Escenario: usuario A y usuario B agregan productos. Se vacia el carrito de A.
    El carrito de B no debe verse afectado.

    Este test verifica un requerimiento fundamental del sistema: el aislamiento
    por sesion. Sin esto, vaciar el carrito de un usuario podria afectar a otro.
    """
    sesion_a = sesion_unica()
    sesion_b = sesion_unica()

    # Cada usuario agrega su producto
    cliente_http.post(
        f"/carrito/{sesion_a}/productos",
        json={"nombre": "Laptop", "precio": 2_500_000, "cantidad": 1},
    )
    cliente_http.post(
        f"/carrito/{sesion_b}/productos",
        json={"nombre": "Mouse", "precio": 85_000, "cantidad": 1},
    )

    # Se vacia el carrito de A
    cliente_http.delete(f"/carrito/{sesion_a}")

    # A queda vacio, B intacto
    assert cliente_http.get(f"/carrito/{sesion_a}").json()["total"] == 0
    assert cliente_http.get(f"/carrito/{sesion_b}").json()["total"] == pytest.approx(85_000)


@pytest.mark.system
def test_mismo_producto_dos_veces_suma(cliente_http):
    """
    Verifica que agregar el mismo producto dos veces suma la cantidad en vez de crear duplicados.

    Este es un caso de regresion: una implementacion ingenua de agregar producto
    crearia dos filas. La implementacion correcta detecta que el producto ya
    existe y actualiza la cantidad.

    Despues de dos POST de "Laptop" x1 y x2, el GET debe mostrar 1 producto
    con cantidad 3 (no 2 productos con cantidades 1 y 2).
    """
    sesion = sesion_unica()
    cliente_http.post(
        f"/carrito/{sesion}/productos",
        json={"nombre": "Laptop", "precio": 2_500_000, "cantidad": 1},
    )
    cliente_http.post(
        f"/carrito/{sesion}/productos",
        json={"nombre": "Laptop", "precio": 2_500_000, "cantidad": 2},
    )

    data = cliente_http.get(f"/carrito/{sesion}").json()
    assert data["cantidad_productos"] == 1
    assert data["productos"][0]["cantidad"] == 3


@pytest.mark.system
def test_sistema_responde_en_menos_de_500ms(cliente_http):
    """
    Verifica que la API responde en menos de 500ms para una consulta simple.

    Este no es un test de carga (para eso esta Locust). Es un test de sanidad
    del tiempo de respuesta: un GET de un carrito vacio no deberia tardar mas
    de medio segundo en ningun escenario normal.

    Si este test falla, es una senal de alerta de que algo en la infraestructura
    esta mal: la BD responde lenta, hay un query sin indice, hay un timeout de
    conexion al arrancar, etc.

    time.monotonic() es un reloj monotono: no retrocede ni da saltos aunque
    se cambie el reloj del sistema. Es mas adecuado para medir duraciones que
    time.time().
    """
    sesion = sesion_unica()
    inicio = time.monotonic()
    cliente_http.get(f"/carrito/{sesion}")
    tiempo_ms = (time.monotonic() - inicio) * 1000
    assert tiempo_ms < 500, f"Respuesta demoro {tiempo_ms:.1f}ms, limite 500ms"
