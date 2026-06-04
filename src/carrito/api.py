"""
API REST para el carrito de compras de TiendaUV.
Construida con FastAPI. Usada por las pruebas de carga (Locust) y de seguridad.

Ejecutar:
    uv run uvicorn src.carrito.api:app --port 8000 --reload
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.carrito.carrito import Carrito

app = FastAPI(title="TiendaUV — Carrito API", version="1.0.0")

# Almacenamiento en memoria: sesion_id → Carrito
_carritos: dict[str, Carrito] = {}


def _get_or_create(sesion_id: str) -> Carrito:
    if sesion_id not in _carritos:
        _carritos[sesion_id] = Carrito()
    return _carritos[sesion_id]


# ── Modelos de entrada (Pydantic valida tipos automáticamente) ────────


class ProductoInput(BaseModel):
    nombre: str
    precio: float
    cantidad: int


class DescuentoInput(BaseModel):
    tipo: str
    valor: float


# ── Endpoints ─────────────────────────────────────────────────────────


@app.get("/carrito/health-check")
def health_check():
    return {"status": "ok"}


@app.post("/carrito/{sesion_id}/productos", status_code=201)
def agregar_producto(sesion_id: str, producto: ProductoInput):
    carrito = _get_or_create(sesion_id)
    try:
        carrito.agregar_producto(producto.nombre, producto.precio, producto.cantidad)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"mensaje": f"Producto '{producto.nombre}' agregado al carrito"}


@app.get("/carrito/{sesion_id}")
def obtener_carrito(sesion_id: str):
    carrito = _get_or_create(sesion_id)
    return {
        "sesion_id": sesion_id,
        "productos": carrito.obtener_productos(),
        "total": carrito.calcular_total(),
    }


@app.post("/carrito/{sesion_id}/descuento")
def aplicar_descuento(sesion_id: str, descuento: DescuentoInput):
    carrito = _get_or_create(sesion_id)
    try:
        carrito.aplicar_descuento(descuento.tipo, descuento.valor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"mensaje": "Descuento aplicado", "total": carrito.calcular_total()}


@app.delete("/carrito/{sesion_id}")
def vaciar_carrito(sesion_id: str):
    if sesion_id in _carritos:
        _carritos[sesion_id].vaciar()
    return {"mensaje": "Carrito vaciado"}
