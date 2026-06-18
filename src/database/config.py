"""
Configuracion de la conexion a la base de datos.

Este modulo determina a que BD conectarse segun el entorno y proporciona
la funcion get_db que FastAPI inyecta en cada endpoint como dependencia.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.database.models import Base

# DATABASE_URL se lee de la variable de entorno. Si no esta definida, se usa
# SQLite en memoria como fallback. Este fallback es fundamental para:
#   - Tests rapidos (test_carrito.py, test_funcional.py, security/): corren sin Docker.
#   - Desarrollo local sin querer levantar PostgreSQL.
# En produccion y en los tests de integracion/sistema, DATABASE_URL esta siempre definida.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///:memory:")

# Normalizacion: si alguien configura una URL con el driver async (asyncpg),
# la convertimos al driver sincrono (psycopg2). FastAPI puede usar SQLAlchemy
# sincrono o asincrono; este proyecto usa la version sincrona por simplicidad.
DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

# Configuracion extra que varia segun el motor de BD
_engine_kwargs: dict = {}

if "sqlite" in DATABASE_URL:
    # SQLite en multiples hilos: por defecto SQLite rechaza conexiones usadas
    # desde hilos distintos al que las creo. check_same_thread=False deshabilita
    # esa restriccion. Es seguro en este contexto porque SQLAlchemy gestiona
    # la concurrencia con su propio sistema de locking.
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

    if ":memory:" in DATABASE_URL:
        # StaticPool: por que SQLite en memoria lo necesita
        #
        # Por defecto, SQLAlchemy usa un pool de conexiones: cuando necesita
        # una conexion, abre una nueva o reutiliza una del pool. Con SQLite en
        # memoria, cada conexion nueva obtiene una BASE DE DATOS COMPLETAMENTE
        # NUEVA Y VACIA. No comparte datos con otras conexiones.
        #
        # Esto causaria un problema: get_db abre una sesion (conexion A, BD A),
        # el endpoint inserta en BD A, luego otra parte del codigo abre otra
        # sesion (conexion B, BD B) y no ve nada porque BD B es diferente.
        #
        # StaticPool hace que SQLAlchemy use SIEMPRE la misma conexion
        # subyacente para todas las sesiones. Todas ven la misma BD en memoria.
        # Sin StaticPool, SQLite en memoria es inutilizable para tests con API.
        from sqlalchemy.pool import StaticPool

        _engine_kwargs["poolclass"] = StaticPool

# create_engine no abre conexiones todavia. Solo guarda la configuracion:
# URL, pool, kwargs. Las conexiones se abren cuando se piden por primera vez.
engine = create_engine(DATABASE_URL, **_engine_kwargs)

# sessionmaker es una fabrica de sesiones. SessionLocal() crea una sesion nueva.
# autocommit=False: los cambios no se confirman automaticamente, hay que llamar commit().
# autoflush=False: SQLAlchemy no hace flush automatico antes de cada query.
#   Preferimos controlar explicitamente cuando hacer flush (en el repositorio).
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    """
    Crea todas las tablas definidas en los modelos si no existen.

    Base.metadata contiene la definicion de todas las clases que heredan de Base
    (CarritoDB, ItemCarritoDB). create_all ejecuta el CREATE TABLE IF NOT EXISTS
    correspondiente en la BD conectada.

    En PostgreSQL en produccion, las migraciones se manejan con Alembic.
    Esta funcion se usa para la inicializacion inicial y para los tests.
    """
    Base.metadata.create_all(bind=engine)


# Para SQLite (desarrollo y tests sin Docker), crear tablas al importar el modulo.
# Esto garantiza que las tablas existen antes de que cualquier endpoint procese
# el primer request, sin necesidad de llamar init_db() explicitamente.
#
# Para PostgreSQL, las tablas se crean en el evento on_event("startup") de la API
# (ver src/carrito/api.py) o via migraciones de Alembic. No se crean aqui para
# evitar conectar a PostgreSQL al importar el modulo (PostgreSQL puede no estar
# disponible en el momento del import).
if "sqlite" in DATABASE_URL:
    init_db()


def get_db():
    """
    Generador que proporciona una sesion de BD para cada request HTTP.

    FastAPI llama a esta funcion via Depends(get_db) en cada endpoint.
    Al ser un generador (tiene yield), FastAPI la usa como context manager:
      1. Llama a get_db() → ejecuta hasta el yield → obtiene la sesion.
      2. Pasa la sesion al endpoint como parametro.
      3. El endpoint corre.
      4. Continua la ejecucion de get_db() despues del yield.

    El patron try/yield/except/finally garantiza que:
      - Si el endpoint termina sin errores: se confirman los cambios (commit).
      - Si el endpoint lanza una excepcion: se revierten los cambios (rollback)
        y la excepcion se propaga para que FastAPI la maneje (convertir en 500).
      - En cualquier caso (exito o error): la sesion se cierra (finally).

    Por que yield en vez de return:
    Una funcion con return cierra su scope al retornar. Una funcion con yield
    (generador) puede reanudar su ejecucion despues de que el consumidor
    termina. FastAPI usa este patron para ejecutar teardown despues del endpoint.

    Diferencia entre flush() y commit():
    - flush(): envia el SQL al motor de BD dentro de la transaccion activa.
      Los datos son visibles para queries posteriores en la MISMA sesion.
      La transaccion sigue abierta. Si hay un error mas adelante, se puede
      hacer rollback y deshacer todo.
    - commit(): confirma la transaccion definitivamente. Los datos son
      permanentes y visibles para CUALQUIER conexion externa a la BD.
      No hay vuelta atras sin un nuevo INSERT/UPDATE.

    El repositorio usa flush() porque no decide cuando confirmar: esa
    decision la toma get_db() al final del request.
    """
    db: Session = SessionLocal()
    try:
        yield db
        # Si llegamos aqui, el endpoint termino sin excepciones → confirmar
        db.commit()
    except Exception:
        # Algo salio mal en el endpoint → deshacer todos los cambios del request
        db.rollback()
        raise  # Re-lanzar la excepcion para que FastAPI la convierta en respuesta HTTP
    finally:
        # Siempre cerrar la sesion, independientemente de exito o error.
        # Cierra la conexion al pool para que pueda ser reutilizada.
        db.close()
