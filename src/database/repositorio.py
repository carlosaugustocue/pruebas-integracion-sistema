"""
Repositorio de operaciones de BD para el carrito de compras.

El patron Repository
--------------------
El patron Repository es una capa de abstraccion entre la logica de negocio
(la API) y la persistencia (la BD). La API no sabe si los datos estan en
PostgreSQL, SQLite o en un CSV. Solo llama al repositorio y este se encarga
de los detalles de acceso a datos.

Beneficios del patron:
  1. La API es mas simple: no tiene queries SQL, solo llamadas a metodos.
  2. El repositorio es testeable de forma independiente (test_repositorio_db.py).
  3. Si se cambia de PostgreSQL a otra BD, solo hay que modificar el repositorio.
  4. Se centraliza la logica de acceso a datos: si hay un bug en como se calcula
     el total en BD, hay un solo lugar donde corregirlo.

Por que recibe session en el constructor en vez de crearla internamente
----------------------------------------------------------------------
Si el repositorio creara su propia sesion internamente:

    def obtener_o_crear(self, sesion_id):
        with SessionLocal() as session:
            ...

Tendria su propia transaccion. Cuando la API llama a obtener_o_crear y luego a
agregar_item, serian dos transacciones separadas. Si agregar_item falla, los
cambios de obtener_o_crear ya se habrian confirmado (o no, dependiendo de los
detalles) y habria inconsistencia.

Al recibir la sesion como dependencia:
  1. get_db() crea la sesion y la pasa al endpoint.
  2. El endpoint pasa la sesion al repositorio.
  3. Todas las operaciones del request usan la misma sesion y la misma transaccion.
  4. get_db() hace commit al final si todo salio bien, o rollback si hubo error.
  5. La atomicidad del request esta garantizada: o todo se confirma o nada.

Este principio se llama "inyeccion de dependencias": el repositorio no crea sus
dependencias, las recibe desde afuera. Esto facilita enormemente el testing
(los tests de integracion inyectan su propia sesion con rollback automatico).

Por que usa flush() en vez de commit()
---------------------------------------
flush() envia el SQL al motor de BD (INSERT, UPDATE, DELETE) dentro de la
transaccion activa. La BD procesa el SQL y asigna IDs autoincrementales, por
lo que despues del flush() podemos leer item.id (que antes seria None).

commit() confirma definitivamente la transaccion. Los datos son permanentes.

El repositorio usa flush() porque no es su responsabilidad decidir cuando
confirmar. Esa decision la toma:
  - En produccion: get_db() en src/database/config.py hace commit al final del request.
  - En tests de integracion: el fixture db_session hace rollback al final del test.

Si el repositorio hiciera commit(), los tests de integracion no podrian usar
el patron rollback para aislar cada test: el commit confirmaria los datos
permanentemente y los tests se contaminarían entre si.
"""

from sqlalchemy.orm import Session

from src.database.models import CarritoDB, ItemCarritoDB


