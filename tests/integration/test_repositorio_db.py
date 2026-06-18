"""
Tests de integracion para CarritoRepositorio contra PostgreSQL real.

Que son las pruebas de integracion y en que se diferencian de las unitarias
----------------------------------------------------------------------------
Las pruebas unitarias (test_carrito.py) verifican que la logica de negocio
funciona en memoria, sin ninguna infraestructura externa. Son rapidas y
aisladas porque no tienen dependencias.

Las pruebas de integracion verifican que DOS O MAS componentes funcionan
JUNTOS correctamente. En este archivo: el repositorio Python + PostgreSQL real.
La pregunta que responden no es "la logica de calculo de totales esta bien"
sino "cuando ejecuto esa logica contra una base de datos real, los datos se
persisten, se leen y se manipulan correctamente".

Por que testear el repositorio directamente (sin HTTP)
------------------------------------------------------
El repositorio (CarritoRepositorio) es la capa de datos: la unica que habla
con la BD. Testear el repositorio directamente tiene dos ventajas:

1. Aislamiento: si un test de repositorio falla, sabemos que el problema esta
   en la capa de datos, no en la API ni en el routing de FastAPI.

2. Granularidad: podemos insertar objetos directamente en la sesion de BD,
   leerlos con queries SQL directos, y verificar exactamente lo que se guardo.

Los tests en test_api_integracion.py prueban la capa superior (API + repositorio
+ BD). Estos tests prueban solo la capa de repositorio + BD.

Como funciona TestContainers: Docker se levanta desde el codigo
---------------------------------------------------------------
TestContainers es una libreria que controla Docker desde Python. Cuando pytest
carga el conftest.py y algun test pide el fixture db_session, la cadena de
dependencias llega hasta postgres_container, que ejecuta:

    docker run -d -p XXXX:5432 postgres:16-alpine

El puerto XXXX es aleatorio, asignado por Docker para evitar conflictos.
TestContainers espera hasta que PostgreSQL acepte conexiones (healthcheck
interno) y luego retorna la URL de conexion con el puerto asignado.

Este mecanismo funciona en GitHub Actions porque los runners de ubuntu-latest
tienen el daemon de Docker disponible. El runner puede ejecutar contenedores
de la misma forma que lo hace en una maquina local.

Por que el rollback pattern es mejor que truncar tablas
-------------------------------------------------------
Para que cada test encuentre la BD limpia, hay dos enfoques:

Enfoque 1 — TRUNCATE entre tests:
  - Ejecutar DELETE FROM items_carrito; DELETE FROM carritos; entre tests.
  - Problema: son operaciones de escritura reales, con I/O al disco.
  - Problema: si el test falla a la mitad, puede quedar estado inconsistente.

Enfoque 2 — Rollback pattern (el que usa este proyecto):
  - Cada test corre dentro de una transaccion abierta.
  - Al terminar el test (pase o falle), la transaccion se revierte.
  - Las operaciones se hacen en memoria del motor de BD, sin I/O de confirmacion.
  - El rollback es atomico: deshace absolutamente todo, sin excepciones.

El rollback pattern es mas rapido y mas seguro. Ver conftest.py, fixture
db_session, para la implementacion exacta.

Como el fixture db_session les llega (cadena desde conftest.py)
---------------------------------------------------------------
Estos tests declaran db_session como parametro. pytest busca en conftest.py
(en esta carpeta y en las carpetas padre) un fixture con ese nombre. Lo
encuentra en tests/conftest.py. Ese fixture depende de db_engine, que depende
de postgres_container. pytest construye el arbol de dependencias y los
instancia de abajo hacia arriba.

El desarrollador de este archivo no necesita saber como se creo db_session.
Solo necesita saber que cuando lo declara como parametro, recibe una sesion
SQLAlchemy lista para usar contra PostgreSQL real, dentro de una transaccion
que se va a revertir al terminar el test.
"""

import pytest
from sqlalchemy import func

from src.database.models import CarritoDB, ItemCarritoDB
from src.database.repositorio import CarritoRepositorio


