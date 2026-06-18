"""
Archivo de configuracion compartida para pytest.

Por que existe este archivo y por que se llama conftest.py
----------------------------------------------------------
pytest busca automaticamente archivos llamados conftest.py en la carpeta donde
estan los tests y en todas las carpetas padre hasta la raiz del proyecto. No
necesitas importarlo ni mencionarlo en ninguna parte: pytest lo encuentra y lo
carga solo antes de empezar a correr los tests.

Todo lo que se defina aqui queda disponible para todos los tests dentro de
tests/ y sus subcarpetas (integration/, system/, security/, features/), sin
necesidad de importar nada.

Que es un fixture
-----------------
Un fixture es una funcion de preparacion que pytest ejecuta antes de un test
para dejarle listo el contexto que necesita. Se define con @pytest.fixture.
La firma:

    @pytest.fixture(scope="session")
    def postgres_container():
        ...setup...
        yield valor   # <-- el test recibe 'valor' como parametro
        ...teardown...

El yield divide el fixture en dos fases:
  - Todo lo que va ANTES del yield: setup (preparacion).
  - El valor que se pone en el yield: lo que el test recibe como parametro.
  - Todo lo que va DESPUES del yield: teardown (limpieza).

El teardown corre siempre, pase o falle el test. Si el test lanza una excepcion,
pytest atrapa el error, ejecuta el teardown de los fixtures y luego reporta el
fallo. Esto garantiza que la BD no queda sucia aunque el test explote.

Los fixtures son lazy
---------------------
Un fixture no se ejecuta hasta que alguien lo pide. pytest registra los fixtures
al leer conftest.py, pero no los instancia. Solo cuando un test declara un
parametro con el mismo nombre, pytest ejecuta el fixture correspondiente.

Consecuencia practica: si corres solo tests/test_carrito.py, ninguno de los
tests en ese archivo tiene parametros llamados db_session ni postgres_container.
pytest lee este conftest.py, registra los fixtures, y nunca los ejecuta. Docker
no se toca. Los tests corren en milisegundos.

Matching por nombre de parametro
---------------------------------
Cuando pytest ve un test como:

    def test_algo(db_session, client_con_bd):
        ...

Lee los nombres de los parametros: 'db_session' y 'client_con_bd'. Busca en
conftest.py y en los plugins instalados si existe un fixture con ese nombre
exacto. Si lo encuentra, lo ejecuta y pasa su resultado como argumento. El
nombre del parametro en el test DEBE ser identico al nombre de la funcion
decorada con @pytest.fixture.

El scope: cuantas veces se instancia cada fixture
-------------------------------------------------
scope="session"  -> una sola instancia para toda la ejecucion de pytest.
                    Todos los tests comparten el mismo objeto.
scope="module"   -> una instancia por archivo de test.
scope="class"    -> una instancia por clase de test.
scope="function" -> una instancia por cada test individual (es el default).

La cadena de dependencias de este conftest
------------------------------------------
Los fixtures dependen unos de otros. Para resolver un test que pide
client_con_bd, pytest construye este arbol y lo ejecuta de abajo hacia arriba:

    client_con_bd (scope=function)
        └── db_session (scope=function)
                └── db_engine (scope=session)
                        └── postgres_container (scope=session)

postgres_container y db_engine se crean una sola vez para toda la sesion.
db_session y client_con_bd se crean y destruyen una vez por cada test.

Por que dependency_overrides
-----------------------------
La API usa get_db() (definida en src/database/config.py) para obtener una sesion
de BD cada vez que recibe un request. Esa funcion crea una sesion nueva desde el
pool de conexiones, hace commit al final y cierra la sesion.

En los tests de integracion, necesitamos que la API use la MISMA sesion que el
test para que el rollback del fixture limpie lo que hizo la API. Si la API usara
su propio get_db, tendria su propia sesion y su propia transaccion, separada de
la del test. El test no podria ver lo que inserto la API (no hay commit) y el
rollback del fixture no limpiaria los datos de la API.

app.dependency_overrides es un diccionario de FastAPI que permite reemplazar
cualquier dependencia Depends(...) con otra funcion durante los tests. Aqui se
reemplaza get_db con override_get_db, que simplemente retorna la sesion del test.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.carrito.api import app
from src.database.config import get_db
from src.database.models import Base


@pytest.fixture(scope="session")
def postgres_container():
    """
    Levanta un contenedor PostgreSQL real usando TestContainers.

    Por que scope="session": levantar un contenedor Docker tarda 2-5 segundos.
    Si cada test levantara su propio contenedor, 16 tests tardarian 30-80 segundos
    solo en setup. Con scope="session", el contenedor se levanta una vez y todos
    los tests lo comparten.

    Por que la importacion esta dentro de la funcion: los tests unitarios y
    funcionales nunca llaman a este fixture. Si importaramos PostgresContainer
    al inicio del archivo, pytest lo importaria al leer conftest.py, incluso
    para tests que jamas usan Docker. Con la importacion lazy, testcontainers
    se importa solo cuando alguien realmente necesita el contenedor.

    Que recibe quien pide este fixture: el objeto PostgresContainer, que tiene
    un metodo get_connection_url() que retorna la URL de conexion con el puerto
    aleatorio que Docker asigno al contenedor.
    """
    # La importacion lazy evita que testcontainers se cargue en tests que no lo necesitan
    from testcontainers.postgres import PostgresContainer

    # El bloque 'with' le dice a TestContainers que levante el contenedor al entrar
    # y lo pare y elimine al salir. El 'yield container' pausa la ejecucion aqui
    # mientras pytest corre todos los tests. Cuando pytest termina la sesion,
    # el bloque 'with' cierra y Docker para el contenedor.
    with PostgresContainer("postgres:16-alpine") as container:
        yield container


@pytest.fixture(scope="session")
def db_engine(postgres_container):
    """
    Crea el motor SQLAlchemy y las tablas en la BD del contenedor.

    Por que scope="session": las tablas se crean una vez y persisten para todos
    los tests. Cada test individual usa el patron rollback para aislar sus datos,
    pero las tablas en si existen durante toda la sesion.

    Por que depende de postgres_container: necesita la URL de conexion que solo
    el contenedor ya levantado puede proporcionar. pytest ve que este fixture
    tiene un parametro llamado postgres_container y lo resuelve automaticamente.

    Que hace create_all: lee la definicion de todas las clases que heredan de
    Base en src/database/models.py y ejecuta los CREATE TABLE correspondientes
    en PostgreSQL. Es el equivalente a correr migraciones de Alembic, pero mas
    simple para el entorno de tests.

    Teardown (despues del yield): drop_all elimina todas las tablas y engine.dispose()
    cierra el pool de conexiones. Limpieza explicitamente antes de que el
    contenedor Docker desaparezca.

    Que recibe quien pide este fixture: el Engine de SQLAlchemy configurado
    contra la PostgreSQL real del contenedor.
    """
    url = postgres_container.get_connection_url()
    # create_engine no abre conexiones todavia; solo guarda la configuracion de como conectarse
    engine = create_engine(url)
    # Aqui si se abre una conexion para ejecutar los CREATE TABLE
    Base.metadata.create_all(engine)
    yield engine
    # Teardown: limpiar tablas y cerrar el pool antes de que el contenedor desaparezca
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    """
    Proporciona una sesion SQLAlchemy aislada para cada test individual.

    El patron rollback
    ------------------
    Este fixture implementa el patron de aislamiento por rollback. En vez de
    truncar tablas entre tests (lo que requiere operaciones de escritura en disco),
    cada test corre dentro de una transaccion que nunca se confirma y se revierte
    al final.

    Mecanica exacta:
    1. Se abre una conexion al motor (al PostgreSQL del contenedor).
    2. Se inicia una transaccion en esa conexion: BEGIN TRANSACTION.
    3. Se crea una sesion SQLAlchemy ATADA a esa conexion especifica.
       Importante: sessionmaker(bind=connection), no bind=engine. Esto garantiza
       que todos los INSERT, UPDATE, DELETE de la sesion van a la misma transaccion.
    4. El yield entrega la sesion al test.
    5. El test corre: puede hacer cualquier cantidad de operaciones de BD.
    6. Teardown: session.close(), transaction.rollback(), connection.close().
       El rollback deshace exactamente todo lo que hizo el test. La BD queda
       como estaba antes del test sin ningun paso adicional.

    Por que scope="function": cada test necesita empezar con la BD limpia.
    Si fuera scope="session", el primer test que inserte datos contamina a
    todos los siguientes. Con scope="function", cada test tiene su propia
    transaccion y su propio rollback.

    Que recibe quien pide este fixture: un objeto Session de SQLAlchemy listo
    para hacer queries, dentro de una transaccion aislada.
    """
    # Patron rollback: abrir conexion, iniciar transaccion, crear sesion sobre esa conexion
    connection = db_engine.connect()
    transaction = connection.begin()
    # La sesion se vincula a la conexion (con su transaccion abierta), no al engine
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    # Teardown: siempre corre, pase o falle el test
    session.close()
    # El rollback deshace absolutamente todo lo que hizo el test: INSERT, UPDATE, DELETE
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client_con_bd(db_session):
    """
    Proporciona un TestClient de FastAPI con la sesion de BD del test inyectada.

    Por que este fixture existe
    ---------------------------
    Los tests de integracion necesitan hacer dos cosas:
    a) Llamar a la API (via HTTP simulado).
    b) Verificar directamente en la BD que los datos se guardaron bien.

    Para que (b) funcione, la API y el test deben usar la MISMA sesion de BD.
    Si la API usara su propio get_db() (que crea una sesion nueva), los datos
    que inserta la API estarian en una transaccion separada. El test buscaria
    en db_session y no encontraria nada, aunque los datos esten en la BD,
    porque no se han confirmado en la transaccion de la API.

    Como funciona dependency_overrides
    ------------------------------------
    FastAPI tiene un mecanismo para reemplazar dependencias en tests. El dict
    app.dependency_overrides mapea la funcion original a su reemplazo.

    Normalmente en un endpoint:
        def agregar_producto(db: Session = Depends(get_db)):
            ...
    FastAPI llama a get_db() para obtener la sesion.

    Con el override:
        app.dependency_overrides[get_db] = override_get_db
    FastAPI llama a override_get_db() en su lugar, que retorna db_session.

    Resultado: la API usa la misma sesion del test. Misma conexion. Misma
    transaccion. Cuando el test hace db_session.query(...), ve exactamente
    lo que inserto la API con flush().

    Sobre TestClient
    ----------------
    TestClient de FastAPI (basado en Starlette) llama a la app ASGI directamente
    en memoria. No abre ninguna conexion de red, no hay socket TCP, no hay puerto.
    Es como llamar a la funcion del endpoint directamente pero con toda la
    maquinaria de FastAPI (validacion Pydantic, manejo de errores, routing, etc.).

    Teardown: app.dependency_overrides.clear() elimina el override para que
    otros tests (o el servidor en produccion) no se vean afectados.

    Que recibe quien pide este fixture: un objeto TestClient configurado para
    llamar a la API, con la BD inyectada de forma que comparte la transaccion
    del test.
    """

    # override_get_db reemplaza a get_db en todos los endpoints de la API
    # para este test. En vez de crear una sesion nueva, retorna la del test.
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    # TestClient como context manager garantiza que el ciclo de vida de la app
    # (startup/shutdown events) se ejecute correctamente
    with TestClient(app) as client:
        yield client
    # Teardown: restaurar la dependencia original para no contaminar otros tests
    app.dependency_overrides.clear()
