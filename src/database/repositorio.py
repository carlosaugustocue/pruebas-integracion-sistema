from sqlalchemy.orm import Session

from src.database.models import CarritoDB, ItemCarritoDB


class CarritoRepositorio:
    def __init__(self, session: Session) -> None:
        self._session = session

    def obtener_o_crear(self, sesion_id: str) -> CarritoDB:
        carrito = self._session.query(CarritoDB).filter(CarritoDB.sesion_id == sesion_id).first()
        if carrito is None:
            carrito = CarritoDB(sesion_id=sesion_id)
            self._session.add(carrito)
            self._session.flush()
        return carrito

    def agregar_item(
        self, sesion_id: str, nombre: str, precio: float, cantidad: int
    ) -> ItemCarritoDB:
        if precio <= 0:
            raise ValueError(f"El precio debe ser mayor a 0, recibido: {precio}")
        if cantidad < 1:
            raise ValueError(f"La cantidad debe ser al menos 1, recibido: {cantidad}")
        if cantidad > 99:
            raise ValueError(f"La cantidad no puede superar 99 unidades, recibido: {cantidad}")

        carrito = self.obtener_o_crear(sesion_id)
        item_existente = next((i for i in carrito.items if i.nombre == nombre), None)
        if item_existente is not None:
            item_existente.cantidad += cantidad
            self._session.flush()
            return item_existente

        item = ItemCarritoDB(carrito_id=carrito.id, nombre=nombre, precio=precio, cantidad=cantidad)
        self._session.add(item)
        self._session.flush()
        return item

    def eliminar_item(self, sesion_id: str, nombre: str) -> None:
        carrito = self.obtener_o_crear(sesion_id)
        item = next((i for i in carrito.items if i.nombre == nombre), None)
        if item is None:
            raise ValueError(f"El producto '{nombre}' no se encuentra en el carrito")
        self._session.delete(item)
        self._session.flush()

    def aplicar_descuento(self, sesion_id: str, tipo: str, valor: float) -> None:
        if tipo not in ("porcentaje", "fijo"):
            raise ValueError(f"Tipo de descuento invalido: {tipo}")
        if tipo == "porcentaje" and (valor < 0 or valor > 100):
            raise ValueError(f"El porcentaje debe estar entre 0 y 100, recibido: {valor}")
        if tipo == "fijo" and valor < 0:
            raise ValueError(f"El descuento fijo no puede ser negativo: {valor}")

        carrito = self.obtener_o_crear(sesion_id)
        carrito.descuento_tipo = tipo
        carrito.descuento_valor = valor
        self._session.flush()

    def calcular_total(self, sesion_id: str) -> float:
        carrito = self._session.query(CarritoDB).filter(CarritoDB.sesion_id == sesion_id).first()
        if carrito is None:
            return 0.0
        subtotal = sum(item.subtotal() for item in carrito.items)
        if carrito.descuento_tipo == "porcentaje":
            subtotal = subtotal * (1 - carrito.descuento_valor / 100)
        elif carrito.descuento_tipo == "fijo":
            subtotal = subtotal - carrito.descuento_valor
        return max(subtotal, 0.0)

    def calcular_total_con_iva(self, sesion_id: str, tasa: float = 19.0) -> float:
        return self.calcular_total(sesion_id) * (1 + tasa / 100)

    def vaciar(self, sesion_id: str) -> None:
        carrito = self._session.query(CarritoDB).filter(CarritoDB.sesion_id == sesion_id).first()
        if carrito is not None:
            carrito.items.clear()
            carrito.descuento_tipo = None
            carrito.descuento_valor = 0.0
            self._session.flush()

    def obtener_productos(self, sesion_id: str) -> list[dict]:
        carrito = self._session.query(CarritoDB).filter(CarritoDB.sesion_id == sesion_id).first()
        if carrito is None:
            return []
        return [
            {
                "nombre": item.nombre,
                "precio": item.precio,
                "cantidad": item.cantidad,
                "subtotal": item.subtotal(),
            }
            for item in carrito.items
        ]
