import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.carrito.api import app
from src.database.config import get_db
from src.database.models import Base


@pytest.fixture(scope="session")
def postgres_container():
    # Importacion lazy: testcontainers solo se importa si un test de integracion
    # lo necesita. Los tests unitarios/funcionales no necesitan Docker.
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16-alpine") as container:
        yield container


@pytest.fixture(scope="session")
def db_engine(postgres_container):
    url = postgres_container.get_connection_url()
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    # Patron rollback: cada test corre dentro de una transaccion que se revierte
    # al final, dejando la BD limpia para el siguiente test sin necesidad de truncar tablas.
    connection = db_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client_con_bd(db_session):
    # Inyecta la sesion de BD del test en la API via dependency_overrides,
    # asegurando que la API y los asserts del test usen la misma transaccion.
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
