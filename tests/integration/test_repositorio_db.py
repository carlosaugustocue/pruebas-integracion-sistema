"""
Tests de integracion para CarritoRepositorio contra PostgreSQL real.
Usan el fixture db_session del conftest con rollback automatico por test.
"""

import pytest
from sqlalchemy import func

from src.database.models import CarritoDB, ItemCarritoDB
from src.database.repositorio import CarritoRepositorio


@pytest.mark.integration
class TestCarritoRepositorioIntegracion:
    def test_crear_carrito_nuevo_en_bd(self, db_session):
        repo = CarritoRepositorio(db_session)
        carrito = repo.obtener_o_crear("int-1")

        assert carrito.id is not None
        assert carrito.sesion_id == "int-1"
        count = db_session.query(func.count(CarritoDB.id)).scalar()
        assert count == 1

    def test_obtener_carrito_existente_no_duplica(self, db_session):
        repo = CarritoRepositorio(db_session)
        repo.obtener_o_crear("int-dup")
        repo.obtener_o_crear("int-dup")

        count = (
            db_session.query(func.count(CarritoDB.id))
            .filter(CarritoDB.sesion_id == "int-dup")
            .scalar()
        )
        assert count == 1

    def test_agregar_item_persiste_en_bd(self, db_session):
        repo = CarritoRepositorio(db_session)
        item = repo.agregar_item("int-3", "Laptop", 2_500_000, 1)

        assert item.id is not None
        carrito = repo.obtener_o_crear("int-3")
        assert len(carrito.items) == 1

    def test_agregar_item_existente_suma_cantidad(self, db_session):
        repo = CarritoRepositorio(db_session)
        repo.agregar_item("int-4", "Laptop", 2_500_000, 1)
        repo.agregar_item("int-4", "Laptop", 2_500_000, 3)

        count = (
            db_session.query(func.count(ItemCarritoDB.id))
            .join(CarritoDB)
            .filter(CarritoDB.sesion_id == "int-4")
            .scalar()
        )
        assert count == 1
        item = (
            db_session.query(ItemCarritoDB)
            .join(CarritoDB)
            .filter(CarritoDB.sesion_id == "int-4")
            .first()
        )
        assert item.cantidad == 4

    def test_calcular_total_con_items_en_bd(self, db_session):
        repo = CarritoRepositorio(db_session)
        repo.agregar_item("int-5", "Laptop", 2_500_000, 1)
        repo.agregar_item("int-5", "Mouse", 85_000, 2)

        assert repo.calcular_total("int-5") == 2_670_000

    def test_descuento_persiste_en_bd(self, db_session):
        repo = CarritoRepositorio(db_session)
        repo.agregar_item("int-6", "Laptop", 1_000_000, 1)
        repo.aplicar_descuento("int-6", "porcentaje", 10)

        carrito = repo.obtener_o_crear("int-6")
        assert carrito.descuento_tipo == "porcentaje"
        assert carrito.descuento_valor == 10.0
        assert repo.calcular_total("int-6") == pytest.approx(900_000)

    def test_vaciar_carrito_elimina_items_de_bd(self, db_session):
        repo = CarritoRepositorio(db_session)
        repo.agregar_item("int-7", "Laptop", 2_500_000, 1)
        repo.vaciar("int-7")

        carrito = repo.obtener_o_crear("int-7")
        assert len(carrito.items) == 0
        assert carrito.id is not None

    def test_precio_invalido_no_se_guarda(self, db_session):
        repo = CarritoRepositorio(db_session)

        with pytest.raises(ValueError):
            repo.agregar_item("int-8", "Laptop", -100, 1)

        count = (
            db_session.query(func.count(ItemCarritoDB.id))
            .join(CarritoDB)
            .filter(CarritoDB.sesion_id == "int-8")
            .scalar()
        )
        assert count == 0

    def test_total_carrito_inexistente_es_cero(self, db_session):
        repo = CarritoRepositorio(db_session)
        assert repo.calcular_total("sesion-que-no-existe") == 0.0

    def test_rollback_en_error_no_corrompe_estado(self, db_session):
        repo = CarritoRepositorio(db_session)
        repo.agregar_item("int-10", "Laptop", 2_500_000, 1)

        with pytest.raises(ValueError):
            repo.agregar_item("int-10", "Mouse", -999, 1)

        carrito = repo.obtener_o_crear("int-10")
        assert len(carrito.items) == 1
        assert carrito.items[0].nombre == "Laptop"
