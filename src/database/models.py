from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class CarritoDB(Base):
    __tablename__ = "carritos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sesion_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    descuento_tipo: Mapped[str | None] = mapped_column(String(20), nullable=True)
    descuento_valor: Mapped[float] = mapped_column(Float, default=0.0)
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    items: Mapped[list["ItemCarritoDB"]] = relationship(
        "ItemCarritoDB", back_populates="carrito", cascade="all, delete-orphan"
    )


class ItemCarritoDB(Base):
    __tablename__ = "items_carrito"
    __table_args__ = (
        CheckConstraint("precio > 0", name="ck_precio_positivo"),
        CheckConstraint("cantidad >= 1", name="ck_cantidad_minima"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    carrito_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("carritos.id", ondelete="CASCADE"), nullable=False
    )
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    precio: Mapped[float] = mapped_column(Float, nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    carrito: Mapped["CarritoDB"] = relationship("CarritoDB", back_populates="items")

    def subtotal(self) -> float:
        return self.precio * self.cantidad
