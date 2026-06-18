# tests/performance/locustfile.py
"""
Pruebas de carga para la API del carrito de TiendaUV.
Escenario: Dia normal de operacion con usuarios comprando.

Que es Locust y como se diferencia de pytest
---------------------------------------------
pytest es un framework de pruebas funcionales: verifica que el codigo hace
lo correcto. Locust es un framework de pruebas de carga: verifica que el
sistema se comporta bien bajo presion de multiples usuarios concurrentes.

Con pytest se ejecutan tests secuencialmente (uno a la vez). Con Locust se
simulan N usuarios haciendo peticiones simultaneamente, lo que genera carga
real en el servidor, la BD, la red y la CPU.

Locust no usa pytest: tiene su propio ejecutable ('locust'), su propia forma
de definir escenarios (clases que heredan de HttpUser) y su propio reporte
(CSV, HTML, dashboard web). Los archivos de Locust no son descubiertos por
pytest y no aparecen en la suite de pytest.

Que son los usuarios virtuales y como simulan comportamiento humano
-------------------------------------------------------------------
Locust instancia N copies de las clases HttpUser definidas en este archivo.
Cada instancia es un "usuario virtual": un hilo de ejecucion independiente
que hace peticiones al servidor en un bucle continuo.

El ciclo de vida de un usuario virtual:
  1. on_start(): se ejecuta una vez cuando el usuario "llega al sitio".
     Aqui se inicializa el estado del usuario (sesion_id, catalogo).
  2. Bucle: Locust elige aleatoriamente una tarea (@task) ponderada por su peso.
     Ejecuta la tarea. Espera wait_time. Vuelve a elegir una tarea.
  3. Esto se repite hasta que termina el tiempo de ejecucion (--run-time).

El resultado es un flujo de peticiones que se parece al de usuarios reales:
no todos hacen lo mismo al mismo tiempo, hay pauses, hay variedad de acciones.

Que significa el peso (peso 3 vs peso 1) en las tareas
-------------------------------------------------------
@task(3) significa que esta tarea tiene peso 3. Locust elige la siguiente
tarea con probabilidad proporcional al peso:

  Si las tareas son:
    agregar_producto_al_carrito: peso 3
    consultar_carrito:           peso 2
    aplicar_cupon:               peso 1
    abandonar_carrito:           peso 1
  Total de pesos: 3 + 2 + 1 + 1 = 7

  Probabilidades:
    agregar_producto: 3/7 ≈ 43%
    consultar_carrito: 2/7 ≈ 29%
    aplicar_cupon: 1/7 ≈ 14%
    abandonar_carrito: 1/7 ≈ 14%

Esto refleja el comportamiento real observado en e-commerce: los usuarios
agregan productos con mucha mayor frecuencia que aplican cupones o abandonan.

Que son los SLAs y por que P95 es mejor que el promedio
--------------------------------------------------------
SLA (Service Level Agreement) es el compromiso de rendimiento del sistema.
Por ejemplo: "el 95% de las peticiones deben responder en menos de 500ms".

P95 (percentil 95): el tiempo de respuesta que el 95% de las peticiones no
supera. Si el P95 es 300ms, significa que 95 de cada 100 peticiones responden
en menos de 300ms. Las 5 restantes pueden tardar mas.

Por que P95 es mejor que el promedio:
  Ejemplo: 99 peticiones en 50ms, 1 peticion en 10.000ms.
    Promedio: (99*50 + 10000) / 100 = 149ms. Parece bien.
    P95: 50ms. Tambien parece bien.
    P99: 10.000ms. Alerta! 1 de cada 100 usuarios espera 10 segundos.

El promedio oculta los casos extremos. El P95 los revela parcialmente.
El P99 los revela casi completamente. Para un sistema de e-commerce, un
usuario que espera 10 segundos probablemente abandona la compra.

Los SLAs de este proyecto (verificados en el pipeline):
  - P95 < 500ms: el 95% de las peticiones responden en menos de medio segundo.
  - Tasa de error < 1%: menos del 1% de las peticiones retornan error.

Como ejecutarlo con interfaz web vs headless
---------------------------------------------
Con dashboard web (modo interactivo):
    # La API debe estar corriendo
    docker compose up -d
    # Lanzar Locust
    uv run locust -f tests/performance/locustfile.py --host http://localhost:8000
    # Abrir en el navegador: http://localhost:8089
    # En la UI: definir numero de usuarios y tasa de spawn, click Start

Headless (sin interfaz, como en CI):
    uv run locust -f tests/performance/locustfile.py \\
        --headless -u 100 -r 10 --run-time 60s \\
        --host http://localhost:8000 \\
        --csv reports/locust/resultados \\
        --html reports/locust/reporte.html
    # -u 100: 100 usuarios virtuales
    # -r 10: spawn rate: 10 nuevos usuarios por segundo hasta llegar a 100
    # --run-time 60s: correr 60 segundos y parar

Por que wait_time simula comportamiento humano
----------------------------------------------
Un sistema real no recibe peticiones a velocidad maxima del CPU. Los usuarios
reales leen, piensan, mueven el mouse, esperan que cargue la pagina. wait_time
simula ese tiempo de "think time" entre acciones.

between(1, 3): el usuario espera entre 1 y 3 segundos entre cada tarea.
Si hay 50 usuarios con wait_time=between(1,3), el servidor recibe
aproximadamente 50/(1.5 promedio) ≈ 33 peticiones por segundo.

Sin wait_time (o con wait_time muy pequeno), los usuarios generan peticiones
a la maxima velocidad que Locust puede procesar, lo que no refleja trafico
real y puede generar metricas de rendimiento muy diferentes a produccion.
"""