@pytest.mark.integration
class TestCarritoRepositorioIntegracion:
    """
    Tests de integracion para CarritoRepositorio.

    La marca @pytest.mark.integration permite ejecutar solo este grupo:
        uv run pytest tests/integration/ -m integration

    Todos los metodos reciben db_session como parametro. Es el mismo fixture
    para todos, pero cada metodo tiene SU PROPIA instancia (scope=function),
    con su propia transaccion y su propio rollback. Los tests son independientes.
    """

    def test_crear_carrito_nuevo_en_bd(self, db_session):
        """
        Verifica que obtener_o_crear inserta una fila en la tabla carritos.

        Despues de llamar al repositorio, se hace una query SQL directa para
        contar cuantas filas hay en carritos. Esto verifica que el flush()
        del repositorio envio el INSERT a la BD y que la sesion puede leerlo.
        """
        repo = CarritoRepositorio(db_session)
        carrito = repo.obtener_o_crear("int-1")

        # El carrito debe tener un ID asignado por la BD (no None)
        assert carrito.id is not None
        assert carrito.sesion_id == "int-1"
        # Query directa a la BD via la misma sesion del test
        count = db_session.query(func.count(CarritoDB.id)).scalar()
        assert count == 1

    def test_obtener_carrito_existente_no_duplica(self, db_session):
        """
        Verifica que obtener_o_crear es idempotente: llamarlo dos veces con el
        mismo sesion_id no crea dos carritos, solo retorna el existente.
        """
        repo = CarritoRepositorio(db_session)
        repo.obtener_o_crear("int-dup")
        repo.obtener_o_crear("int-dup")  # segunda llamada, no debe insertar

        count = (
            db_session.query(func.count(CarritoDB.id))
            .filter(CarritoDB.sesion_id == "int-dup")
            .scalar()
        )
        assert count == 1

    def test_agregar_item_persiste_en_bd(self, db_session):
        """
        Verifica que agregar_item crea una fila en items_carrito.

        item.id is not None confirma que la BD asigno un ID autoincremental,
        lo que significa que el INSERT fue procesado exitosamente (flush).
        """
        repo = CarritoRepositorio(db_session)
        item = repo.agregar_item("int-3", "Laptop", 2_500_000, 1)

        assert item.id is not None
        # Leer el carrito de la BD y verificar que tiene el item
        carrito = repo.obtener_o_crear("int-3")
        assert len(carrito.items) == 1

    def test_agregar_item_existente_suma_cantidad(self, db_session):
        """
        Verifica que agregar el mismo producto dos veces actualiza la cantidad
        en vez de crear una fila duplicada en items_carrito.

        El query JOIN verifica directamente en la BD que hay exactamente 1 fila
        para ese producto, y que esa fila tiene la cantidad sumada (1 + 3 = 4).
        """
        repo = CarritoRepositorio(db_session)
        repo.agregar_item("int-4", "Laptop", 2_500_000, 1)
        repo.agregar_item("int-4", "Laptop", 2_500_000, 3)

        # Debe haber una sola fila en items_carrito para este carrito
        count = (
            db_session.query(func.count(ItemCarritoDB.id))
            .join(CarritoDB)
            .filter(CarritoDB.sesion_id == "int-4")
            .scalar()
        )
        assert count == 1
        # Y esa fila debe tener la cantidad sumada
        item = (
            db_session.query(ItemCarritoDB)
            .join(CarritoDB)
            .filter(CarritoDB.sesion_id == "int-4")
            .first()
        )
        assert item.cantidad == 4

    def test_calcular_total_con_items_en_bd(self, db_session):
        """
        Verifica que calcular_total lee los items de la BD y suma correctamente.
        Laptop x1 = $2.5M, Mouse x2 = $170k, total = $2.67M.
        """
        repo = CarritoRepositorio(db_session)
        repo.agregar_item("int-5", "Laptop", 2_500_000, 1)
        repo.agregar_item("int-5", "Mouse", 85_000, 2)

        assert repo.calcular_total("int-5") == 2_670_000

    def test_descuento_persiste_en_bd(self, db_session):
        """
        Verifica que aplicar_descuento guarda descuento_tipo y descuento_valor
        en la fila de la tabla carritos.

        Despues de aplicar el descuento, se lee el carrito directamente de la BD
        y se verifican las columnas. Esto confirma que el UPDATE llego a la BD
        (via flush), no solo que la logica del repositorio lo calcula bien.
        """
        repo = CarritoRepositorio(db_session)
        repo.agregar_item("int-6", "Laptop", 1_000_000, 1)
        repo.aplicar_descuento("int-6", "porcentaje", 10)

        # Leer la fila del carrito directamente de la BD
        carrito = repo.obtener_o_crear("int-6")
        assert carrito.descuento_tipo == "porcentaje"
        assert carrito.descuento_valor == 10.0
        # Ademas verificar que el calculo del total usa el descuento
        assert repo.calcular_total("int-6") == pytest.approx(900_000)

    def test_vaciar_carrito_elimina_items_de_bd(self, db_session):
        """
        Verifica que vaciar() elimina los items pero deja el carrito en pie.

        La fila en carritos permanece (el carrito sigue existiendo, solo vacio).
        Los items son eliminados. La relacion cascade="all, delete-orphan" en
        el modelo se encarga de la eliminacion fisica cuando se llama items.clear().
        """
        repo = CarritoRepositorio(db_session)
        repo.agregar_item("int-7", "Laptop", 2_500_000, 1)
        repo.vaciar("int-7")

        carrito = repo.obtener_o_crear("int-7")
        assert len(carrito.items) == 0
        # El carrito sigue existiendo en la BD (no fue borrado)
        assert carrito.id is not None

    def test_precio_invalido_no_se_guarda(self, db_session):
        """
        Verifica que una validacion fallida en el repositorio no deja datos
        parciales en la BD.

        El repositorio valida precio > 0 antes de hacer cualquier INSERT.
        Si lanza ValueError, no se ejecuta ningun INSERT. La BD queda limpia.
        El count final confirma que la BD esta en estado integro.
        """
        repo = CarritoRepositorio(db_session)

        with pytest.raises(ValueError):
            repo.agregar_item("int-8", "Laptop", -100, 1)

        # Despues del error, no debe haber ninguna fila en items_carrito
        count = (
            db_session.query(func.count(ItemCarritoDB.id))
            .join(CarritoDB)
            .filter(CarritoDB.sesion_id == "int-8")
            .scalar()
        )
        assert count == 0

    def test_total_carrito_inexistente_es_cero(self, db_session):
        """
        Verifica que calcular_total maneja graciosamente el caso de un
        sesion_id que no existe en la BD: retorna 0.0 en vez de lanzar excepcion.

        La API usa este comportamiento para el endpoint GET /carrito/{sesion_id}:
        si el carrito no existe, no falla con 404 sino que retorna estado vacio.
        """
        repo = CarritoRepositorio(db_session)
        assert repo.calcular_total("sesion-que-no-existe") == 0.0

    def test_rollback_en_error_no_corrompe_estado(self, db_session):
        """
        Verifica que un error en el segundo agregar_item no afecta al primero.

        Este test verifica la atomicidad a nivel de operacion individual del
        repositorio. El primer agregar_item hace flush exitoso (Laptop guardado).
        El segundo agregar_item con precio negativo lanza ValueError antes del
        flush. El Laptop sigue en la BD intacto.

        Nota: el rollback que garantiza el aislamiento ENTRE TESTS es el del
        fixture db_session (en conftest.py). El rollback que este test verifica
        es el comportamiento de la sesion SQLAlchemy ante un error en una
        operacion individual del repositorio.
        """
        repo = CarritoRepositorio(db_session)
        repo.agregar_item("int-10", "Laptop", 2_500_000, 1)

        with pytest.raises(ValueError):
            repo.agregar_item("int-10", "Mouse", -999, 1)

        # El Laptop insertado antes del error debe seguir en la BD
        carrito = repo.obtener_o_crear("int-10")
        assert len(carrito.items) == 1
        assert carrito.items[0].nombre == "Laptop"
