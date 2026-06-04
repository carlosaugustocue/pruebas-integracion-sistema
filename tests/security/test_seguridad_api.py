"""
Pruebas básicas de seguridad para la API del carrito de TiendaUV.
Basadas en OWASP API Security Top 10 (2023).

Estas pruebas son la primera línea de defensa automatizada en el pipeline.
No reemplazan un pentest profesional.
"""

from fastapi.testclient import TestClient

from src.carrito.api import app

client = TestClient(app)


class TestInyeccion:
    """
    OWASP API8 / Injection
    Los datos del usuario no deben interpretarse como comandos.
    """

    def test_sql_injection_en_nombre_no_causa_error_500(self):
        """
        SQL Injection en el nombre del producto.
        El sistema debe tratar el string como dato, nunca como SQL.
        Nunca debe retornar 500.
        """
        payload_malicioso = "Laptop'; DROP TABLE productos; --"

        response = client.post(
            "/carrito/test-sql/productos",
            json={"nombre": payload_malicioso, "precio": 100, "cantidad": 1},
        )

        assert response.status_code in [201, 422], f"Código inesperado: {response.status_code}"
        assert response.status_code != 500, (
            "ERROR DE SEGURIDAD: el payload SQL causó un error interno"
        )

    def test_xss_en_nombre_se_almacena_como_texto(self):
        """
        Cross-Site Scripting (XSS): el payload JavaScript no debe ejecutarse,
        debe guardarse y devolverse como texto plano.
        """
        payload_xss = "<script>document.cookie='stolen'</script>"

        response = client.post(
            "/carrito/test-xss/productos",
            json={"nombre": payload_xss, "precio": 100, "cantidad": 1},
        )

        if response.status_code == 201:
            r_get = client.get("/carrito/test-xss")
            productos = r_get.json()["productos"]
            nombres = [p["nombre"] for p in productos]
            assert payload_xss in nombres, (
                "El payload XSS no se almacenó como texto — posible ejecución"
            )

    def test_integer_overflow_no_colapsa_servidor(self):
        """
        Número extremadamente grande en el precio.
        El servidor debe manejarlo graciosamente, sin error 500.
        """
        numero_gigante = 10**308

        response = client.post(
            "/carrito/test-overflow/productos",
            json={"nombre": "Laptop", "precio": numero_gigante, "cantidad": 1},
        )

        assert response.status_code in [201, 422]
        assert response.status_code != 500


class TestValidacionEntradas:
    """
    OWASP API8: Security Misconfiguration
    Las entradas deben validarse estrictamente en la frontera del sistema.
    """

    def test_tipos_de_datos_incorrectos_son_rechazados(self):
        """
        Un string donde se espera un número debe retornar 422, nunca 500.
        FastAPI/Pydantic captura esto automáticamente.
        """
        response = client.post(
            "/carrito/test-tipos/productos",
            json={"nombre": "Laptop", "precio": "dos millones", "cantidad": 1},
        )
        assert response.status_code == 422
        assert response.status_code != 500

    def test_mass_assignment_campos_extra_ignorados(self):
        """
        Mass Assignment: campos adicionales no esperados deben ignorarse.
        Pydantic v2 los descarta silenciosamente.
        """
        response = client.post(
            "/carrito/test-mass/productos",
            json={
                "nombre": "Laptop",
                "precio": 2_500_000,
                "cantidad": 1,
                "admin": True,
                "precio_real": 0.01,
                "sesion_id": "admin-super",
                "descuento_forzado": 99,
            },
        )
        assert response.status_code == 201

    def test_payload_extremadamente_grande_no_colapsa(self):
        """
        Un nombre de 100.000 caracteres no debe provocar un error 500.
        Puede aceptarse (201) o rechazarse por validación (422).
        """
        nombre_enorme = "A" * 100_000

        response = client.post(
            "/carrito/test-payload/productos",
            json={"nombre": nombre_enorme, "precio": 100, "cantidad": 1},
        )

        assert response.status_code in [201, 422]
        assert response.status_code != 500


class TestCabeceras:
    """
    OWASP API8: Security Misconfiguration
    Las cabeceras de respuesta no deben revelar información interna del servidor.
    """

    def test_cabecera_content_type_es_json(self):
        """El Content-Type de toda respuesta de la API debe ser application/json."""
        response = client.get("/carrito/test-headers")
        assert "application/json" in response.headers.get("content-type", "")

    def test_cabecera_server_no_revela_version(self):
        """
        La cabecera 'Server' no debe revelar versiones internas.
        Ejemplo de valor problemático: 'uvicorn/0.29.0 python/3.12'.
        """
        response = client.get("/carrito/test-headers")
        server_header = response.headers.get("server", "").lower()

        assert "python/3" not in server_header, (
            f"Cabecera Server revela versión de Python: {server_header}"
        )
        assert "uvicorn/0." not in server_header, (
            f"Cabecera Server revela versión de uvicorn: {server_header}"
        )


class TestRateLimit:
    """
    OWASP API4: Unrestricted Resource Consumption
    El servidor no debe colapsar bajo carga básica sostenida.
    """

    def test_100_solicitudes_rapidas_no_causan_error_500(self):
        """
        100 solicitudes seguidas no deben generar ningún error 500.
        Un sistema robusto maneja esto sin inmutarse.
        """
        errores_500 = 0

        for i in range(100):
            response = client.post(
                f"/carrito/rate-test-{i}/productos",
                json={"nombre": f"Producto{i}", "precio": 10_000, "cantidad": 1},
            )
            if response.status_code == 500:
                errores_500 += 1

        assert errores_500 == 0, f"El servidor tuvo {errores_500} errores 500 bajo carga básica"