import random
import uuid

from locust import HttpUser, between, task


class UsuarioNormal(HttpUser):
    """
    Simula un usuario tipico que navega y compra en TiendaUV.

    wait_time = between(1, 3) significa que entre cada tarea
    el usuario espera entre 1 y 3 segundos — simula el tiempo
    que un humano real tarda en decidir que hacer.
    """

    wait_time = between(1, 3)

    def on_start(self):
        """
        Se ejecuta UNA VEZ cuando el usuario virtual "llega al sitio".

        Cada usuario virtual tiene su propio sesion_id unico. Esto garantiza
        que los 50 usuarios virtuales tienen 50 carritos independientes en la BD.
        Si compartieran el mismo sesion_id, habria contention (bloqueos en la
        BD) y el test no mediria el rendimiento real del sistema.
        """
        # Cada usuario tiene su propia sesion unica
        self.sesion_id = str(uuid.uuid4())

        # Productos disponibles en la tienda
        self.catalogo = [
            {"nombre": "Laptop Lenovo", "precio": 2500000},
            {"nombre": "Mouse Logitech", "precio": 85000},
            {"nombre": "Teclado Mecanico", "precio": 250000},
            {"nombre": "Monitor 27''", "precio": 1500000},
            {"nombre": "Webcam HD", "precio": 200000},
            {"nombre": "Audifonos Sony", "precio": 350000},
        ]

    @task(3)
    def agregar_producto_al_carrito(self):
        """
        Tarea mas frecuente (peso 3).
        El usuario agrega un producto aleatorio al carrito.
        Se ejecuta ~3 veces mas seguido que las tareas de peso 1.

        catch_response=True permite validar la respuesta manualmente y
        marcarla como exitosa o fallida segun la logica de negocio.
        Sin catch_response, Locust marca como fallo cualquier respuesta
        con status >= 400. Aqui 422 es una validacion esperada, no un fallo.

        name="/carrito/[id]/productos" agrupa todas las peticiones de este tipo
        bajo el mismo nombre en el dashboard, sin importar el sesion_id.
        Sin esto, cada usuario tendria su propia fila de metricas.
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
            name="/carrito/[id]/productos",  # Nombre agrupado en el dashboard
        ) as response:
            # 201 = exito, 422 = validacion (no es falla del server)
            if response.status_code in [201, 422]:
                response.success()
            else:
                # Cualquier otro codigo es un fallo inesperado que se reporta en el dashboard
                response.failure(f"Status inesperado: {response.status_code}")

    @task(2)
    def consultar_carrito(self):
        """
        Tarea frecuente (peso 2).
        El usuario mira su carrito para ver el total antes de pagar.

        Ademas de verificar el status HTTP, valida una regla de negocio critica:
        el total nunca debe ser negativo. Si Locust detecta un total negativo,
        lo registra como un fallo de logica de negocio en el dashboard.
        """
        with self.client.get(
            f"/carrito/{self.sesion_id}",
            catch_response=True,
            name="/carrito/[id] GET",
        ) as response:
            if response.status_code == 200:
                data = response.json()
                # Validacion de negocio: el total nunca debe ser negativo
                if data.get("total", 0) < 0:
                    response.failure("BUG CRITICO: total negativo detectado")
                else:
                    response.success()
            else:
                response.failure(f"No se pudo obtener el carrito: {response.status_code}")

    @task(1)
    def aplicar_cupon(self):
        """
        Tarea ocasional (peso 1).
        El usuario intenta aplicar un cupon de descuento.

        No usa catch_response porque cualquier status es aceptable aqui:
        201/200 si funciono, 422 si el descuento es invalido, etc. Locust
        usara su comportamiento por defecto (marcar como fallo si status >= 400).
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

        El DELETE vacia el carrito. Si el usuario sigue comprando despues,
        el siguiente agregar_producto creara un carrito nuevo. Esto simula
        el ciclo real: ver productos, agregar, arrepentirse, vaciar, comprar de nuevo.
        """
        self.client.delete(
            f"/carrito/{self.sesion_id}",
            name="/carrito/[id] DELETE",
        )


class UsuarioPremium(HttpUser):
    """
    Simula usuarios premium que compran mas rapido y en mayor volumen.

    weight = 1 controla la proporcion entre tipos de usuarios.
    Si UsuarioNormal no tiene weight, Locust le asigna weight=1 implicito.
    Con UsuarioPremium weight=1, la proporcion es 1:1 (misma cantidad de usuarios
    premium y normales). Para cambiar a 3 normales por cada 1 premium, pon
    weight=3 en UsuarioNormal.
    """

    weight = 1  # Relacion 1:1 con UsuarioNormal
    wait_time = between(0.5, 1)  # Mas rapido que el usuario normal

    def on_start(self):
        # Prefijo "premium-" facilita identificar sesiones premium en los logs de la BD
        self.sesion_id = f"premium-{uuid.uuid4()}"

    @task
    def compra_rapida(self):
        """El premium agrega varios productos seguidos y consulta el total."""
        # El usuario premium sabe lo que quiere: compra sin dudar
        for nombre, precio in [
            ("Laptop Lenovo", 2500000),
            ("Monitor 27''", 1500000),
        ]:
            self.client.post(
                f"/carrito/{self.sesion_id}/productos",
                json={"nombre": nombre, "precio": precio, "cantidad": 1},
                name="/carrito/premium/productos",
            )

        # Consulta el total para confirmar antes de pagar
        self.client.get(
            f"/carrito/{self.sesion_id}",
            name="/carrito/premium GET",
        )
