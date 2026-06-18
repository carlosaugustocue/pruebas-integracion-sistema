# Carrito de Compras — TiendaUV

Sistema de carrito de compras construido como proyecto académico de la asignatura
**Pruebas de Software** (Semestre V, Ingeniería de Software). El proyecto evoluciona
semana a semana aplicando TDD, BDD, técnicas de diseño de pruebas, integración con
base de datos real y pipeline de CI/CD.

---

## Tabla de contenidos

1. [Descripción del sistema](#1-descripción-del-sistema)
2. [Estructura del proyecto](#2-estructura-del-proyecto)
3. [Arquitectura de capas](#3-arquitectura-de-capas)
4. [Requisitos](#4-requisitos)
5. [Instalación y configuración local](#5-instalación-y-configuración-local)
6. [Cómo levantar el proyecto con Docker](#6-cómo-levantar-el-proyecto-con-docker)
7. [Los dos Dockerfiles explicados](#7-los-dos-dockerfiles-explicados)
8. [Los dos Docker Compose explicados](#8-los-dos-docker-compose-explicados)
9. [Cómo funciona la base de datos](#9-cómo-funciona-la-base-de-datos)
10. [La API REST](#10-la-api-rest)
11. [Qué es TestContainers y cómo funciona](#11-qué-es-testcontainers-y-cómo-funciona)
12. [El archivo conftest.py explicado](#12-el-archivo-conftestpy-explicado)
13. [Inventario completo de pruebas](#13-inventario-completo-de-pruebas)
14. [Pruebas unitarias TDD](#14-pruebas-unitarias-tdd)
15. [Pruebas de aceptación BDD](#15-pruebas-de-aceptación-bdd)
16. [Pruebas funcionales con técnicas de diseño](#16-pruebas-funcionales-con-técnicas-de-diseño)
17. [Pruebas de tabla de decisión](#17-pruebas-de-tabla-de-decisión)
18. [Pruebas de seguridad OWASP](#18-pruebas-de-seguridad-owasp)
19. [Pruebas de integración con base de datos real](#19-pruebas-de-integración-con-base-de-datos-real)
20. [Pruebas de sistema E2E](#20-pruebas-de-sistema-e2e)
21. [Pruebas de rendimiento con Locust](#21-pruebas-de-rendimiento-con-locust)
22. [Cómo se conecta todo: trazabilidad completa de un test de integración](#22-cómo-se-conecta-todo-trazabilidad-completa-de-un-test-de-integración)
23. [Comandos de referencia rápida](#23-comandos-de-referencia-rápida)
24. [El pipeline de CI/CD](#24-el-pipeline-de-cicd)

---

## 1. Descripción del sistema

TiendaUV es una tienda en línea universitaria. El módulo que construimos es el
**carrito de compras**: el componente que permite a los usuarios agregar productos,
aplicar descuentos, calcular totales con IVA y vaciar el carrito.

El sistema tiene dos modos de operación:

- **Sin Docker (desarrollo y tests rápidos):** usa SQLite en memoria. La base de
  datos existe mientras corre el proceso y desaparece cuando termina. No necesitas
  instalar nada más que Python.

- **Con Docker (producción y tests de sistema):** usa PostgreSQL real. La base de
  datos persiste en un volumen de Docker y sobrevive reinicios del contenedor.

---

## 2. Estructura del proyecto

```
carrito-compras/
│
├── src/                              Código fuente de producción
│   ├── carrito/
│   │   ├── carrito.py                Lógica de negocio del carrito (sin BD)
│   │   ├── modelos.py                Dataclass Producto con validaciones
│   │   └── api.py                    API REST con FastAPI
│   ├── database/
│   │   ├── models.py                 Tablas de la BD (SQLAlchemy 2.x)
│   │   ├── config.py                 Conexión a la BD, fallback SQLite
│   │   └── repositorio.py            Operaciones de datos del carrito
│   └── envios/
│       └── calculadora_envio.py      Reglas de negocio de envíos
│
├── tests/                            Todas las pruebas del proyecto
│   ├── conftest.py                   Fixtures compartidos (TestContainers, BD)
│   ├── test_carrito.py               Pruebas unitarias TDD (21 tests)
│   ├── test_funcional.py             Equivalencia, límites, estados (29 tests)
│   ├── test_tabla_decision.py        Tabla de decisión envíos (15 tests)
│   ├── features/
│   │   ├── carrito.feature           Escenarios en lenguaje Gherkin
│   │   └── test_carrito_bdd.py       Definición de pasos BDD (12 tests)
│   ├── security/
│   │   └── test_seguridad_api.py     Pruebas OWASP Top 10 (11 tests)
│   ├── integration/
│   │   ├── test_repositorio_db.py    Repositorio vs PostgreSQL real (10 tests)
│   │   └── test_api_integracion.py   API vs PostgreSQL real (6 tests)
│   ├── system/
│   │   └── test_sistema_e2e.py       E2E contra la API desplegada (6 tests)
│   └── performance/
│       └── locustfile.py             Simulación de carga con Locust
│
├── Dockerfile                        Imagen de producción
├── Dockerfile.test                   Imagen para correr tests en contenedor
├── docker-compose.yml                Stack de desarrollo local
├── docker-compose.test.yml           Stack para tests E2E y CI/CD
├── .dockerignore                     Archivos que Docker no debe copiar
├── pyproject.toml                    Dependencias y configuración del proyecto
├── uv.lock                           Versiones exactas de dependencias (no editar)
└── .github/workflows/pipeline.yml   Pipeline de CI/CD en GitHub Actions
```

---

## 3. Arquitectura de capas

El sistema está organizado en capas. Cada capa tiene una responsabilidad única
y no conoce los detalles internos de las demás.

```
┌──────────────────────────────────────────────────────────┐
│  CAPA DE ENTRADA (src/carrito/api.py)                    │
│  FastAPI recibe peticiones HTTP, valida datos con        │
│  Pydantic y delega la lógica al repositorio.             │
└───────────────────────────┬──────────────────────────────┘
                            │ usa
┌───────────────────────────▼──────────────────────────────┐
│  CAPA DE REPOSITORIO (src/database/repositorio.py)       │
│  Contiene toda la lógica de negocio: agregar, eliminar,  │
│  calcular totales, aplicar descuentos. Habla con la      │
│  sesión de SQLAlchemy.                                   │
└───────────────────────────┬──────────────────────────────┘
                            │ usa
┌───────────────────────────▼──────────────────────────────┐
│  CAPA DE MODELOS (src/database/models.py)                │
│  Define la estructura de las tablas en la base de datos. │
│  CarritoDB e ItemCarritoDB mapean a filas de PostgreSQL. │
└───────────────────────────┬──────────────────────────────┘
                            │ conecta a
┌───────────────────────────▼──────────────────────────────┐
│  BASE DE DATOS                                           │
│  SQLite en memoria (tests sin Docker)                    │
│  PostgreSQL (desarrollo con Docker y producción)         │
└──────────────────────────────────────────────────────────┘
```

También existe `src/carrito/carrito.py` con la lógica original de las semanas 4 y 5,
que opera en memoria sin base de datos. Los tests unitarios y BDD usan esa clase
directamente, sin pasar por la API ni la BD.

---

## 4. Requisitos

- **Python 3.12 o superior**
- **uv** — gestor de paquetes y entornos virtuales
- **Docker Desktop** — solo para pruebas de integración/sistema y desarrollo con PostgreSQL

Instalar uv en Windows:
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Instalar uv en macOS/Linux:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## 5. Instalación y configuración local

```bash
# 1. Clonar el repositorio
git clone https://github.com/josealfredore2604/carrito-compras.git
cd carrito-compras

# 2. Instalar todas las dependencias (producción + desarrollo)
uv sync --dev

# 3. Verificar que pytest funciona
uv run pytest --version

# 4. Correr los tests rápidos (no necesitan Docker)
uv run pytest tests/test_carrito.py tests/features/ tests/test_funcional.py \
  tests/test_tabla_decision.py tests/security/ -v
```

El comando `uv sync --dev` hace lo siguiente:
1. Crea un entorno virtual en `.venv/` si no existe.
2. Lee `uv.lock` y descarga exactamente las versiones especificadas.
3. Instala tanto las dependencias de producción como las de desarrollo.

Si solo quieres las dependencias de producción (para el servidor):
```bash
uv sync --no-dev
```

---

## 6. Cómo levantar el proyecto con Docker

### Desarrollo local completo

Levanta PostgreSQL + la API + Adminer (interfaz web para ver la BD):

```bash
docker compose up -d
```

Con esto disponible:
- API: http://localhost:8000
- Documentación interactiva: http://localhost:8000/docs
- Adminer (ver tablas): http://localhost:8080
  - Sistema: PostgreSQL
  - Servidor: db
  - Usuario: tiendauv
  - Contraseña: tiendauv_pass
  - Base de datos: tiendauv

Verificar que la API responde:
```bash
curl http://localhost:8000/carrito/health-check
# Respuesta: {"status": "ok"}
```

Detener todo conservando los datos:
```bash
docker compose down
```

Detener todo y borrar los datos (el volumen de PostgreSQL):
```bash
docker compose down -v
```

### Stack de pruebas de sistema

Levanta PostgreSQL de prueba + la API en el puerto 8001:

```bash
docker compose -f docker-compose.test.yml up -d --build
```

Este stack usa una base de datos en memoria temporal (`tmpfs`), así que
los datos desaparecen cuando el contenedor para. Ideal para pruebas porque
garantiza estado limpio en cada ejecución.

Verificar:
```bash
curl http://localhost:8001/carrito/health-check
```

Detener y limpiar:
```bash
docker compose -f docker-compose.test.yml down -v
```

---

## 7. Los dos Dockerfiles explicados

### Dockerfile — imagen de producción

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
```
Parte de una imagen oficial que ya trae Python 3.12 y uv instalados.
`bookworm-slim` es Debian 12 reducido: solo lo esencial del sistema operativo,
sin editores, sin herramientas de compilación, lo que hace la imagen más pequeña
y más segura (menos software instalado = menos superficie de ataque).

```dockerfile
WORKDIR /app
```
Todos los comandos siguientes se ejecutan dentro de `/app`. También es el
directorio donde se copiará el código.

```dockerfile
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
```
Se copian primero **solo** los archivos de dependencias, sin el código fuente.
Esto aprovecha el sistema de caché por capas de Docker: si no cambian las
dependencias, Docker no vuelve a ejecutar `uv sync` en cada build. Solo cuando
cambia `pyproject.toml` o `uv.lock` se reinstalan dependencias.

`--frozen` significa "usa exactamente las versiones del `uv.lock`, sin
actualizar ninguna". `--no-dev` excluye pytest, ruff, testcontainers, etc.,
porque en producción no los necesitamos y solo aumentan el tamaño de la imagen.

```dockerfile
COPY src/ ./src/
```
El código fuente se copia después de las dependencias para no invalidar la
capa de dependencias del caché cuando cambias una línea de código.

```dockerfile
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "src.carrito.api:app", "--host", "0.0.0.0", "--port", "8000"]
```
`EXPOSE` documenta el puerto (no lo abre automáticamente; eso lo hace `-p` o
el `ports` del compose). `--host 0.0.0.0` es obligatorio dentro de Docker:
sin esto el servidor escucha solo en `localhost` interno del contenedor y no
es accesible desde el host ni desde otros contenedores.

### Dockerfile.test — imagen para correr tests

```dockerfile
RUN uv sync --frozen
```
La única diferencia con el Dockerfile de producción: no lleva `--no-dev`,
por lo que instala también pytest, ruff, testcontainers, etc.

```dockerfile
COPY . .
```
Copia todo el proyecto, incluyendo la carpeta `tests/`. El `.dockerignore`
excluye `.venv/`, `__pycache__/`, `.pytest_cache/`, etc.

```dockerfile
CMD ["uv", "run", "pytest", "tests/", "-v", "--tb=short",
     "--ignore=tests/system", "--ignore=tests/performance"]
```
Al ejecutar este contenedor, corre los tests unitarios, BDD, funcionales,
tabla de decisión, seguridad e integración. Excluye los de sistema (necesitan
la API corriendo externamente) y los de rendimiento (Locust, configuración aparte).

---

## 8. Los dos Docker Compose explicados

### docker-compose.yml — ambiente de desarrollo

#### Servicio `db`

```yaml
image: postgres:16-alpine
```
PostgreSQL 16 sobre Alpine Linux. La imagen Alpine pesa ~50MB vs ~400MB de
la imagen estándar de Debian. Para desarrollo es perfecta.

```yaml
environment:
  POSTGRES_USER: tiendauv
  POSTGRES_PASSWORD: tiendauv_pass
  POSTGRES_DB: tiendauv
```
Variables de entorno que PostgreSQL lee al arrancar por primera vez para
crear el usuario, la contraseña y la base de datos inicial. Son credenciales
de desarrollo local; nunca deben usarse en producción.

```yaml
volumes:
  - postgres_data:/var/lib/postgresql/data
```
Los datos de PostgreSQL se guardan en el volumen nombrado `postgres_data`,
que vive fuera del contenedor. Si haces `docker compose down` sin `-v`, el
contenedor desaparece pero los datos quedan. Con `docker compose down -v`
se borra también el volumen y los datos.

```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U tiendauv"]
  interval: 5s
  timeout: 5s
  retries: 5
```
Docker verifica cada 5 segundos si PostgreSQL acepta conexiones. `pg_isready`
es una herramienta incluida en PostgreSQL. Si falla 5 veces seguidas (25s en
total), el contenedor se marca "unhealthy" y la API no arrancará.

#### Servicio `api`

```yaml
build:
  context: .
  dockerfile: Dockerfile
environment:
  DATABASE_URL: postgresql://tiendauv:tiendauv_pass@db:5432/tiendauv
depends_on:
  db:
    condition: service_healthy
```
`context: .` indica que el Dockerfile está en la carpeta actual. En la
`DATABASE_URL`, el hostname es `db` (el nombre del servicio de PostgreSQL),
no `localhost`. Docker crea una red virtual donde los servicios se comunican
por nombre de servicio. `depends_on: condition: service_healthy` garantiza
que la API no arranca hasta que PostgreSQL haya pasado el healthcheck.

#### Servicio `adminer`

Adminer es una interfaz web liviana para administrar bases de datos. Permite
ver las tablas, hacer consultas SQL y exportar datos. Mucho más simple que
pgAdmin y no requiere configuración.

### docker-compose.test.yml — ambiente para tests E2E y CI/CD

La diferencia clave con el compose de desarrollo es:

```yaml
tmpfs:
  - /var/lib/postgresql/data
```
Los datos de PostgreSQL se almacenan en RAM en vez de en disco. Cuando el
contenedor para, todo se borra. Esto garantiza que cada vez que levantes el
stack de tests, la base de datos esté completamente limpia, sin datos de
ejecuciones anteriores.

```yaml
ports:
  - "5433:5432"   # PostgreSQL en puerto 5433 del host
  - "8001:8000"   # API en puerto 8001 del host
```
Usa puertos distintos al compose de desarrollo (5432 y 8000) para que
puedan coexistir sin conflicto si tienes ambos levantados al mismo tiempo.

---

## 9. Cómo funciona la base de datos

### Modelos SQLAlchemy (src/database/models.py)

SQLAlchemy es el ORM (Object-Relational Mapper) más usado en Python. Un ORM
te permite trabajar con la base de datos usando clases Python en vez de
escribir SQL a mano.

**CarritoDB** representa la tabla `carritos`:

| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | Integer PK | Identificador numérico autogenerado |
| sesion_id | String(100) | ID de sesión del usuario (único, indexado) |
| descuento_tipo | String(20) | "porcentaje" o "fijo", puede ser null |
| descuento_valor | Float | Valor del descuento activo |
| creado_en | DateTime | Cuándo se creó el carrito (automático) |
| actualizado_en | DateTime | Última modificación (automático) |

**ItemCarritoDB** representa la tabla `items_carrito`:

| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | Integer PK | Identificador autogenerado |
| carrito_id | Integer FK | Referencia al carrito al que pertenece |
| nombre | String(200) | Nombre del producto |
| precio | Float | Precio unitario (la BD rechaza valores <= 0) |
| cantidad | Integer | Unidades (la BD rechaza valores < 1) |

Los `CheckConstraint` en `__table_args__` son restricciones que PostgreSQL
aplica directamente a nivel de base de datos. Son una segunda capa de
validación: primero valida el repositorio Python, y si algo se salta esa
validación y llega a la BD, PostgreSQL también lo rechaza.

La relación `cascade="all, delete-orphan"` en `CarritoDB.items` significa
que si eliminas un carrito, sus items se eliminan automáticamente. No quedan
filas huérfanas en la tabla `items_carrito`.

### Configuración de conexión (src/database/config.py)

El archivo determina a qué base de datos conectarse según la variable de
entorno `DATABASE_URL`:

```
Sin DATABASE_URL definida:
  → sqlite:///:memory:  (SQLite en RAM, para tests sin Docker)

Con DATABASE_URL definida:
  → Lo que diga la URL (PostgreSQL en Docker o producción)
```

Para SQLite en memoria se usa `StaticPool`. Normalmente SQLAlchemy crea una
conexión nueva por cada sesión de BD. Con SQLite en memoria, cada conexión
nueva obtiene una base de datos vacía diferente (la BD vive atada a esa
conexión). `StaticPool` hace que todas las sesiones compartan la misma
conexión, por lo que todas ven los mismos datos. Sin esto, una sesión que
inserta un carrito y otra que lo busca no se verían entre sí.

La función `get_db` es la que FastAPI inyecta en cada endpoint:

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()   # si no hubo error, confirmar los cambios
    except Exception:
        db.rollback() # si hubo error, deshacer
        raise
    finally:
        db.close()    # siempre cerrar la sesión
```

`yield` convierte `get_db` en un generador. FastAPI abre la sesión antes
del endpoint, la inyecta como parámetro, y la cierra (con commit o rollback)
cuando el endpoint termina. Esto garantiza que cada petición HTTP tiene su
propia sesión aislada.

### El repositorio (src/database/repositorio.py)

`CarritoRepositorio` encapsula todas las operaciones de datos. Recibe una
sesión en el constructor y hace todo a través de ella.

Los métodos usan `session.flush()` en lugar de `session.commit()`. La
diferencia técnica:

- `flush()`: envía el SQL al motor de BD dentro de la transacción actual.
  Los cambios son visibles para consultas posteriores en la misma sesión,
  pero no están confirmados. Si luego hay un error, se pueden deshacer.

- `commit()`: confirma definitivamente. Los cambios son permanentes y
  visibles para cualquier conexión externa.

El repositorio usa `flush()` porque no es su responsabilidad decidir cuándo
confirmar. Esa decisión la toma `get_db` (en la API) o el fixture de test
(en las pruebas de integración).

---

## 10. La API REST

La API tiene 5 endpoints. En todos, `{sesion_id}` es un identificador libre
que el cliente elige para identificar su carrito (puede ser un UUID, un nombre,
cualquier string).

### GET /carrito/health-check

Verifica que el servidor está funcionando. Lo usa Docker en el healthcheck
y el pipeline de CI para saber cuándo la API está lista.

Respuesta: `{"status": "ok"}`

### POST /carrito/{sesion_id}/productos

Agrega un producto al carrito. Si el carrito no existe, lo crea automáticamente.
Si el producto ya existe (mismo nombre), suma la cantidad.

```json
{ "nombre": "Laptop", "precio": 2500000, "cantidad": 1 }
```

Respuestas:
- `201 Created`: producto agregado
- `422 Unprocessable Entity`: datos inválidos (precio <= 0, cantidad fuera de 1-99)

### GET /carrito/{sesion_id}

Estado completo del carrito. Si no existe, retorna total 0 y lista vacía (no falla con 404).

```json
{
  "sesion_id": "mi-sesion",
  "productos": [
    { "nombre": "Laptop", "precio": 2500000, "cantidad": 1, "subtotal": 2500000 }
  ],
  "total": 2500000,
  "total_con_iva": 2975000,
  "cantidad_productos": 1
}
```

### POST /carrito/{sesion_id}/descuento

Aplica un descuento. Un descuento nuevo reemplaza al anterior.

```json
{ "tipo": "porcentaje", "valor": 10 }
```
o
```json
{ "tipo": "fijo", "valor": 50000 }
```

### DELETE /carrito/{sesion_id}

Vacía el carrito: elimina los productos y resetea el descuento. El registro
del carrito en la BD queda vacío (no se elimina la fila).

---

## 11. Qué es TestContainers y cómo funciona

TestContainers es una librería Python que levanta contenedores Docker desde
el código de los tests. No necesitas hacer `docker compose up` antes de
correr las pruebas de integración.

La ventaja sobre mockear la base de datos: un mock de PostgreSQL simula su
comportamiento, pero esa simulación puede ser incorrecta o incompleta.
TestContainers te da una PostgreSQL real con sus constraints, tipos de datos,
comportamiento de transacciones y todo lo demás. Un test que pasa con
TestContainers garantiza que el código funciona contra una BD de producción real.

### Ciclo de vida durante pytest

```
uv run pytest tests/integration/ -v
    │
    ├── recolecta todos los tests
    │
    ├── primer test necesita db_session → necesita db_engine → necesita postgres_container
    │
    ├── postgres_container arranca (scope=session, una sola vez):
    │     docker run postgres:16-alpine
    │     espera healthcheck de PostgreSQL (~2-3 segundos)
    │
    ├── db_engine crea las tablas (scope=session, una sola vez):
    │     CREATE TABLE carritos
    │     CREATE TABLE items_carrito
    │
    ├── test_1 corre:
    │     db_session abre conexión + BEGIN TRANSACTION
    │     el test hace INSERT, SELECT, etc.
    │     db_session hace ROLLBACK → la BD queda como antes del test
    │
    ├── test_2 corre:
    │     db_session abre nueva conexión + BEGIN TRANSACTION
    │     el test corre sobre una BD limpia
    │     db_session hace ROLLBACK
    │
    └── [16 tests de integración corren así]
    │
    └── al terminar la sesión:
          DROP TABLE (limpieza)
          docker stop + docker rm
```

### Por qué el rollback es mejor que truncar tablas

Para que cada test encuentre la BD limpia se podría hacer `DELETE FROM carritos`
entre tests. El patrón de rollback es preferible por dos razones:

1. **Velocidad:** el rollback descarta operaciones en memoria sin escribir en
   disco. Un `DELETE` o `TRUNCATE` es una operación de escritura real.

2. **Atomicidad:** el rollback deshace exactamente lo que hizo el test, sin
   riesgo de que un test olvide limpiar algo. No importa cuántos INSERT, UPDATE
   o DELETE haya hecho el test; el rollback lo deshace todo de una vez.

---

## 12. El archivo conftest.py explicado

`tests/conftest.py` define fixtures que pytest pone disponibles para todos
los archivos de test del proyecto. Un fixture es código que pytest ejecuta
antes (y después) del test para preparar el contexto necesario.

```python
@pytest.fixture(scope="session")
def postgres_container():
    from testcontainers.postgres import PostgresContainer
    with PostgresContainer("postgres:16-alpine") as container:
        yield container
```

`scope="session"` hace que el fixture se cree una sola vez para toda la
sesión de pytest y se destruya al final. 16 tests comparten el mismo contenedor.

La importación de `PostgresContainer` está dentro de la función (import lazy),
no al inicio del archivo. Si importara al inicio, pytest intentaría importar
testcontainers cuando recolecta tests unitarios, aunque no vayan a correr tests
de integración. Con el import lazy, la librería solo se carga cuando se necesita.

```python
@pytest.fixture(scope="session")
def db_engine(postgres_container):
    url = postgres_container.get_connection_url()
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()
```

`get_connection_url()` retorna algo como
`postgresql+psycopg2://user:pass@localhost:49832/dbname`
(el puerto es aleatorio, asignado por Docker).

`Base.metadata.create_all(engine)` ejecuta todos los `CREATE TABLE` definidos
en `models.py`. Al terminar la sesión, `drop_all` elimina las tablas (limpieza).

```python
@pytest.fixture(scope="function")
def db_session(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()
```

`scope="function"` crea una sesión nueva por cada test. La sesión está atada
a una conexión con una transacción abierta. Cuando el test termina, el rollback
deshace todo lo que hizo y la conexión se cierra.

```python
@pytest.fixture(scope="function")
def client_con_bd(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
```

`dependency_overrides` es una característica de FastAPI para reemplazar
dependencias en tests. Normalmente `get_db` crea una sesión nueva desde
`SessionLocal`. Aquí se reemplaza con la sesión del test. Así, cuando la
API hace un INSERT y el test luego busca esa fila directamente en `db_session`,
están en la misma transacción y el test ve los datos sin que se haya hecho commit.

Sin esto, la API insertaría en una transacción y el test buscaría en otra,
sin encontrar nada porque los datos no se habrían confirmado.

---

## 13. Inventario completo de pruebas

| Archivo | Tipo | Tests | Requiere |
|---------|------|-------|----------|
| tests/test_carrito.py | Unitarios TDD | 21 | Nada |
| tests/features/ | Aceptación BDD | 12 | Nada |
| tests/test_funcional.py | Funcionales | 29 | Nada |
| tests/test_tabla_decision.py | Tabla de decisión | 15 | Nada |
| tests/security/ | Seguridad OWASP | 11 | Nada |
| tests/integration/test_repositorio_db.py | Integración | 10 | Docker (TestContainers) |
| tests/integration/test_api_integracion.py | Integración | 6 | Docker (TestContainers) |
| tests/system/test_sistema_e2e.py | Sistema E2E | 6 | API corriendo en API_URL |
| **Total** | | **110** | |

Los tests de rendimiento (Locust) no tienen un conteo fijo de tests; simulan
usuarios durante un tiempo determinado y verifican métricas de latencia.

---

## 14. Pruebas unitarias TDD

**Archivo:** `tests/test_carrito.py`
**Clase bajo prueba:** `src/carrito/carrito.py` — clase `Carrito`

Estas pruebas se escribieron **antes** del código de producción aplicando TDD
(Test-Driven Development). El ciclo es: escribir el test que falla (Red),
escribir el código mínimo para que pase (Green), mejorar sin romper (Refactor).

La clase `Carrito` opera en memoria, sin base de datos. Es la lógica de negocio
pura, testeable sin ninguna infraestructura.

| Test | Qué verifica |
|------|-------------|
| test_carrito_inicia_vacio | Un Carrito nuevo tiene 0 productos y total = 0 |
| test_agregar_un_producto | Después de agregar, el producto aparece en obtener_productos() con nombre, precio y cantidad correctos |
| test_agregar_multiples_productos | El carrito puede contener varios productos distintos |
| test_agregar_producto_existente_suma_cantidad | Agregar "Laptop" dos veces deja 1 entrada con la cantidad sumada |
| test_eliminar_producto | El producto desaparece del carrito tras eliminarlo |
| test_eliminar_producto_inexistente_lanza_error | Eliminar algo que no existe lanza ValueError con "no se encuentra" |
| test_total_carrito_vacio | El total de un carrito sin productos es 0 |
| test_total_con_un_producto | Total = precio × cantidad |
| test_total_con_multiples_productos | Total = suma de todos los subtotales individuales |
| test_descuento_porcentaje | 10% sobre $1M = $900k |
| test_descuento_fijo | Descuento fijo de $150k sobre $1M = $850k |
| test_descuento_fijo_no_genera_total_negativo | Si el descuento fijo supera el total, el resultado es 0 (no negativo) |
| test_descuento_porcentaje_invalido | Porcentaje > 100 o negativo lanza ValueError |
| test_agregar_producto_respetando_stock | Con stock definido, se pueden agregar las unidades disponibles |
| test_agregar_producto_sin_stock_suficiente | Solicitar más unidades de las disponibles lanza ValueError |
| test_agregar_producto_que_no_existe_en_stock | Agregar un producto que no está en el stock definido lanza ValueError |
| test_total_con_iva | $1M × 1.19 = $1.19M con la tasa por defecto de 19% |
| test_total_con_iva_y_descuento | El IVA se aplica sobre el total ya descontado, no antes del descuento |
| test_total_con_iva_personalizado | Se puede pasar una tasa diferente al 19% (ejemplo: 5%) |
| test_vaciar_carrito | vaciar() deja el carrito en estado inicial: 0 productos, total 0 |
| test_carrito_con_multiples_descuentos_aplica_el_ultimo | Aplicar un segundo descuento reemplaza al primero; no se acumulan |

---

## 15. Pruebas de aceptación BDD

**Archivos:** `tests/features/carrito.feature` y `tests/features/test_carrito_bdd.py`
**Framework:** pytest-bdd

BDD (Behavior-Driven Development) escribe los criterios de aceptación en
lenguaje natural estructurado (Gherkin: Given/When/Then). El cliente puede
leer un escenario y confirmar si es lo que quería. Si el test pasa, el
criterio está cumplido; si falla, el comportamiento del sistema difiere de
lo que el cliente pidió.

Los escenarios tienen marcadores (`@smoke`, `@critical`, `@regression`) para
ejecutar subconjuntos específicos:

- `@smoke`: tests mínimos. Si fallan, algo fundamental del sistema está roto.
- `@critical`: flujos de negocio esenciales.
- `@regression`: comportamientos específicos que son sutiles o que alguna vez fallaron.

| Escenario | Marcas | Qué verifica |
|-----------|--------|-------------|
| Agregar un producto al carrito vacío | smoke, critical | Flujo más básico del carrito |
| Agregar múltiples productos diferentes | smoke | El carrito maneja varios productos |
| Agregar el mismo producto dos veces suma cantidades | regression | Comportamiento de acumulación de cantidades |
| Eliminar un producto del carrito | smoke | El producto desaparece correctamente |
| Calcular el total del carrito | critical | $2.5M × 1 + $85k × 2 = $2.67M |
| Aplicar descuento porcentaje 10% | critical | $1M − 10% = $900k |
| Aplicar descuento porcentaje 50% | critical | $1M − 50% = $500k |
| Aplicar descuento fijo $150k | critical | $1M − $150k = $850k |
| Aplicar descuento fijo $0 | critical | Descuento 0 no altera el total |
| Calcular total con IVA del 19% | critical | $1M × 1.19 = $1.19M |
| No agregar producto sin stock suficiente | regression | La validación de stock funciona |
| Vaciar el carrito elimina todo | smoke | Después de vaciar: 0 productos, total = 0 |

---

## 16. Pruebas funcionales con técnicas de diseño

**Archivo:** `tests/test_funcional.py`

Estas pruebas aplican técnicas sistemáticas para elegir qué valores probar,
maximizando la cobertura de defectos con el mínimo número de casos.

### Partición de equivalencia

Si el sistema se comporta igual para todos los valores de un rango, basta
con probar un representativo por rango. Para el campo `cantidad` (válido: 1-99):

| Partición | Rango | Representativo | Resultado esperado |
|-----------|-------|----------------|-------------------|
| Inválida baja | ≤ 0 | -3 | ValueError |
| Válida | 1 a 99 | 50 | OK |
| Inválida alta | ≥ 100 | 500 | ValueError |

`TestParticionEquivalenciaCantidad` tiene 4 tests (uno por representativo + cero).
El `@pytest.mark.parametrize` agrega 7 casos para mayor cobertura: -3, 0, 1, 50, 99, 100, 500.

### Análisis de valores límite

Los bugs "off-by-one" (`>` vs `>=`) solo se detectan probando el valor exacto
del límite. Para descuento porcentual (válido: 0% a 100%), los 6 valores críticos:

| Valor | Posición | Resultado esperado |
|-------|----------|--------------------|
| -0.1 | Justo fuera del límite inferior | ValueError |
| 0 | Límite inferior exacto | OK, sin descuento |
| 0.1 | Justo dentro del límite inferior | OK |
| 99.9 | Justo dentro del límite superior | OK |
| 100 | Límite superior exacto | OK, total = 0 |
| 100.1 | Justo fuera del límite superior | ValueError |

`TestValoresLimiteDescuento` tiene 6 tests (uno por cada valor). El
`@pytest.mark.parametrize` final cubre los mismos 6 valores de forma compacta.

### Transición de estados

El carrito tiene estados implícitos: VACÍO → CON ITEMS → CON DESCUENTO → VACÍO.

`TestTransicionesValidas` verifica 6 transiciones correctas:
el estado inicial, agregar un producto, aplicar un descuento, eliminar el
último producto, vaciar desde estado con descuento, y que el descuento persiste
al agregar más productos.

`TestTransicionesInvalidas` verifica 3 transiciones que deben fallar:
eliminar un producto que no existe, aplicar un descuento inválido, y vaciar
un carrito ya vacío (debe ser idempotente, no lanzar error).

---

## 17. Pruebas de tabla de decisión

**Archivo:** `tests/test_tabla_decision.py`
**Clase bajo prueba:** `src/envios/calculadora_envio.py`

Las tablas de decisión mapean todas las combinaciones posibles de condiciones
a una acción. Para el sistema de envíos hay 2 condiciones binarias (4 combinaciones):

| ¿Es premium? | Total > $500k? | Tipo de envío resultante |
|:---:|:---:|:---:|
| SÍ | SÍ | express gratis |
| SÍ | NO | normal gratis |
| NO | SÍ | normal gratis |
| NO | NO | cliente paga |

`TestTablaDecisionEnvios` tiene un test por columna de la tabla (4 tests),
más 2 tests para el valor límite exacto del umbral ($500.000) y 1 test de
guardia para total negativo.

El `@pytest.mark.parametrize` final cubre las mismas 4 columnas más 4 casos
de borde alrededor del umbral ($500.000 exacto, $500.001).

---

## 18. Pruebas de seguridad OWASP

**Archivo:** `tests/security/test_seguridad_api.py`
**Referencia:** OWASP API Security Top 10 (2023)

Estas pruebas verifican que la API no tiene vulnerabilidades básicas conocidas.
No reemplazan una auditoría de seguridad profesional, pero detectan los problemas
más comunes de forma automática en cada commit.

Usan `TestClient` de FastAPI directamente, sin Docker. La API usa SQLite en
memoria como fallback automático cuando no hay `DATABASE_URL`.

### TestInyeccion

| Test | Vulnerabilidad que busca | Cómo | Resultado esperado |
|------|------------------------|------|-------------------|
| test_sql_injection_en_nombre_no_causa_error_500 | OWASP API8 / SQL Injection | Envía `Laptop'; DROP TABLE productos; --` como nombre del producto | Status 201 o 422, **nunca 500**. Un 500 indicaría que el string fue interpretado como SQL |
| test_xss_en_nombre_se_almacena_como_texto | OWASP API8 / XSS | Envía `<script>document.cookie='stolen'</script>` como nombre | El string se guarda literalmente. Luego el GET verifica que ese string exacto está en la lista de productos, sin modificar |
| test_integer_overflow_no_colapsa_servidor | OWASP API8 / Injection | Envía precio = 10^308 (número gigante) | Status 201 o 422, **nunca 500**. Los servidores mal implementados pueden fallar con números extremos |

La API está protegida contra SQL Injection porque SQLAlchemy usa consultas
preparadas (parameterized queries): los datos del usuario nunca se concatenan
en el SQL, siempre van como parámetros separados.

### TestValidacionEntradas

| Test | Vulnerabilidad que busca | Cómo | Resultado esperado |
|------|------------------------|------|-------------------|
| test_tipos_de_datos_incorrectos_son_rechazados | OWASP API8 / Security Misconfiguration | Envía precio como string `"dos millones"` en vez de número | Status 422 (Pydantic rechaza el tipo incorrecto), nunca 500 |
| test_mass_assignment_campos_extra_ignorados | OWASP API3 / Mass Assignment | Envía campos extra: `admin: true`, `precio_real: 0.01`, `descuento_forzado: 99` | Status 201; los campos extra se ignoran completamente. Pydantic descarta lo que no está declarado en el modelo |
| test_payload_extremadamente_grande_no_colapsa | OWASP API4 / Resource Consumption | Envía nombre de 100.000 caracteres | Status 201 o 422, nunca 500. Un servidor vulnerable podría consumir demasiada memoria |

### TestCabeceras

| Test | Qué verifica |
|------|-------------|
| test_cabecera_content_type_es_json | Toda respuesta incluye `Content-Type: application/json` |
| test_cabecera_server_no_revela_version | La cabecera `Server` no expone versiones como `uvicorn/0.29 python/3.12`. Revelar versiones ayuda a atacantes a buscar CVEs específicos |

### TestRateLimit

| Test | Qué hace |
|------|----------|
| test_100_solicitudes_rapidas_no_causan_error_500 | Hace 100 POST consecutivos a 100 URLs distintas. Cuenta cuántos dan status 500. El resultado debe ser 0 |

Este test verifica que el servidor no se degrada ni falla bajo carga básica
sostenida. Un sistema bien implementado maneja este volumen sin pestañear.

---

## 19. Pruebas de integración con base de datos real

**Archivos:** `tests/integration/test_repositorio_db.py` y `test_api_integracion.py`
**Requisito:** Docker corriendo (TestContainers lo gestiona automáticamente)
**Fixtures:** `db_session` y `client_con_bd` del conftest.py

### test_repositorio_db.py — el repositorio contra PostgreSQL

Estas pruebas llaman a `CarritoRepositorio` directamente, sin HTTP. Verifican
que las operaciones de base de datos funcionan correctamente.

| Test | Qué hace | Qué verifica en la BD |
|------|----------|-----------------------|
| test_crear_carrito_nuevo_en_bd | `obtener_o_crear("int-1")` | Hay exactamente 1 fila en `carritos` con ese `sesion_id` |
| test_obtener_carrito_existente_no_duplica | `obtener_o_crear` dos veces con el mismo ID | Sigue habiendo 1 fila, no 2 |
| test_agregar_item_persiste_en_bd | `agregar_item(...)` | El item retornado tiene ID (fue guardado); el carrito tiene 1 item |
| test_agregar_item_existente_suma_cantidad | "Laptop" x1 luego "Laptop" x3 | 1 fila en `items_carrito` con cantidad = 4 |
| test_calcular_total_con_items_en_bd | Laptop $2.5M x1 + Mouse $85k x2 | `calcular_total` retorna $2.67M |
| test_descuento_persiste_en_bd | `aplicar_descuento("porcentaje", 10)` | La fila en BD tiene `descuento_tipo="porcentaje"` y `descuento_valor=10.0`; total = $900k |
| test_vaciar_carrito_elimina_items_de_bd | `vaciar(...)` | `carrito.items` está vacío, pero el `CarritoDB` sigue existiendo con su ID |
| test_precio_invalido_no_se_guarda | `agregar_item` con precio -100 | Lanza ValueError Y el contador de filas en `items_carrito` es 0 |
| test_total_carrito_inexistente_es_cero | `calcular_total` con sesion_id que no existe | Retorna 0.0, no lanza excepción |
| test_rollback_en_error_no_corrompe_estado | Item válido + item con precio inválido | El item válido sigue en BD después del error en el segundo insert |

### test_api_integracion.py — la API + repositorio + BD juntos

Estos tests usan `client_con_bd`: la sesión del test se inyecta en la API.
Pueden hacer peticiones HTTP y al mismo tiempo verificar la BD directamente.

| Test | Flujo del test |
|------|----------------|
| test_post_producto_persiste_en_bd | POST via API → buscar el item directamente en `db_session` → está ahí |
| test_get_carrito_lee_datos_reales_de_bd | Insertar `CarritoDB` + `ItemCarritoDB` directamente en `db_session` → GET via API → la API lo muestra |
| test_estado_persiste_entre_requests | POST producto 1 → POST producto 2 → GET → la respuesta tiene 2 productos |
| test_descuento_persiste_y_afecta_total | POST producto $1M → POST descuento 10% → GET → total = $900k |
| test_vaciar_elimina_todo_de_bd | POST producto → DELETE via API → contar filas en `items_carrito` → 0 |
| test_estructura_respuesta_es_correcta | GET de carrito nuevo → verificar que la respuesta tiene todos los campos: `sesion_id`, `productos`, `total`, `total_con_iva`, `cantidad_productos` |

El test `test_get_carrito_lee_datos_reales_de_bd` es especialmente importante
porque verifica el flujo inverso: insertar en BD sin pasar por la API, y luego
verificar que la API lo lee correctamente. Esto confirma que el ORM mapea bien
los datos de la BD al JSON de respuesta.

---

## 20. Pruebas de sistema E2E

**Archivo:** `tests/system/test_sistema_e2e.py`
**Requisito:** API corriendo en `API_URL` (por defecto `http://localhost:8000`)

Las pruebas de sistema actúan exactamente como un usuario real: hacen peticiones
HTTP a través de la red, sin acceso a objetos internos, sin acceso directo a la
BD. Verifican el sistema completo desde el exterior.

Cada test genera un `sesion_id` con UUID único (`e2e-a3f9b2c1`) para evitar
que los tests interfieran entre sí aunque la BD sea persistente entre pruebas.

| Test | Escenario completo |
|------|-------------------|
| test_health_check_sistema | GET /carrito/health-check → status 200 con `{"status": "ok"}` |
| test_flujo_compra_normal_completo | POST Laptop + POST Mouse → GET → total = $2.67M, 2 productos |
| test_flujo_con_descuento_porcentaje | POST Laptop $1M → POST descuento 15% → GET → total=$850k, total_con_iva=$1.0115M |
| test_sesiones_independientes | Sesión A con Laptop, Sesión B con Mouse → DELETE A → A tiene total 0, B sigue con $85k |
| test_mismo_producto_dos_veces_suma | POST Laptop x1 → POST Laptop x2 → GET → 1 producto con cantidad=3 |
| test_sistema_responde_en_menos_de_500ms | Mide tiempo de un GET → debe ser < 500ms |

El test de tiempo de respuesta verifica que la API no tiene problemas de
rendimiento estructurales (por ejemplo, consultas sin índice que demoren
varios segundos para un carrito simple).

Para correr localmente:
```bash
# Con el compose de desarrollo (API en puerto 8000)
docker compose up -d

# Esperar que arranque (~10 segundos)
curl http://localhost:8000/carrito/health-check

# Correr los tests
API_URL=http://localhost:8000 uv run pytest tests/system/ -v -m system
docker compose down
```

---

## 21. Pruebas de rendimiento con Locust

**Archivo:** `tests/performance/locustfile.py`
**Herramienta:** Locust 2.x

Locust simula múltiples usuarios virtuales haciendo peticiones simultáneas
a la API. No usa pytest; tiene su propio ejecutable (`locust`).

### Los dos tipos de usuario simulados

**UsuarioNormal** (peso 3 — por cada usuario premium hay 3 normales):
- Espera entre 1 y 3 segundos entre acciones (simula comportamiento humano)
- Tareas con su frecuencia relativa (peso):
  - Agrega producto aleatorio del catálogo (6 opciones) → peso 3 (más frecuente)
  - Consulta el carrito → peso 2
  - Aplica cupón de descuento → peso 1
  - Abandona el carrito (DELETE) → peso 1

**UsuarioPremium** (peso 1):
- Espera entre 0.5 y 1 segundo (compra más rápido)
- Agrega Laptop + Monitor y consulta el total en secuencia

### Los SLAs que verifica el pipeline

- **P95 < 500ms:** el percentil 95 de los tiempos de respuesta debe ser menor a 500ms
- **Tasa de error < 1%:** menos del 1% de las peticiones puede retornar error

El P95 es mejor métrica que el promedio: si 95 usuarios de 100 reciben
respuesta en 50ms pero 5 esperan 10 segundos, el promedio dice ~545ms
(parece aceptable), pero el P95 dice 50ms y el P99 dice 10.000ms, revelando
que 1 de cada 20 usuarios tiene una experiencia terrible.

### Cómo correr Locust

Con interfaz web (puedes configurar la carga en tiempo real):
```bash
# La API debe estar corriendo (con Docker o manualmente)
uv run locust -f tests/performance/locustfile.py --host http://localhost:8000
# Abrir en el navegador: http://localhost:8089
# Configurar: 50 usuarios, 10 usuarios/segundo
# Click en "Start"
```

Headless (sin interfaz, como en CI):
```bash
uv run locust \
  -f tests/performance/locustfile.py \
  --headless \
  --users 50 \
  --spawn-rate 10 \
  --run-time 30s \
  --host http://localhost:8000 \
  --csv reports/locust/resultados \
  --html reports/locust/reporte.html
```

Los archivos CSV generados tienen las estadísticas por endpoint. El HTML
tiene gráficas de tiempo de respuesta y tasa de peticiones en el tiempo.

---

## 22. Cómo se conecta todo: trazabilidad completa de un test de integración

Esta sección responde exactamente: ¿qué archivo llama a qué cosa, quién activa
TestContainers, de dónde viene `client_con_bd`, cómo llega la sesión de BD
hasta el test?

Se trazará paso a paso la ejecución de este test concreto:

```python
# tests/integration/test_api_integracion.py

def test_post_producto_persiste_en_bd(self, client_con_bd, db_session):
    client_con_bd.post(
        "/carrito/api-1/productos",
        json={"nombre": "Laptop", "precio": 2_500_000, "cantidad": 1},
    )
    item = (
        db_session.query(ItemCarritoDB)
        .join(CarritoDB)
        .filter(CarritoDB.sesion_id == "api-1")
        .first()
    )
    assert item is not None
    assert item.nombre == "Laptop"
```

---

### Paso 1 — Tú ejecutas el comando

```bash
uv run pytest tests/integration/ -v
```

pytest arranca. Lo primero que hace es **recolectar** todos los tests:
lee todos los archivos `test_*.py` dentro de `tests/integration/` y
los registra. Todavía no corre nada.

---

### Paso 2 — pytest lee tests/conftest.py

Antes de correr cualquier test, pytest busca archivos `conftest.py` en la
carpeta del test y en todas las carpetas padre. Encuentra:

```
tests/conftest.py
```

pytest registra los fixtures que están ahí definidos:
`postgres_container`, `db_engine`, `db_session`, `client_con_bd`.
Los registra pero **todavía no los ejecuta**. Los fixtures son lazy:
solo se instancian cuando un test los pide.

---

### Paso 3 — pytest analiza las dependencias del test

pytest ve que `test_post_producto_persiste_en_bd` necesita dos argumentos:
`client_con_bd` y `db_session`. Los busca en los fixtures registrados y
construye un árbol de dependencias:

```
test_post_producto_persiste_en_bd
    ├── client_con_bd         (definido en tests/conftest.py)
    │       └── db_session    (client_con_bd lo necesita)
    │               └── db_engine   (db_session lo necesita)
    │                       └── postgres_container  (db_engine lo necesita)
    └── db_session            (el mismo que ya está en la cadena de arriba)
```

pytest resuelve los duplicados: `db_session` aparece dos veces pero es el
mismo fixture, se instancia una sola vez por test.

---

### Paso 4 — pytest instancia postgres_container (AQUÍ arranca TestContainers)

Es la primera vez en la sesión que un test pide `postgres_container`.
Como tiene `scope="session"`, pytest lo instancia ahora y lo reutilizará
para todos los tests de la sesión.

```python
# tests/conftest.py — línea 11-18

@pytest.fixture(scope="session")
def postgres_container():
    from testcontainers.postgres import PostgresContainer  # se importa aquí

    with PostgresContainer("postgres:16-alpine") as container:
        yield container
```

`PostgresContainer("postgres:16-alpine")` le dice a TestContainers qué
imagen usar. Al entrar en el bloque `with`, TestContainers hace internamente:

```
1. docker pull postgres:16-alpine   (si no está en caché local)
2. docker run -d \
     -e POSTGRES_DB=test \
     -e POSTGRES_USER=test \
     -e POSTGRES_PASSWORD=test \
     -p {puerto_aleatorio}:5432 \
     postgres:16-alpine
3. Espera hasta que pg_isready responda (healthcheck interno)
4. Retorna el objeto container con la URL de conexión
```

El puerto en el host es **aleatorio** (ejemplo: 49832). TestContainers
lo elige para evitar conflictos con otros PostgreSQL que puedas tener corriendo.

En este punto existe un proceso PostgreSQL real corriendo en tu máquina,
dentro de un contenedor Docker, esperando conexiones en `localhost:49832`.

El `yield container` pausa la ejecución del fixture y entrega el objeto
`container` a quien lo pidió (el siguiente fixture en la cadena). El código
después del `yield` (la destrucción del contenedor) solo corre cuando pytest
termina toda la sesión.

---

### Paso 5 — pytest instancia db_engine

```python
# tests/conftest.py — línea 21-28

@pytest.fixture(scope="session")
def db_engine(postgres_container):
    url = postgres_container.get_connection_url()
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()
```

`postgres_container.get_connection_url()` retorna algo como:
```
postgresql+psycopg2://test:test@localhost:49832/test
```

`create_engine(url)` crea el motor SQLAlchemy. No abre conexiones todavía;
solo prepara la configuración de cómo conectarse.

`Base.metadata.create_all(engine)` sí abre una conexión y ejecuta:
```sql
CREATE TABLE IF NOT EXISTS carritos (
    id SERIAL PRIMARY KEY,
    sesion_id VARCHAR(100) UNIQUE NOT NULL,
    ...
);
CREATE TABLE IF NOT EXISTS items_carrito (
    id SERIAL PRIMARY KEY,
    carrito_id INTEGER REFERENCES carritos(id) ON DELETE CASCADE,
    ...
);
```

`Base` viene de `src/database/models.py`. El `metadata` contiene la
definición de todas las tablas que heredan de `Base`. `create_all` lee
esas definiciones y las traduce a SQL.

También es `scope="session"`: las tablas se crean una vez y persisten
para todos los tests. Se limpian con `drop_all` al final de la sesión.

---

### Paso 6 — pytest instancia db_session (una por test)

```python
# tests/conftest.py — línea 31-42

@pytest.fixture(scope="function")
def db_session(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()
```

`scope="function"` significa que esto se ejecuta para cada test.

`db_engine.connect()` abre una conexión real a PostgreSQL (el contenedor
que levantamos en el paso 4).

`connection.begin()` inicia una transacción en esa conexión. A partir de
aquí, todo lo que haga sobre esa conexión está dentro de la transacción y
puede deshacerse.

`sessionmaker(bind=connection)` crea una fábrica de sesiones SQLAlchemy
atada a esa conexión específica (no al engine general). Esto es importante:
la sesión usará siempre esa misma conexión, con la transacción abierta.

`Session()` crea la sesión. Es el objeto que se entrega al test como
`db_session`.

El `yield session` pausa el fixture y entrega la sesión. El test corre.
Cuando el test termina (pase o falle), el código después del `yield` se ejecuta:
`transaction.rollback()` deshace todo lo que hizo el test. La BD queda
exactamente como estaba antes de que el test empezara.

---

### Paso 7 — pytest instancia client_con_bd

```python
# tests/conftest.py — línea 45-55

@pytest.fixture(scope="function")
def client_con_bd(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
```

Este fixture necesita `db_session`, que pytest ya instanció en el paso 6.

`get_db` es la función definida en `src/database/config.py`:

```python
# src/database/config.py

def get_db():
    db = SessionLocal()   # crea sesión nueva desde el pool
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

Normalmente, cuando FastAPI recibe un request, llama a `get_db()` para
obtener una sesión. Esa sesión viene de `SessionLocal`, que crea una conexión
nueva y tiene su propia transacción separada.

`app.dependency_overrides[get_db] = override_get_db` le dice a FastAPI:
"cuando alguien pida `get_db`, en vez de llamar a la función original,
llama a `override_get_db`". `override_get_db` retorna la `db_session` del test.

El resultado: cuando la API procese el POST del test, obtendrá la misma
sesión que el test tiene en `db_session`. Misma conexión. Misma transacción.

`TestClient(app)` crea el cliente de pruebas de FastAPI/Starlette. Este
cliente no abre un puerto de red. Llama a la app ASGI directamente en memoria,
dentro del mismo proceso Python.

---

### Paso 8 — El test corre

```python
def test_post_producto_persiste_en_bd(self, client_con_bd, db_session):
    client_con_bd.post(
        "/carrito/api-1/productos",
        json={"nombre": "Laptop", "precio": 2_500_000, "cantidad": 1},
    )
```

`client_con_bd.post(...)` construye una petición HTTP sintética y la envía
directamente a la app FastAPI en memoria. No hay socket. No hay TCP.

FastAPI recibe la petición y la enruta al endpoint:

```python
# src/carrito/api.py

@app.post("/carrito/{sesion_id}/productos", status_code=201)
def agregar_producto(sesion_id: str, producto: ProductoInput, db: Session = Depends(get_db)):
    repo = CarritoRepositorio(db)
    ...
```

El `Depends(get_db)` normalmente llamaría a `get_db()` de `config.py`.
Pero como aplicamos `dependency_overrides`, FastAPI llama a `override_get_db()`
del conftest, que retorna la `db_session` del test.

`CarritoRepositorio(db)` recibe esa sesión. Cuando llama a `session.flush()`,
los SQL van a la conexión del test, dentro de su transacción abierta.

```python
    item = (
        db_session.query(ItemCarritoDB)
        .join(CarritoDB)
        .filter(CarritoDB.sesion_id == "api-1")
        .first()
    )
    assert item is not None
```

El test ahora consulta directamente en `db_session`. Como es la misma
conexión que usó la API, el `SELECT` ve el item que se insertó con `flush()`,
aunque no se haya hecho `commit()`. Dentro de la misma transacción, puedes
leer tus propios cambios pendientes.

---

### Paso 9 — El test termina, el fixture limpia

El test termina (pasó el assert). pytest vuelve al fixture `db_session`
y ejecuta el código después del `yield`:

```python
    session.close()
    transaction.rollback()   # ← deshace el INSERT que hizo el test
    connection.close()
```

El `CarritoDB` y el `ItemCarritoDB` que insertó la API desaparecen de la BD.
El siguiente test encontrará la base de datos exactamente vacía.

También limpia `client_con_bd`:
```python
    app.dependency_overrides.clear()   # ← la API vuelve a usar get_db original
```

---

### El mapa completo de archivos y su rol

```
uv run pytest tests/integration/
        │
        │ pytest lee
        ▼
tests/conftest.py               ← define los 4 fixtures
        │
        │ fixture postgres_container activa
        ▼
testcontainers (librería)       ← habla con Docker daemon
        │
        │ Docker levanta
        ▼
postgres:16-alpine (contenedor) ← BD real corriendo en localhost:XXXXX
        │
        │ fixture db_engine se conecta y ejecuta
        ▼
src/database/models.py          ← Base.metadata → CREATE TABLE
        │
        │ fixture db_session abre
        ▼
Transacción abierta en la BD    ← todo lo que haga el test va aquí
        │
        │ fixture client_con_bd registra
        ▼
app.dependency_overrides        ← FastAPI usará la sesión del test
        │
        │ el test llama
        ▼
TestClient(app)                 ← llamada en memoria, no hay red
        │
        │ FastAPI enruta al endpoint que llama
        ▼
src/database/repositorio.py     ← usa la sesión del test → INSERT
        │
        │ el test verifica con
        ▼
db_session.query(...)           ← misma sesión → ve el INSERT
        │
        │ test termina → fixture db_session ejecuta
        ▼
transaction.rollback()          ← el INSERT desaparece
```

---

### Por qué los tests de sistema son distintos

En los tests de sistema (`tests/system/test_sistema_e2e.py`) no hay
`dependency_overrides`, no hay `conftest.py` con fixtures de BD, no hay
TestContainers. Solo hay:

```python
httpx.Client(base_url="http://localhost:8001")
```

Eso es un cliente HTTP real que abre un socket TCP hacia el contenedor Docker
donde corre la API. La API está en un proceso completamente separado con su
propio `get_db`, su propia conexión a PostgreSQL, su propia transacción.
El test no puede ver lo que hay en la BD a menos que lo pida a través de
la API. No hay acceso interno.

```
test de sistema (tu proceso Python)
    │
    │  socket TCP → localhost:8001 → Docker container
    ▼
uvicorn en Docker               ← proceso separado, sin acceso desde el test
    │
    │  get_db() crea sesión nueva, commit al final del request
    ▼
PostgreSQL en Docker            ← proceso separado, solo accesible via API
```

Cuando el test hace `assert data["total"] == 2_670_000`, está verificando
lo que la API retornó. No puede ir a verificar en la BD directamente porque
la BD está dentro de Docker, en otro proceso. La única forma de saber si los
datos se guardaron es pidiéndoselos a la API.

---

## 23. Comandos de referencia rápida

### Instalación
```bash
uv sync --dev
```

### Tests rápidos (sin Docker)
```bash
# Todos los tests rápidos con cobertura
uv run pytest tests/test_carrito.py tests/features/ tests/test_funcional.py \
  tests/test_tabla_decision.py tests/security/ \
  --cov=src --cov-report=term-missing -v

# Solo unitarios
uv run pytest tests/test_carrito.py -v

# Solo BDD
uv run pytest tests/features/ -v

# Solo BDD smoke y críticos
uv run pytest tests/features/ -m "smoke or critical" -v

# Solo seguridad
uv run pytest tests/security/ -v

# Reporte de cobertura HTML
uv run pytest tests/test_carrito.py tests/features/ tests/test_funcional.py \
  tests/test_tabla_decision.py tests/security/ \
  --cov=src --cov-report=html:reports/htmlcov

# Abrir reporte de cobertura (Windows)
start reports/htmlcov/index.html

# Abrir reporte de cobertura (macOS/Linux)
open reports/htmlcov/index.html
```

### Tests de integración (necesita Docker)
```bash
uv run pytest tests/integration/ -v -m integration
```

### Tests de sistema E2E (necesita API corriendo)
```bash
# Con docker compose de desarrollo
docker compose up -d
API_URL=http://localhost:8000 uv run pytest tests/system/ -v -m system
docker compose down

# Con docker compose de tests
docker compose -f docker-compose.test.yml up -d --build
API_URL=http://localhost:8001 uv run pytest tests/system/ -v -m system
docker compose -f docker-compose.test.yml down -v
```

### Calidad de código
```bash
uv run ruff check src/ tests/           # verificar lint
uv run ruff format --check src/ tests/  # verificar formato
uv run ruff check src/ tests/ --fix     # corregir lint automáticamente
uv run ruff format src/ tests/          # formatear automáticamente
```

### API manual (sin Docker)
```bash
uv run uvicorn src.carrito.api:app --port 8000 --reload
# Documentación interactiva: http://localhost:8000/docs
```

### Docker
```bash
# Desarrollo completo
docker compose up -d
docker compose down
docker compose down -v            # borra también los datos

# Stack de tests
docker compose -f docker-compose.test.yml up -d --build
docker compose -f docker-compose.test.yml down -v

# Ver logs
docker compose logs api -f
docker compose logs api-test -f
```

---

## 24. El pipeline de CI/CD

El pipeline en `.github/workflows/pipeline.yml` corre automáticamente en
cada `git push` a `main` o `develop`, y en cada Pull Request a `main`.

Si un job falla, los siguientes no corren. Esto evita gastar minutos de CI
en tests de integración cuando los tests unitarios ya fallaron.

```
tests-rapidos
      |
      v
tests-integracion
      |
      v
tests-sistema
      |
      v
tests-rendimiento  (solo en push a main)
```

### Job 1: tests-rapidos

- Verifica lint y formato con ruff (si hay errores de estilo, falla aquí)
- Corre los 89 tests sin Docker (SQLite en memoria como fallback automático)
- Exige cobertura mínima del 80%; si baja de ese umbral, falla
- Guarda reportes de cobertura como artefacto por 7 días en GitHub

### Job 2: tests-integracion

- TestContainers levanta PostgreSQL automáticamente dentro del runner
  de GitHub Actions (Docker está disponible por defecto en `ubuntu-latest`)
- Corre los 16 tests de integración
- Cada test usa el patrón rollback para aislamiento completo

### Job 3: tests-sistema

- Construye la imagen Docker con `docker compose -f docker-compose.test.yml up -d --build`
- Espera hasta 90 segundos en un bucle de reintentos a que el endpoint
  `/carrito/health-check` responda correctamente
- Corre los 6 tests E2E con `API_URL=http://localhost:8001`
- Siempre ejecuta `docker compose down -v` al terminar, aunque los tests fallen

### Job 4: tests-rendimiento

Solo corre en `push` a `main`, no en Pull Requests. La razón: ejecutar
30 segundos de carga en cada PR aumentaría el tiempo del pipeline de ~3 minutos
a ~6 minutos, lo que desincentiva hacer commits pequeños y frecuentes.

- Levanta el mismo stack de tests
- Corre Locust headless: 50 usuarios, 10 por segundo, durante 30 segundos
- Si P95 > 500ms o error rate > 1%, el job falla y el commit queda rojo
- Guarda el reporte HTML y los CSV de Locust como artefacto por 14 días
