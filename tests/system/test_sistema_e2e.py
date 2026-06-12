"""
Tests de sistema end-to-end.
Requieren que la API este corriendo en API_URL.
Para CI: docker compose -f docker-compose.test.yml up -d
Para local: docker compose up -d && export API_URL=http://localhost:8000
"""

import os
import time
import uuid

import httpx
import pytest

API_URL = os.getenv("API_URL", "http://localhost:8000")


@pytest.fixture(scope="module")
def cliente_http():
    with httpx.Client(base_url=API_URL, timeout=10.0) as client:
        yield client


def sesion_unica() -> str:
    return f"e2e-{uuid.uuid4().hex[:8]}"


@pytest.mark.system
def test_health_check_sistema(cliente_http):
    response = cliente_http.get("/carrito/health-check")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.system
def test_flujo_compra_normal_completo(cliente_http):
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
    assert data["total"] == pytest.approx(2_670_000)
    assert len(data["productos"]) == 2


@pytest.mark.system
def test_flujo_con_descuento_porcentaje(cliente_http):
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
    sesion_a = sesion_unica()
    sesion_b = sesion_unica()

    cliente_http.post(
        f"/carrito/{sesion_a}/productos",
        json={"nombre": "Laptop", "precio": 2_500_000, "cantidad": 1},
    )
    cliente_http.post(
        f"/carrito/{sesion_b}/productos",
        json={"nombre": "Mouse", "precio": 85_000, "cantidad": 1},
    )

    cliente_http.delete(f"/carrito/{sesion_a}")

    assert cliente_http.get(f"/carrito/{sesion_a}").json()["total"] == 0
    assert cliente_http.get(f"/carrito/{sesion_b}").json()["total"] == pytest.approx(85_000)


@pytest.mark.system
def test_mismo_producto_dos_veces_suma(cliente_http):
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
    sesion = sesion_unica()
    inicio = time.monotonic()
    cliente_http.get(f"/carrito/{sesion}")
    tiempo_ms = (time.monotonic() - inicio) * 1000
    assert tiempo_ms < 500, f"Respuesta demoro {tiempo_ms:.1f}ms, limite 500ms"
