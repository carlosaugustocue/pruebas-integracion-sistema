"""
Modelos SQLAlchemy que mapean las clases Python a las tablas de la BD.

Que es un ORM y por que SQLAlchemy 2.x usa Mapped y mapped_column
------------------------------------------------------------------
ORM (Object-Relational Mapper) es una tecnica para trabajar con la BD usando
objetos Python en vez de SQL directo. SQLAlchemy es el ORM mas usado en Python.

En SQLAlchemy 1.x, las columnas se declaraban con Column():
    id = Column(Integer, primary_key=True)

En SQLAlchemy 2.x (el que usa este proyecto), se usan Mapped y mapped_column():
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

La diferencia clave: Mapped[int] es una anotacion de tipo Python. Esto permite
que mypy, pyright y otros analizadores de tipos entiendan que carrito.id es
un int, sin necesidad de stubs adicionales. La API de Mapped es mas verbosa
pero produce codigo con tipos mucho mejor definidos.

Que es DeclarativeBase y por que los modelos heredan de Base
------------------------------------------------------------
DeclarativeBase es la clase base de SQLAlchemy 2.x para definir modelos ORM.
Al subclasificarla, se crea la clase Base que tiene el metadata: el registro
de todas las tablas que hereden de ella.

    class Base(DeclarativeBase):
        pass

Todos los modelos (CarritoDB, ItemCarritoDB) heredan de Base. Esto permite que
Base.metadata.create_all() encuentre automaticamente todas las tablas y ejecute
los CREATE TABLE. No hay que registrarlas manualmente.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Clase base de SQLAlchemy. Contiene el metadata con el registro de tablas."""

    pass


class CarritoDB(Base):
    """
    Tabla 'carritos': un registro por sesion de usuario.

    Un carrito se identifica por su sesion_id: un string libre que el cliente
    elige (puede ser un UUID, un nombre de usuario, cualquier identificador).
    El carrito se crea automaticamente la primera vez que se agrega un producto.
    """

    __tablename__ = "carritos"

    # primary_key=True: columna de clave primaria, identifica de forma unica cada fila.
    # autoincrement=True: la BD asigna el proximo entero disponible al insertar.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # unique=True: no pueden existir dos carritos con el mismo sesion_id.
    # index=True: crea un indice B-tree en esta columna, lo que hace los
    # SELECT WHERE sesion_id = ... extremadamente rapidos (O(log n) vs O(n)).
    sesion_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    # nullable=True: el campo puede ser NULL en la BD. Un carrito sin descuento
    # activo tiene descuento_tipo = NULL, no un string vacio.
    descuento_tipo: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # default=0.0 establece el valor por defecto en Python (al crear el objeto).
    # server_default= (si lo hubiera) lo estableceria en la BD con DEFAULT 0.0 en la columna.
    descuento_valor: Mapped[float] = mapped_column(Float, default=0.0)

    # func.now() llama a la funcion NOW() de la BD en el momento del INSERT.
    # Es mas confiable que datetime.utcnow() en Python porque usa el reloj de la BD,
    # que es consistente aunque haya multiples instancias del servidor.
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # onupdate=func.now(): cada vez que se hace UPDATE en esta fila, la BD
    # actualiza automaticamente este campo con la hora actual.
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # relationship define la relacion ORM entre CarritoDB e ItemCarritoDB.
    # back_populates="carrito" en ItemCarritoDB hace que la relacion sea bidireccional:
    #   carrito.items → lista de ItemCarritoDB de ese carrito
    #   item.carrito  → el CarritoDB al que pertenece el item
    #
    # cascade="all, delete-orphan": define que pasa con los items cuando el carrito
    # se modifica o elimina.
    #   "all": propaga save, update, expunge, delete desde el padre a los hijos.
    #   "delete-orphan": si un item deja de estar en carrito.items (se desvincula
    #     del padre), SQLAlchemy lo elimina de la BD automaticamente.
    #     Ejemplo: carrito.items.clear() → SQLAlchemy emite DELETE para cada item.
    #   Sin esta opcion, los items desvinculados quedarian como huerfanos en la
    #   tabla items_carrito (FK a un carrito que ya no los referencia).
    items: Mapped[list["ItemCarritoDB"]] = relationship(
        "ItemCarritoDB", back_populates="carrito", cascade="all, delete-orphan"
    )


class ItemCarritoDB(Base):
    """
    Tabla 'items_carrito': un registro por producto dentro de un carrito.

    La relacion es: un CarritoDB tiene muchos ItemCarritoDB (one-to-many).
    Cada ItemCarritoDB tiene exactamente un CarritoDB padre.
    """

    __tablename__ = "items_carrito"

    # __table_args__ define restricciones a nivel de tabla.
    # CheckConstraint son restricciones que la BD misma verifica en cada INSERT/UPDATE.
    # Son una SEGUNDA CAPA de validacion, complementaria a la del repositorio Python.
    #
    # Por que tener dos capas? Porque la validacion en Python es mas clara y produce
    # mejores mensajes de error (se puede retornar un 422 con descripcion).
    # La restriccion en la BD es la red de seguridad: si por algun bug en el codigo
    # Python la validacion se salta, la BD rechaza el INSERT con un error de constraint.
    # Esto garantiza integridad de datos absolutamente, sin importar quien escribe.
    __table_args__ = (
        # precio > 0: precio de 0 o negativo no tiene sentido para un producto en venta.
        # Nota: el repositorio valida precio <= 0 (mas permisivo que este constraint).
        CheckConstraint("precio > 0", name="ck_precio_positivo"),
        # cantidad >= 1: no tiene sentido tener 0 unidades de un producto en el carrito.
        CheckConstraint("cantidad >= 1", name="ck_cantidad_minima"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ForeignKey("carritos.id"): clave foranea que referencia la clave primaria de carritos.
    # ondelete="CASCADE": si se elimina la fila del carrito padre, la BD automaticamente
    # elimina todos los items de ese carrito. Es la restriccion FK a nivel de BD,
    # complementaria al cascade="all, delete-orphan" del ORM Python.
    carrito_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("carritos.id", ondelete="CASCADE"), nullable=False
    )

    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    precio: Mapped[float] = mapped_column(Float, nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relacion inversa: desde el item se puede navegar al carrito padre.
    # back_populates="items" sincroniza con la lista items de CarritoDB.
    carrito: Mapped["CarritoDB"] = relationship("CarritoDB", back_populates="items")

    def subtotal(self) -> float:
        """Calcula precio x cantidad para este item."""
        return self.precio * self.cantidad
