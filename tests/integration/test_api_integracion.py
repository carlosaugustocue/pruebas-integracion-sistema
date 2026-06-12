"""
Tests de integracion API + PostgreSQL.
La BD se inyecta via client_con_bd del conftest.
"""

import pytest

from src.database.models import CarritoDB, ItemCarritoDB


@pytest.mark.integration
class TestAPIConBaseDeDatos:
    def test_post_producto_persiste_en_bd(self, client_con_bd, db_session):
        client_con_bd.post(
            "/carrito/api-1/productos",
            json={"nombre": "Laptop", "precio": 2_500_000, "cantidad": 1},
        )

        item = (
            db_session.query(ItemCarritoDB)
            .join(CarritoDB)
            .filter(CarritoDB.sesion_id == "api-1")
            .first()
        )
        assert item is not None
        assert item.nombre == "Laptop"

    def test_get_carrito_lee_datos_reales_de_bd(self, client_con_bd, db_session):
        carrito = CarritoDB(sesion_id="api-2")
        db_session.add(carrito)
        db_session.flush()
        db_session.add(
            ItemCarritoDB(carrito_id=carrito.id, nombre="Monitor", precio=1_500_000, cantidad=1)
        )
        db_session.flush()

        response = client_con_bd.get("/carrito/api-2")
        data = response.json()

        assert response.status_code == 200
        assert len(data["productos"]) == 1
        assert data["productos"][0]["nombre"] == "Monitor"

    def test_estado_persiste_entre_requests(self, client_con_bd):
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
        client_con_bd.post(
            "/carrito/api-4/productos",
            json={"nombre": "Laptop", "precio": 1_000_000, "cantidad": 1},
        )
        client_con_bd.post(
            "/carrito/api-4/descuento",
            json={"tipo": "porcentaje", "valor": 10},
        )

        assert client_con_bd.get("/carrito/api-4").json()["total"] == pytest.approx(900_000)

    def test_vaciar_elimina_todo_de_bd(self, client_con_bd, db_session):
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
        data = client_con_bd.get("/carrito/api-6-nuevo").json()

        assert "sesion_id" in data
        assert "productos" in data
        assert isinstance(data["productos"], list)
        assert "total" in data
        assert "total_con_iva" in data
        assert "cantidad_productos" in data
        assert data["total"] == 0
        assert data["cantidad_productos"] == 0
