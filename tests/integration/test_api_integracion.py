"""
Tests de integracion API + PostgreSQL.

Diferencia entre este archivo y test_repositorio_db.py
-------------------------------------------------------
test_repositorio_db.py prueba la capa de datos directamente: llama al
repositorio, verifica la BD. No hay HTTP, no hay FastAPI.

Este archivo prueba la pila completa desde la perspectiva HTTP:
  request HTTP (via TestClient) → FastAPI → repositorio → PostgreSQL → respuesta

La pregunta que responde no es "la BD guarda los datos" sino "cuando llega
un request HTTP, el sistema completo funciona correctamente: el routing, la
validacion Pydantic, la inyeccion de dependencias y la persistencia en BD".

Por que se usa client_con_bd (TestClient) en vez de httpx
----------------------------------------------------------
httpx.Client es un cliente HTTP real que abre conexiones de red TCP. Para
usarlo, la API tendria que estar corriendo como proceso separado (con uvicorn).
Eso es para los tests de sistema (tests/system/), que verifican el sistema
desplegado.

TestClient de FastAPI/Starlette llama a la app ASGI directamente en memoria,
dentro del mismo proceso Python. No hay socket, no hay TCP, no hay puerto.
Es como llamar a las funciones de FastAPI directamente pero con todo el
pipeline de validacion, routing y manejo de errores activado. Mucho mas
rapido y sin necesidad de levantar un servidor.

Que significa que no hay red real: TestClient llama en memoria
--------------------------------------------------------------
Cuando el test hace client_con_bd.post("/carrito/api-1/productos", ...), esto
ocurre:
  1. TestClient serializa el JSON y construye un objeto Request de ASGI.
  2. Llama a app(scope, receive, send) directamente en la memoria del proceso.
  3. FastAPI procesa el request: valida con Pydantic, ejecuta el endpoint.
  4. El endpoint llama al repositorio con la sesion de BD del test.
  5. El repositorio hace el INSERT con flush().
  6. FastAPI serializa la respuesta y la retorna al TestClient.
  Todo esto ocurre en el mismo hilo, sin ningun salto de red.

Por que client_con_bd y db_session usan la misma transaccion
------------------------------------------------------------
client_con_bd depende de db_session (ver conftest.py). Cuando crea el TestClient,
reemplaza get_db con una funcion que retorna db_session. Resultado:

  La API usa db_session → el test usa db_session → misma conexion → misma transaccion

Sin este override, la API crearia su propia sesion en su propio get_db. El test
buscaria en db_session y no encontraria los datos de la API, porque estarian
en una transaccion separada (y sin commit, no son visibles para otras sesiones).

Cuando un test verifica en db_session vs cuando verifica en la respuesta HTTP
-----------------------------------------------------------------------------
Regla general:
  - Verificar en la RESPUESTA HTTP cuando quieres confirmar que la API retorna
    la informacion correcta al cliente.
  - Verificar en db_session cuando quieres confirmar que los datos se
    persistieron correctamente en la BD, independientemente de lo que retorne la API.

Ejemplo 1 (verifica en BD):
  test_post_producto_persiste_en_bd: hace POST, luego busca directamente en
  db_session. Verifica que el INSERT llego a la BD.

Ejemplo 2 (verifica en respuesta HTTP):
  test_estado_persiste_entre_requests: hace dos POST y un GET, verifica la
  respuesta del GET. No accede a la BD directamente. Verifica la consistencia
  del estado desde la perspectiva del cliente HTTP.

Ejemplo mixto:
  test_vaciar_elimina_todo_de_bd: hace POST y DELETE via API, luego cuenta
  filas en db_session. Combina ambos enfoques para verificar que el DELETE
  HTTP limpia realmente la BD.
"""

import pytest

from src.database.models import CarritoDB, ItemCarritoDB


