"""
Módulo del carrito de compras.
Construido paso a paso con TDD.
"""

from src.carrito.modelos import Producto


class Carrito:
    """Representa un carrito de compras de un usuario."""

    def __init__(self, stock_disponible: dict[str, int] | None = None):
        self._productos: list[Producto] = []
        self._descuento_tipo: str | None = None
        self._descuento_valor: float = 0
        self._stock = stock_disponible

    def obtener_productos(self) -> list[dict]:
        """Retorna la lista de productos como diccionarios."""
        return [
            {"nombre": p.nombre, "precio": p.precio, "cantidad": p.cantidad}
            for p in self._productos
        ]

    def cantidad_productos(self) -> int:
        """Retorna cuántos productos distintos hay en el carrito."""
        return len(self._productos)

    def _validar_stock(self, nombre: str, cantidad_nueva: int):
        """Valida que haya stock suficiente para agregar el producto."""
        if self._stock is None:
            return

        if nombre not in self._stock:
            raise ValueError(f"El producto '{nombre}' no tiene stock disponible")

        cantidad_en_carrito = 0
        for producto in self._productos:
            if producto.nombre == nombre:
                cantidad_en_carrito = producto.cantidad
                break

        total_solicitado = cantidad_en_carrito + cantidad_nueva
        if total_solicitado > self._stock[nombre]:
            raise ValueError(
                f"stock insuficiente para '{nombre}': "
                f"disponible={self._stock[nombre]}, "
                f"en carrito={cantidad_en_carrito}, "
                f"solicitado={cantidad_nueva}"
            )

    def agregar_producto(self, nombre: str, precio: float, cantidad: int):
        """
        Agrega un producto al carrito.
        Si el producto ya existe (mismo nombre), suma la cantidad.
        """
        self._validar_stock(nombre, cantidad)

        for producto in self._productos:
            if producto.nombre == nombre:
                producto.cantidad += cantidad
                return

        self._productos.append(Producto(nombre=nombre, precio=precio, cantidad=cantidad))

    def eliminar_producto(self, nombre: str):
        """
        Elimina un producto del carrito por su nombre.
        Lanza ValueError si el producto no existe.
        """
        for i, producto in enumerate(self._productos):
            if producto.nombre == nombre:
                self._productos.pop(i)
                return

        raise ValueError(f"El producto '{nombre}' no se encuentra en el carrito")

    def calcular_total(self) -> float:
        """Calcula el total del carrito aplicando descuentos si existen."""
        subtotal = sum(producto.subtotal() for producto in self._productos)

        if self._descuento_tipo == "porcentaje":
            subtotal = subtotal * (1 - self._descuento_valor / 100)
        elif self._descuento_tipo == "fijo":
            subtotal = subtotal - self._descuento_valor

        return max(subtotal, 0)

    def aplicar_descuento(self, tipo: str, valor: float):
        """
        Aplica un descuento al carrito.
        tipo: 'porcentaje' (0-100) o 'fijo' (valor en pesos)
        """
        if tipo == "porcentaje" and (valor < 0 or valor > 100):
            raise ValueError(f"El porcentaje debe estar entre 0 y 100, recibido: {valor}")

        if tipo == "fijo" and valor < 0:
            raise ValueError(f"El descuento fijo no puede ser negativo: {valor}")

        self._descuento_tipo = tipo
        self._descuento_valor = valor

    def calcular_total_con_impuestos(self, tasa: float = 19) -> float:
        """
        Calcula el total incluyendo impuestos.
        La tasa por defecto es 19% (IVA Colombia).
        El impuesto se aplica DESPUÉS de descuentos.
        """
        total_sin_iva = self.calcular_total()
        return total_sin_iva * (1 + tasa / 100)

    def vaciar(self):
        """Elimina todos los productos y descuentos del carrito."""
        self._productos.clear()
        self._descuento_tipo = None
        self._descuento_valor = 0
