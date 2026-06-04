"""
Modelos de datos del sistema de carrito de compras.
Usamos dataclasses para tener objetos tipados y con validación.
"""

from dataclasses import dataclass


@dataclass
class Producto:
    """Representa un producto dentro del carrito."""

    nombre: str
    precio: float
    cantidad: int

    def __post_init__(self):
        """Validaciones al crear un producto."""
        if self.precio < 0:
            raise ValueError(f"El precio no puede ser negativo: {self.precio}")
        if self.cantidad < 1:
            raise ValueError(f"La cantidad debe ser al menos 1: {self.cantidad}")
        if self.cantidad > 99:
            raise ValueError(f"La cantidad no puede superar 99 unidades: {self.cantidad}")

    def subtotal(self) -> float:
        """Calcula precio × cantidad para este producto."""
        return self.precio * self.cantidad
