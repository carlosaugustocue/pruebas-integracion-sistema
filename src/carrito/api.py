"""
API REST para el carrito de compras de TiendaUV.
Construida con FastAPI. Usada por las pruebas de carga (Locust) y de seguridad.

Ejecutar:
    uv run uvicorn src.carrito.api:app --port 8000 --reload
"""

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.database.config import get_db, init_db
from src.database.repositorio import CarritoRepositorio

app = FastAPI(title="TiendaUV - Carrito API", version="1.0.0")


@app.on_event("startup")
def on_startup() -> None:
    # Garantiza tablas en PostgreSQL. En SQLite ya se crean al importar config.
    init_db()


class ProductoInput(BaseModel):
    nombre: str
    precio: float
    cantidad: int


class DescuentoInput(BaseModel):
    tipo: str
    valor: float


@app.get("/carrito/health-check")
def health_check():
    return {"status": "ok"}


@app.post("/carrito/{sesion_id}/productos", status_code=201)
def agregar_producto(sesion_id: str, producto: ProductoInput, db: Session = Depends(get_db)):
    repo = CarritoRepositorio(db)
    try:
        repo.agregar_item(sesion_id, producto.nombre, producto.precio, producto.cantidad)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"mensaje": f"Producto '{producto.nombre}' agregado al carrito"}


@app.get("/carrito/{sesion_id}")
def obtener_carrito(sesion_id: str, db: Session = Depends(get_db)):
    repo = CarritoRepositorio(db)
    productos = repo.obtener_productos(sesion_id)
    return {
        "sesion_id": sesion_id,
        "productos": productos,
        "total": repo.calcular_total(sesion_id),
        "total_con_iva": repo.calcular_total_con_iva(sesion_id),
        "cantidad_productos": len(productos),
    }


@app.post("/carrito/{sesion_id}/descuento")
def aplicar_descuento(sesion_id: str, descuento: DescuentoInput, db: Session = Depends(get_db)):
    repo = CarritoRepositorio(db)
    try:
        repo.aplicar_descuento(sesion_id, descuento.tipo, descuento.valor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"mensaje": "Descuento aplicado", "total": repo.calcular_total(sesion_id)}


@app.delete("/carrito/{sesion_id}")
def vaciar_carrito(sesion_id: str, db: Session = Depends(get_db)):
    repo = CarritoRepositorio(db)
    repo.vaciar(sesion_id)
    return {"mensaje": "Carrito vaciado"}