class CarritoRepositorio:
    """Encapsula todas las operaciones de BD relacionadas con el carrito."""

    def __init__(self, session: Session) -> None:
        # La sesion se almacena como atributo privado.
        # Todos los metodos usan self._session para sus queries y operaciones.
        self._session = session

    def obtener_o_crear(self, sesion_id: str) -> CarritoDB:
        """
        Retorna el carrito existente con ese sesion_id, o crea uno nuevo.

        Este metodo implementa el patron "get or create" (upsert simplificado).
        Es idempotente: llamarlo multiples veces con el mismo sesion_id siempre
        retorna el mismo carrito, sin crear duplicados.

        La query usa .first() en vez de .one(): si no encuentra ninguna fila
        retorna None en vez de lanzar excepcion. Si hay multiples filas (no puede
        pasar porque sesion_id tiene constraint UNIQUE), retorna la primera.

        El flush() despues del add() es necesario para que la BD asigne el id
        autoincremental. Sin flush(), carrito.id seria None y no podriamos
        crear ItemCarritoDB con carrito_id correcto en el siguiente paso.
        """
        # Buscar el carrito por sesion_id: SELECT * FROM carritos WHERE sesion_id = :id LIMIT 1
        carrito = self._session.query(CarritoDB).filter(CarritoDB.sesion_id == sesion_id).first()
        if carrito is None:
            # No existe → crear uno nuevo
            carrito = CarritoDB(sesion_id=sesion_id)
            self._session.add(carrito)
            # flush() envia el INSERT a la BD dentro de la transaccion.
            # La BD asigna el id autoincremental. carrito.id ya tiene valor.
            self._session.flush()
        return carrito

    def agregar_item(
        self, sesion_id: str, nombre: str, precio: float, cantidad: int
    ) -> ItemCarritoDB:
        """
        Agrega un item al carrito. Si el producto ya existe, suma la cantidad.

        Validaciones al inicio del metodo (antes de tocar la BD):
          - precio <= 0: no tiene sentido un producto sin precio positivo.
          - cantidad < 1 o > 99: restricciones de negocio.

        Si la validacion falla, se lanza ValueError antes de cualquier operacion
        de BD, lo que garantiza que no queda estado parcial.

        El next() con un generador es una forma Pythonica de buscar el primer
        item que cumpla la condicion en una lista, retornando None si no hay ninguno.
        Es equivalente a un loop for/break pero mas conciso.
        """
        # Validaciones de negocio antes de cualquier operacion en BD
        if precio <= 0:
            raise ValueError(f"El precio debe ser mayor a 0, recibido: {precio}")
        if cantidad < 1:
            raise ValueError(f"La cantidad debe ser al menos 1, recibido: {cantidad}")
        if cantidad > 99:
            raise ValueError(f"La cantidad no puede superar 99 unidades, recibido: {cantidad}")

        carrito = self.obtener_o_crear(sesion_id)

        # Buscar si el producto ya existe en el carrito (por nombre)
        item_existente = next((i for i in carrito.items if i.nombre == nombre), None)
        if item_existente is not None:
            # El producto ya esta en el carrito: sumar la cantidad
            item_existente.cantidad += cantidad
            self._session.flush()  # Envia el UPDATE a la BD dentro de la transaccion
            return item_existente

        # Producto nuevo: crear un ItemCarritoDB y agregarlo a la sesion
        item = ItemCarritoDB(carrito_id=carrito.id, nombre=nombre, precio=precio, cantidad=cantidad)
        self._session.add(item)
        self._session.flush()  # Envia el INSERT; la BD asigna item.id
        return item

    def eliminar_item(self, sesion_id: str, nombre: str) -> None:
        """
        Elimina un item del carrito por su nombre.
        Lanza ValueError si el producto no existe.
        """
        carrito = self.obtener_o_crear(sesion_id)
        item = next((i for i in carrito.items if i.nombre == nombre), None)
        if item is None:
            raise ValueError(f"El producto '{nombre}' no se encuentra en el carrito")
        self._session.delete(item)
        self._session.flush()

    def aplicar_descuento(self, sesion_id: str, tipo: str, valor: float) -> None:
        """
        Guarda el descuento en la fila del carrito en la BD.

        Actualiza dos columnas de CarritoDB: descuento_tipo y descuento_valor.
        SQLAlchemy detecta automaticamente que el objeto fue modificado y emite
        el UPDATE correspondiente al hacer flush().
        """
        if tipo not in ("porcentaje", "fijo"):
            raise ValueError(f"Tipo de descuento invalido: {tipo}")
        if tipo == "porcentaje" and (valor < 0 or valor > 100):
            raise ValueError(f"El porcentaje debe estar entre 0 y 100, recibido: {valor}")
        if tipo == "fijo" and valor < 0:
            raise ValueError(f"El descuento fijo no puede ser negativo: {valor}")

        carrito = self.obtener_o_crear(sesion_id)
        # Modificar los atributos del objeto ORM: SQLAlchemy marca la fila como "dirty"
        carrito.descuento_tipo = tipo
        carrito.descuento_valor = valor
        # flush() emite el UPDATE: UPDATE carritos SET descuento_tipo=..., descuento_valor=...
        # WHERE id = ...
        self._session.flush()

    def calcular_total(self, sesion_id: str) -> float:
        """
        Calcula el total del carrito leyendo de la BD.

        Nota: este metodo NO llama a obtener_o_crear porque NO debe crear un
        carrito si no existe. Si se pide el total de un carrito inexistente,
        el resultado logico es 0.0, no crear un carrito vacio.

        La query usa .first() que retorna None si no hay ninguna fila para ese
        sesion_id, y se maneja con el if carrito is None.
        """
        carrito = self._session.query(CarritoDB).filter(CarritoDB.sesion_id == sesion_id).first()
        if carrito is None:
            return 0.0
        # La navegacion ORM carrito.items carga los items relacionados de la BD
        # (lazy loading por defecto: SQLAlchemy hace el SELECT cuando se accede por primera vez)
        subtotal = sum(item.subtotal() for item in carrito.items)
        if carrito.descuento_tipo == "porcentaje":
            subtotal = subtotal * (1 - carrito.descuento_valor / 100)
        elif carrito.descuento_tipo == "fijo":
            subtotal = subtotal - carrito.descuento_valor
        return max(subtotal, 0.0)  # El total nunca puede ser negativo

    def calcular_total_con_iva(self, sesion_id: str, tasa: float = 19.0) -> float:
        """Calcula el total con IVA. El IVA se aplica despues del descuento."""
        return self.calcular_total(sesion_id) * (1 + tasa / 100)

    def vaciar(self, sesion_id: str) -> None:
        """
        Elimina todos los items del carrito y resetea el descuento.

        El carrito en si (la fila en la tabla carritos) NO se elimina.
        Solo se limpian sus items y su descuento. Esto es importante para
        mantener el historial del carrito y para que el sesion_id siga siendo
        valido para futuros items.

        carrito.items.clear() funciona porque la relacion tiene cascade="all,
        delete-orphan": al desconectar los items del carrito, SQLAlchemy
        automaticamente emite DELETE para cada uno de ellos en el flush().
        """
        carrito = self._session.query(CarritoDB).filter(CarritoDB.sesion_id == sesion_id).first()
        if carrito is not None:
            # clear() desvincula todos los items. El cascade delete-orphan
            # hace que SQLAlchemy los elimine de la BD al hacer flush().
            carrito.items.clear()
            carrito.descuento_tipo = None
            carrito.descuento_valor = 0.0
            self._session.flush()

    def obtener_productos(self, sesion_id: str) -> list[dict]:
        """
        Retorna la lista de productos del carrito como diccionarios.

        Retorna lista vacia si el carrito no existe, sin lanzar excepcion.
        El endpoint GET /carrito/{sesion_id} usa esto para poder retornar
        un carrito "vacio" en vez de un 404 cuando el sesion_id no existe.
        """
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