@pytest.mark.integration
class TestAPIConBaseDeDatos:
    """
    Tests de integracion para la API completa con PostgreSQL real.

    Todos los metodos reciben client_con_bd y/o db_session como parametros.
    pytest resuelve estos nombres buscando fixtures en conftest.py.
    Cada metodo tiene su propia instancia de ambos fixtures (scope=function),
    con su propia transaccion y su propio rollback.
    """

    def test_post_producto_persiste_en_bd(self, client_con_bd, db_session):
        """
        Hace un POST via la API y verifica directamente en la BD que el item fue guardado.

        Este test cruza las capas: actua como un cliente HTTP (POST) y como
        un inspector de BD (db_session.query). Si solo verificara la respuesta HTTP
        no confirmaria que el dato llego a la BD. Si solo verificara la BD no
        probaria el routing y la validacion de FastAPI.
        """
        client_con_bd.post(
            "/carrito/api-1/productos",
            json={"nombre": "Laptop", "precio": 2_500_000, "cantidad": 1},
        )

        # Buscar el item directamente en la BD via la misma sesion del test
        item = (
            db_session.query(ItemCarritoDB)
            .join(CarritoDB)
            .filter(CarritoDB.sesion_id == "api-1")
            .first()
        )
        assert item is not None
        assert item.nombre == "Laptop"

    def test_get_carrito_lee_datos_reales_de_bd(self, client_con_bd, db_session):
        """
        Inserta datos directamente en la BD y verifica que la API los retorna.

        Este es el flujo inverso al test anterior: en vez de hacer POST y buscar
        en BD, se inserta en BD y se verifica via GET. Confirma que el ORM mapea
        correctamente los datos de la BD al JSON de respuesta de la API.

        Insertar directamente en db_session (sin pasar por la API) verifica que
        la API puede leer datos que no creo ella misma, por ejemplo datos
        migrados o insertados por otros procesos.

        db_session.flush() es necesario despues de cada INSERT para que el ID
        autoincremental sea asignado y este disponible para el siguiente INSERT.
        Sin flush, carrito.id seria None y el INSERT del item fallaria por la
        FK carrito_id.
        """
        # Insertar el carrito directamente en la BD (sin HTTP)
        carrito = CarritoDB(sesion_id="api-2")
        db_session.add(carrito)
        db_session.flush()  # Necesario para que la BD asigne carrito.id
        db_session.add(
            ItemCarritoDB(carrito_id=carrito.id, nombre="Monitor", precio=1_500_000, cantidad=1)
        )
        db_session.flush()

        # Ahora hacer el GET via la API y verificar que retorna el dato insertado
        response = client_con_bd.get("/carrito/api-2")
        data = response.json()

        assert response.status_code == 200
        assert len(data["productos"]) == 1
        assert data["productos"][0]["nombre"] == "Monitor"

    def test_estado_persiste_entre_requests(self, client_con_bd):
        """
        Verifica que el estado del carrito persiste entre requests HTTP separados.

        Sin DB, cada request al TestClient crearia un estado efimero que
        desapareceria al terminar el request. Con la BD, el primer POST inserta
        el Laptop, el segundo POST inserta el Mouse, y el GET ve ambos.

        Este test no necesita db_session porque solo verifica la respuesta HTTP.
        La persistencia ya esta garantizada por el hecho de que usa PostgreSQL
        real (no SQLite en memoria por request).
        """
        client_con_bd.post(
            "/carrito/api-3/productos",
            json={"nombre": "Laptop", "precio": 2_500_000, "cantidad": 1},
        )
        client_con_bd.post(
            "/carrito/api-3/productos",
            json={"nombre": "Mouse", "precio": 85_000, "cantidad": 2},
        )

        data = client_con_bd.get("/carrito/api-3").json()
        assert len(data["productos"]) == 2

    def test_descuento_persiste_y_afecta_total(self, client_con_bd):
        """
        Verifica el flujo completo: agregar producto, aplicar descuento, consultar total.

        Tres requests HTTP: POST producto, POST descuento, GET carrito.
        Cada request es procesado por la API con la misma sesion del test.
        El descuento se guarda en la tabla carritos. El GET los lee y calcula.
        """
        client_con_bd.post(
            "/carrito/api-4/productos",
            json={"nombre": "Laptop", "precio": 1_000_000, "cantidad": 1},
        )
        client_con_bd.post(
            "/carrito/api-4/descuento",
            json={"tipo": "porcentaje", "valor": 10},
        )

        # pytest.approx maneja posibles imprecisiones de punto flotante en el calculo
        assert client_con_bd.get("/carrito/api-4").json()["total"] == pytest.approx(900_000)

    def test_vaciar_elimina_todo_de_bd(self, client_con_bd, db_session):
        """
        Verifica que DELETE /carrito/{id} limpia los items en la BD.

        Despues del DELETE via API, se cuenta directamente en la BD cuantos
        items quedan. El count debe ser 0. Esto confirma que la operacion de
        vaciar no solo retorna el mensaje correcto sino que efectivamente
        ejecuta los DELETE en la BD.
        """
        client_con_bd.post(
            "/carrito/api-5/productos",
            json={"nombre": "Laptop", "precio": 2_500_000, "cantidad": 1},
        )
        client_con_bd.delete("/carrito/api-5")

        count = (
            db_session.query(ItemCarritoDB)
            .join(CarritoDB)
            .filter(CarritoDB.sesion_id == "api-5")
            .count()
        )
        assert count == 0

    def test_estructura_respuesta_es_correcta(self, client_con_bd):
        """
        Verifica que el GET de un carrito nuevo retorna todos los campos requeridos
        con los tipos y valores correctos.

        Este test actua como contrato de la API: si alguien cambia la estructura
        de la respuesta (renombra un campo, elimina uno), este test falla y alerta.
        Es especialmente util para detectar cambios involuntarios que romperian
        a los clientes de la API (frontend, otros servicios).

        Un carrito nuevo tiene: lista vacia de productos, totales en 0, y el
        sesion_id correcto. El test verifica tanto la presencia de los campos
        como sus valores iniciales.
        """
        data = client_con_bd.get("/carrito/api-6-nuevo").json()

        assert "sesion_id" in data
        assert "productos" in data
        assert isinstance(data["productos"], list)
        assert "total" in data
        assert "total_con_iva" in data
        assert "cantidad_productos" in data
        assert data["total"] == 0
        assert data["cantidad_productos"] == 0
