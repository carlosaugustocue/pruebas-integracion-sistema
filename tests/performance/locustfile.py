# tests/performance/locustfile.py
"""
Pruebas de carga para la API del carrito de TiendaUV.
Escenario: Día normal de operación con usuarios comprando.

Cómo ejecutar (headless — sin interfaz):
  uv run locust -f tests/performance/locustfile.py \
    --headless -u 100 -r 10 --run-time 60s \
    --host http://localhost:8000

Cómo ejecutar (con dashboard web):
  uv run locust -f tests/performance/locustfile.py \
    --host http://localhost:8000
  Luego abre: http://localhost:8089
"""

import random
import uuid

from locust import HttpUser, between, task


class UsuarioNormal(HttpUser):
    """
    Simula un usuario típico que navega y compra en TiendaUV.

    wait_time = between(1, 3) significa que entre cada tarea
    el usuario espera entre 1 y 3 segundos — simula el tiempo
    que un humano real tarda en decidir qué hacer.
    """

    wait_time = between(1, 3)

    def on_start(self):
        """
        Se ejecuta UNA VEZ cuando el usuario virtual "llega al sitio".
        Aquí inicializamos el estado del usuario.
        """
        # Cada usuario tiene su propia sesión única
        self.sesion_id = str(uuid.uuid4())

        # Productos disponibles en la tienda
        self.catalogo = [
            {"nombre": "Laptop Lenovo", "precio": 2500000},
            {"nombre": "Mouse Logitech", "precio": 85000},
            {"nombre": "Teclado Mecánico", "precio": 250000},
            {"nombre": "Monitor 27''", "precio": 1500000},
            {"nombre": "Webcam HD", "precio": 200000},
            {"nombre": "Audífonos Sony", "precio": 350000},
        ]

    @task(3)
    def agregar_producto_al_carrito(self):
        """
        Tarea más frecuente (peso 3).
        El usuario agrega un producto aleatorio al carrito.
        Se ejecuta ~3 veces más seguido que las otras tareas.
        """
        producto = random.choice(self.catalogo)
        cantidad = random.randint(1, 3)

        with self.client.post(
            f"/carrito/{self.sesion_id}/productos",
            json={
                "nombre": producto["nombre"],
                "precio": producto["precio"],
                "cantidad": cantidad,
            },
            catch_response=True,  # Permite validar la respuesta manualmente
            name="/carrito/[id]/productos",  # Nombre en el dashboard
        ) as response:
            # Validamos el negocio: 201 = éxito, 422 = validación (no es falla del server)
            if response.status_code in [201, 422]:
                response.success()
            else:
                # Cualquier otro código es un fallo inesperado
                response.failure(f"Status inesperado: {response.status_code}")

    @task(2)
    def consultar_carrito(self):
        """
        Tarea frecuente (peso 2).
        El usuario mira su carrito para ver el total.
        """
        with self.client.get(
            f"/carrito/{self.sesion_id}",
            catch_response=True,
            name="/carrito/[id] GET",
        ) as response:
            if response.status_code == 200:
                data = response.json()
                # Validación de negocio: el total nunca debe ser negativo
                if data.get("total", 0) < 0:
                    response.failure("BUG CRÍTICO: total negativo detectado")
                else:
                    response.success()
            else:
                response.failure(f"No se pudo obtener el carrito: {response.status_code}")

    @task(1)
    def aplicar_cupon(self):
        """
        Tarea ocasional (peso 1).
        El usuario intenta aplicar un cupón de descuento.
        """
        self.client.post(
            f"/carrito/{self.sesion_id}/descuento",
            json={"tipo": "porcentaje", "valor": 10},
            name="/carrito/[id]/descuento",
        )

    @task(1)
    def abandonar_carrito(self):
        """
        Tarea ocasional (peso 1).
        El usuario abandona el carrito (comportamiento real: ~70% de carritos son abandonados).
        """
        self.client.delete(
            f"/carrito/{self.sesion_id}",
            name="/carrito/[id] DELETE",
        )


class UsuarioPremium(HttpUser):
    """
    Simula usuarios premium que compran más rápido y en mayor volumen.

    weight = 1 significa que por cada 3 usuarios normales
    habrá 1 usuario premium.
    """

    weight = 1  # Relación 3:1 con UsuarioNormal
    wait_time = between(0.5, 1)  # Más rápido que el usuario normal

    def on_start(self):
        self.sesion_id = f"premium-{uuid.uuid4()}"

    @task
    def compra_rapida(self):
        """El premium agrega varios productos seguidos y consulta el total."""
        for nombre, precio in [
            ("Laptop Lenovo", 2500000),
            ("Monitor 27''", 1500000),
        ]:
            self.client.post(
                f"/carrito/{self.sesion_id}/productos",
                json={"nombre": nombre, "precio": precio, "cantidad": 1},
                name="/carrito/premium/productos",
            )

        self.client.get(
            f"/carrito/{self.sesion_id}",
            name="/carrito/premium GET",
        )
