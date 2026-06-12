# TiendaUV - Carrito de Compras

API REST para un sistema de carrito de compras construida con FastAPI y SQLAlchemy.
Implementa persistencia en PostgreSQL (produccion) o SQLite en memoria (desarrollo y tests rapidos).

## Estructura del proyecto

```
carrito-compras/
├── src/
│   ├── carrito/
│   │   ├── api.py          # Endpoints FastAPI
│   │   ├── carrito.py      # Logica de negocio (en memoria)
│   │   └── modelos.py      # Dataclasses de dominio
│   └── database/
│       ├── config.py       # Engine, sesion y get_db
│       ├── models.py       # Modelos SQLAlchemy (ORM)
│       └── repositorio.py  # Capa de acceso a datos
├── tests/
│   ├── features/           # Escenarios BDD (Gherkin + pytest-bdd)
│   ├── integration/        # Tests contra PostgreSQL real (TestContainers)
│   ├── performance/        # Pruebas de carga con Locust
│   ├── security/           # Tests OWASP API Security Top 10
│   ├── system/             # Tests E2E contra API desplegada
│   ├── test_carrito.py     # Tests unitarios TDD
│   ├── test_funcional.py   # Particion, valores limite, transicion de estados
│   └── test_tabla_decision.py
├── .github/workflows/
│   └── pipeline.yml        # Pipeline CI/CD en 4 jobs
├── docker-compose.yml      # Stack de produccion
├── docker-compose.test.yml # Stack de tests E2E
├── Dockerfile
└── Dockerfile.test
```

## Requisitos

- Python 3.12+
- uv (gestor de paquetes): https://docs.astral.sh/uv/
- Docker y Docker Compose (para tests de integracion, sistema y produccion)

## Instalacion

```bash
uv sync --dev
```

## Levantar con Docker

```bash
# Stack completo (API + PostgreSQL + Adminer)
docker compose up -d

# Ver logs
docker compose logs -f api

# Detener
docker compose down -v
```

La API queda disponible en http://localhost:8000
Adminer (cliente web de BD) en http://localhost:8080

## Comandos de prueba

### Tests rapidos (sin Docker, usan SQLite en memoria)

```bash
uv run pytest tests/test_carrito.py tests/features/ tests/test_funcional.py tests/test_tabla_decision.py tests/security/ -v
```

### Tests con cobertura

```bash
uv run pytest tests/test_carrito.py tests/features/ tests/test_funcional.py tests/test_tabla_decision.py tests/security/ --cov=src --cov-report=html
```

### Tests de integracion (requieren Docker)

```bash
uv run pytest tests/integration/ -v -m integration
```

TestContainers levanta un contenedor PostgreSQL automaticamente durante la ejecucion.

### Tests de sistema E2E (requieren stack levantado)

```bash
docker compose -f docker-compose.test.yml up -d --build
API_URL=http://localhost:8001 uv run pytest tests/system/ -v -m system
docker compose -f docker-compose.test.yml down -v
```

### Tests de rendimiento (Locust)

```bash
docker compose -f docker-compose.test.yml up -d --build
uv run locust -f tests/performance/locustfile.py --headless --users 50 --spawn-rate 10 --run-time 30s --host http://localhost:8001
docker compose -f docker-compose.test.yml down -v
```

## Inventario de tests

| Tipo           | Archivo(s)                                              | Cantidad |
|----------------|---------------------------------------------------------|----------|
| Unitarios TDD  | tests/test_carrito.py                                   | 21       |
| BDD Gherkin    | tests/features/test_carrito_bdd.py                      | 12       |
| Funcionales    | tests/test_funcional.py                                 | 34       |
| Tabla decision | tests/test_tabla_decision.py                            | 15       |
| Seguridad OWASP| tests/security/test_seguridad_api.py                    | 7        |
| **Subtotal rapidos** |                                                   | **89**   |
| Integracion    | tests/integration/test_repositorio_db.py (10)           | 16       |
|                | tests/integration/test_api_integracion.py (6)           |          |
| Sistema E2E    | tests/system/test_sistema_e2e.py                        | 6        |
| **Total**      |                                                         | **111**  |

## Pipeline CI/CD

El pipeline en `.github/workflows/pipeline.yml` tiene 4 jobs en cascada:

### Job 1: Tests Rapidos
Corre los 89 tests sin Docker usando SQLite en memoria. Incluye lint (ruff) y verificacion
de formato. Es la compuerta principal: si falla, no se ejecutan los jobs siguientes.
Genera reporte de cobertura con umbral minimo del 80%.

### Job 2: Tests de Integracion
Usa TestContainers para levantar un PostgreSQL real dentro del runner de GitHub Actions.
Verifica que el repositorio y la API interactuan correctamente con la base de datos.
Patron rollback: cada test revierte su transaccion al finalizar.

### Job 3: Tests de Sistema E2E
Levanta el stack completo con docker-compose.test.yml (PostgreSQL + API en puerto 8001).
Los tests en tests/system/ hacen peticiones HTTP reales contra la API desplegada.

### Job 4: Tests de Rendimiento (solo en push a main)
Ejecuta Locust con 50 usuarios durante 30 segundos y verifica los SLAs:
- Percentil 95 de tiempo de respuesta menor a 500ms
- Tasa de error menor al 1%
