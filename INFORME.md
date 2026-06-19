# Informe Ejecutivo — Taller de Pruebas de Software
## Sistema Carrito de Compras · TiendaUV

**Asignatura:** Pruebas de Software — Semestre V, Ingeniería de Sistemas
**Repositorio:** `git@github.com:carlosaugustocue/pruebas-integracion-sistema.git`
**Tecnologías:** Python 3.12 · FastAPI · SQLAlchemy 2.x · PostgreSQL 16 · Docker · pytest · TestContainers · httpx · Locust
**Total de pruebas implementadas:** 111 pruebas en 7 suites

---

## Tabla de contenidos

1. [Descripción del sistema](#1-descripción-del-sistema)
2. [Arquitectura del proyecto](#2-arquitectura-del-proyecto)
3. [Modelo de base de datos](#3-modelo-de-base-de-datos)
4. [Fase 1 — Pruebas unitarias con TDD](#4-fase-1--pruebas-unitarias-con-tdd)
5. [Fase 2 — Pruebas de aceptación con BDD](#5-fase-2--pruebas-de-aceptación-con-bdd)
6. [Fase 3 — Pruebas funcionales y de tabla de decisión](#6-fase-3--pruebas-funcionales-y-de-tabla-de-decisión)
7. [Fase 4 — Pruebas de seguridad OWASP](#7-fase-4--pruebas-de-seguridad-owasp)
8. [Fase 5 — Pruebas de integración con base de datos real](#8-fase-5--pruebas-de-integración-con-base-de-datos-real)
9. [Fase 6 — Pruebas de sistema end-to-end](#9-fase-6--pruebas-de-sistema-end-to-end)
10. [Fase 7 — Pruebas de rendimiento con Locust](#10-fase-7--pruebas-de-rendimiento-con-locust)
11. [Pipeline CI/CD](#11-pipeline-cicd)
12. [Resumen consolidado de resultados](#12-resumen-consolidado-de-resultados)

---

## 1. Descripción del sistema

TiendaUV es una tienda en línea universitaria. El módulo construido es el **carrito de compras**: permite a los usuarios agregar productos, aplicar descuentos (por porcentaje o monto fijo), calcular totales con IVA y vaciar el carrito, todo persistido en una base de datos PostgreSQL real accesible vía API REST.

El sistema funciona en dos modos:

| Modo | Base de datos | Cuándo se usa |
|------|---------------|---------------|
| Sin Docker | SQLite en memoria | Pruebas unitarias, BDD, funcionales, seguridad |
| Con Docker | PostgreSQL 16 | Pruebas de integración, sistema y producción |

---

## 2. Arquitectura del proyecto

```
carrito-compras/
├── src/
│   ├── carrito/
│   │   ├── carrito.py          Lógica de negocio en memoria (para TDD y BDD)
│   │   ├── modelos.py          Dataclass Producto con validaciones de negocio
│   │   └── api.py              API REST con FastAPI (5 endpoints)
│   ├── database/
│   │   ├── models.py           Tablas ORM: CarritoDB e ItemCarritoDB
│   │   ├── config.py           Conexión a BD, fallback SQLite/PostgreSQL
│   │   └── repositorio.py      Patrón Repository — toda la lógica de datos
│   └── envios/
│       └── calculadora_envio.py  Reglas de negocio para costos de envío
│
├── tests/
│   ├── conftest.py             Fixtures compartidos (TestContainers, rollback)
│   ├── test_carrito.py         21 pruebas unitarias TDD
│   ├── test_funcional.py       29 pruebas funcionales
│   ├── test_tabla_decision.py  15 pruebas de tabla de decisión
│   ├── features/
│   │   ├── carrito.feature     12 escenarios BDD en Gherkin
│   │   └── test_carrito_bdd.py Definición de pasos BDD
│   ├── security/
│   │   └── test_seguridad_api.py  11 pruebas OWASP Top 10
│   ├── integration/
│   │   ├── test_repositorio_db.py  10 pruebas — repositorio vs PostgreSQL
│   │   └── test_api_integracion.py  6 pruebas — API + PostgreSQL
│   ├── system/
│   │   └── test_sistema_e2e.py  6 pruebas E2E vía HTTP real
│   └── performance/
│       └── locustfile.py       Simulación de carga (50 usuarios)
│
├── Dockerfile                  Imagen de producción (Python 3.12 + uvicorn)
├── Dockerfile.test             Imagen para correr tests en contenedor
├── docker-compose.yml          Stack de desarrollo (PostgreSQL + API + Adminer)
├── docker-compose.test.yml     Stack de tests E2E y CI/CD (puerto 8001)
├── pyproject.toml              Dependencias y configuración del proyecto
└── .github/workflows/pipeline.yml  Pipeline CI/CD con 4 jobs
```

### Capas de la arquitectura

```
 Cliente HTTP (browser / httpx / curl)
        │
        ▼
┌───────────────────────────────┐
│  API REST (FastAPI)           │  src/carrito/api.py
│  Routing, validación Pydantic │
└──────────────┬────────────────┘
               │ delega
               ▼
┌───────────────────────────────┐
│  Repositorio (Repository)     │  src/database/repositorio.py
│  Lógica de negocio + BD       │
└──────────────┬────────────────┘
               │ ORM
               ▼
┌───────────────────────────────┐
│  Modelos SQLAlchemy           │  src/database/models.py
│  CarritoDB · ItemCarritoDB    │
└──────────────┬────────────────┘
               │
               ▼
┌───────────────────────────────┐
│  Base de datos                │
│  SQLite (tests rápidos)       │
│  PostgreSQL 16 (producción)   │
└───────────────────────────────┘
```

---

## 3. Modelo de base de datos

### Tabla `carritos`

Almacena una fila por sesión de usuario. El carrito se crea automáticamente la primera vez que se agrega un producto.

| Columna | Tipo | Restricción | Descripción |
|---------|------|-------------|-------------|
| `id` | INTEGER | PK, autoincrement | Identificador interno del carrito |
| `sesion_id` | VARCHAR(100) | UNIQUE, NOT NULL, INDEX | Identificador de la sesión del usuario |
| `descuento_tipo` | VARCHAR(20) | nullable | `"porcentaje"` o `"fijo"` |
| `descuento_valor` | FLOAT | default=0.0 | Valor del descuento activo |
| `creado_en` | DATETIME | server_default=NOW() | Fecha y hora de creación |
| `actualizado_en` | DATETIME | server_default=NOW(), onupdate=NOW() | Última modificación |

### Tabla `items_carrito`

Almacena una fila por producto dentro de un carrito.

| Columna | Tipo | Restricción | Descripción |
|---------|------|-------------|-------------|
| `id` | INTEGER | PK, autoincrement | Identificador interno del item |
| `carrito_id` | INTEGER | FK → carritos.id (CASCADE) | Carrito al que pertenece |
| `nombre` | VARCHAR(200) | NOT NULL | Nombre del producto |
| `precio` | FLOAT | NOT NULL, CHECK precio > 0 | Precio unitario |
| `cantidad` | INTEGER | NOT NULL, CHECK cantidad >= 1 | Unidades en el carrito |

### Diagrama entidad-relación

```
carritos (1) ──────────────────── (*) items_carrito
  id (PK)                              id (PK)
  sesion_id (UNIQUE)                   carrito_id (FK)
  descuento_tipo                       nombre
  descuento_valor                      precio
  creado_en                            cantidad
  actualizado_en
```

### Reglas de integridad de negocio en la base de datos

- **FK con CASCADE:** Si se elimina un carrito, PostgreSQL elimina todos sus items automáticamente.
- **CHECK precio > 0:** La base de datos rechaza cualquier item con precio cero o negativo, independientemente del código Python.
- **CHECK cantidad >= 1:** No puede existir un item con 0 unidades en la tabla.
- **UNIQUE sesion_id:** No pueden existir dos carritos con el mismo identificador de sesión.
- **INDEX sesion_id:** Búsquedas por sesión son O(log n) en vez de O(n).

### Datos que guarda el sistema en una operación típica

Cuando un usuario agrega "Laptop" y "Mouse" con un descuento del 15%:

**Tabla `carritos` (1 fila):**
```
id=1 | sesion_id="usuario-abc" | descuento_tipo="porcentaje" | descuento_valor=15.0
```

**Tabla `items_carrito` (2 filas):**
```
id=1 | carrito_id=1 | nombre="Laptop" | precio=2500000.0 | cantidad=1
id=2 | carrito_id=1 | nombre="Mouse"  | precio=85000.0   | cantidad=2
```

**Cálculos derivados (no almacenados, calculados al consultar):**
```
subtotal_laptop = 2500000 × 1 = 2.500.000
subtotal_mouse  =   85000 × 2 =   170.000
subtotal_bruto  =             = 2.670.000
descuento_15%   =             =   400.500
total_neto      =             = 2.269.500
IVA_19%         =             =   431.205
total_con_iva   =             = 2.700.705
```

---

## 4. Fase 1 — Pruebas unitarias con TDD

### Qué es TDD

Test-Driven Development es una metodología donde primero se escribe el test que falla (rojo), luego se escribe el código mínimo para que pase (verde) y finalmente se refactoriza. En este proyecto se aplicó para construir la lógica de negocio del carrito en memoria.

### Archivos involucrados

| Archivo | Rol |
|---------|-----|
| `src/carrito/carrito.py` | Clase `Carrito` con lógica en memoria |
| `src/carrito/modelos.py` | Dataclass `Producto` con validaciones |
| `tests/test_carrito.py` | 21 pruebas unitarias |

### Pruebas implementadas (21 tests)

| # | Nombre del test | Qué verifica |
|---|----------------|--------------|
| 1 | `test_carrito_inicia_vacio` | El carrito recién creado no tiene productos |
| 2 | `test_agregar_un_producto` | Agregar un producto lo incluye en el carrito |
| 3 | `test_agregar_dos_productos_diferentes` | Dos productos distintos coexisten en el carrito |
| 4 | `test_agregar_mismo_producto_suma_cantidad` | El mismo producto suma cantidad, no duplica |
| 5 | `test_calcular_total_un_producto` | Total = precio × cantidad para un item |
| 6 | `test_calcular_total_multiples_productos` | Total = suma de subtotales |
| 7 | `test_eliminar_producto_existente` | Eliminar un producto lo quita del carrito |
| 8 | `test_eliminar_producto_inexistente` | Intentar eliminar un inexistente lanza error |
| 9 | `test_vaciar_carrito` | Vaciar deja el carrito con 0 productos y total 0 |
| 10 | `test_descuento_porcentaje` | Descuento del 10% calcula total correcto |
| 11 | `test_descuento_fijo` | Descuento de monto fijo calcula total correcto |
| 12 | `test_descuento_no_hace_total_negativo` | Total nunca baja de 0 con descuentos grandes |
| 13 | `test_total_con_iva` | Total con IVA del 19% es correcto |
| 14 | `test_precio_invalido_lanza_error` | Precio ≤ 0 lanza `ValueError` |
| 15 | `test_cantidad_invalida_lanza_error` | Cantidad < 1 lanza `ValueError` |
| 16 | `test_nombre_vacio_lanza_error` | Nombre vacío lanza `ValueError` |
| 17 | `test_stock_insuficiente_lanza_error` | Agregar más de lo disponible lanza error |
| 18 | `test_carrito_sin_productos_total_cero` | Total de carrito vacío es 0 |
| 19 | `test_cantidad_maxima_permitida` | Cantidad de 99 se acepta correctamente |
| 20 | `test_cantidad_sobre_maximo_lanza_error` | Cantidad > 99 lanza `ValueError` |
| 21 | `test_descuento_porcentaje_invalido_lanza_error` | Porcentaje fuera de [0,100] lanza error |

### Resultado

```
21 passed
```

---

## 5. Fase 2 — Pruebas de aceptación con BDD

### Qué es BDD

Behavior-Driven Development permite escribir pruebas en lenguaje natural (Gherkin) legible por personas no técnicas. Los escenarios describen el comportamiento esperado desde la perspectiva del usuario.

### Archivos involucrados

| Archivo | Rol |
|---------|-----|
| `tests/features/carrito.feature` | Escenarios en lenguaje Gherkin |
| `tests/features/test_carrito_bdd.py` | Implementación de los pasos (step definitions) |

### Escenarios implementados (12 tests)

```gherkin
Feature: Carrito de compras de TiendaUV
  Como cliente de TiendaUV
  Quiero poder gestionar mi carrito de compras
  Para realizar mis compras de forma organizada y correcta.
```

| # | Escenario | Etiquetas |
|---|-----------|-----------|
| 1 | Agregar un producto al carrito vacío | `@smoke @critical` |
| 2 | Agregar múltiples productos diferentes | `@smoke` |
| 3 | Agregar el mismo producto dos veces suma cantidades | `@regression` |
| 4 | Eliminar un producto del carrito | `@smoke` |
| 5 | Calcular el total del carrito | `@critical` |
| 6 | Aplicar descuento porcentaje 10% | `@critical` |
| 7 | Aplicar descuento porcentaje 50% | `@critical` |
| 8 | Aplicar descuento fijo $150.000 | `@critical` |
| 9 | Aplicar descuento fijo $0 | `@critical` |
| 10 | Calcular total con IVA del 19% | `@critical` |
| 11 | No se puede agregar producto sin stock suficiente | `@regression` |
| 12 | Vaciar el carrito elimina todo | `@smoke` |

### Resultado

```
12 passed
```

---

## 6. Fase 3 — Pruebas funcionales y de tabla de decisión

### Pruebas funcionales (29 tests) — `tests/test_funcional.py`

Aplican tres técnicas clásicas de diseño de pruebas:

**Partición de equivalencia:** Divide el espacio de entrada en clases donde el sistema se comporta igual. Se prueba un representante de cada clase.

| Clase de equivalencia | Valor probado | Resultado esperado |
|-----------------------|---------------|--------------------|
| Precio válido | 100.000 | Acepta |
| Precio límite | 0.01 | Acepta |
| Precio inválido (cero) | 0 | `ValueError` |
| Precio inválido (negativo) | -100 | `ValueError` |
| Cantidad válida | 5 | Acepta |
| Cantidad límite inferior | 1 | Acepta |
| Cantidad límite superior | 99 | Acepta |
| Cantidad fuera de rango | 100 | `ValueError` |

**Análisis de valores límite:** Prueba los valores exactamente en los bordes de los rangos válidos.

| Frontera | Valor | Comportamiento |
|----------|-------|----------------|
| Precio mínimo | 0.01 | Acepta |
| Precio justo debajo del mínimo | 0.00 | Rechaza |
| Cantidad mínima | 1 | Acepta |
| Cantidad máxima | 99 | Acepta |
| Cantidad sobre máximo | 100 | Rechaza |
| Descuento porcentaje máximo | 100% | Acepta |
| Descuento porcentaje sobre máximo | 101% | Rechaza |

**Pruebas de transición de estados:** Verifican que el carrito pasa correctamente por sus estados: Vacío → Con productos → Con descuento → Vaciado.

### Pruebas de tabla de decisión (15 tests) — `tests/test_tabla_decision.py`

Modelan las reglas de negocio del costo de envío. Cada combinación de condiciones produce una acción específica:

| Peso (kg) | Distancia (km) | Tipo envío | ¿Envío gratuito? | Costo esperado |
|-----------|---------------|------------|-----------------|----------------|
| < 1 | < 50 | Estándar | No | $5.000 |
| 1–5 | < 50 | Estándar | No | $10.000 |
| > 5 | < 50 | Estándar | No | $20.000 |
| < 1 | 50–200 | Estándar | No | $15.000 |
| 1–5 | 50–200 | Estándar | No | $25.000 |
| > 5 | 50–200 | Estándar | No | $40.000 |
| Cualquiera | > 200 | Estándar | No | $60.000 |
| Cualquiera | Cualquiera | Express | No | +50% |
| Cualquiera | Cualquiera | Cualquiera | Sí (compra ≥ $500k) | $0 |

### Resultado

```
44 passed  (29 funcionales + 15 tabla de decisión)
```

---

## 7. Fase 4 — Pruebas de seguridad OWASP

### Archivos involucrados

| Archivo | Rol |
|---------|-----|
| `tests/security/test_seguridad_api.py` | 11 pruebas de vulnerabilidades OWASP Top 10 |

### Pruebas implementadas (11 tests)

| # | Vulnerabilidad OWASP | Test | Qué verifica |
|---|---------------------|------|--------------|
| 1 | A03 — Inyección SQL | `test_inyeccion_sql_en_sesion_id` | SQL en `sesion_id` no rompe la API |
| 2 | A03 — Inyección SQL | `test_inyeccion_sql_en_nombre_producto` | SQL en nombre de producto es tratado como texto |
| 3 | A03 — XSS | `test_xss_en_nombre_producto` | Scripts HTML se almacenan como texto, no ejecutan |
| 4 | A03 — XSS | `test_xss_en_sesion_id` | Scripts en sesión_id son texto inerte |
| 5 | A04 — Diseño inseguro | `test_precio_negativo_rechazado` | Precio negativo retorna 422, no se guarda |
| 6 | A04 — Diseño inseguro | `test_cantidad_cero_rechazada` | Cantidad 0 retorna 422 |
| 7 | A04 — Diseño inseguro | `test_cantidad_extremadamente_grande` | Cantidad > 99 retorna 422 |
| 8 | A05 — Configuración insegura | `test_headers_de_seguridad_presentes` | La API responde con headers HTTP válidos |
| 9 | A08 — Fallos de integridad | `test_campos_extra_ignorados` | Campos adicionales en el JSON son descartados |
| 10 | A09 — Fallos de registro | `test_error_retorna_json_estructurado` | Los errores retornan JSON con campo `detail` |
| 11 | A04 — Diseño inseguro | `test_descuento_porcentaje_invalido` | Porcentaje > 100 retorna 422 |

### Resultado

```
11 passed
```

---

## 8. Fase 5 — Pruebas de integración con base de datos real

### Qué son las pruebas de integración

Verifican que **dos o más componentes funcionan juntos correctamente**. En esta fase: el repositorio Python interactuando con una instancia real de PostgreSQL. No usan mocks ni SQLite — prueban la capa de datos con la tecnología exacta de producción.

### Tecnología: TestContainers

TestContainers es una librería que controla Docker desde Python. Al iniciar la suite, ejecuta automáticamente:

```
docker run -d -p <puerto-aleatorio>:5432 postgres:16-alpine
```

Espera a que PostgreSQL acepte conexiones y entrega la URL de conexión al código de prueba. Al terminar, para y elimina el contenedor. Funciona tanto en local como en el runner de GitHub Actions.

### Patrón rollback — aislamiento entre tests

Cada test corre dentro de una transacción que **nunca se confirma**:

```
1. Abrir conexión al PostgreSQL del contenedor
2. BEGIN TRANSACTION
3. Crear sesión SQLAlchemy vinculada a esa conexión
4. Entregar la sesión al test
5. El test ejecuta INSERT / UPDATE / DELETE
6. Al finalizar: ROLLBACK
7. La tabla queda exactamente como estaba
```

Esto es más eficiente y seguro que truncar tablas: el rollback es atómico, no genera I/O de disco y garantiza que un test que falla a la mitad no contamina a los siguientes.

### Archivos involucrados

| Archivo | Rol |
|---------|-----|
| `tests/conftest.py` | Fixtures `postgres_container`, `db_engine`, `db_session`, `client_con_bd` |
| `tests/integration/test_repositorio_db.py` | 10 tests — repositorio directamente contra PostgreSQL |
| `tests/integration/test_api_integracion.py` | 6 tests — API + repositorio + PostgreSQL |

### Fixtures de conftest.py (cadena de dependencias)

```
client_con_bd (scope=function)
    └── db_session (scope=function)
            └── db_engine (scope=session)
                    └── postgres_container (scope=session)
```

- `postgres_container`: levanta el contenedor Docker una sola vez para toda la ejecución.
- `db_engine`: crea las tablas con `Base.metadata.create_all()` una sola vez.
- `db_session`: abre una transacción por cada test individual.
- `client_con_bd`: inyecta `db_session` en la API via `dependency_overrides`.

### test_repositorio_db.py — 10 pruebas

| # | Nombre del test | Datos en BD que verifica |
|---|----------------|--------------------------|
| 1 | `test_crear_carrito_nuevo_en_bd` | 1 fila en `carritos`, `id IS NOT NULL` |
| 2 | `test_obtener_carrito_existente_no_duplica` | COUNT(`carritos`) = 1 tras 2 llamadas |
| 3 | `test_agregar_item_persiste_en_bd` | 1 fila en `items_carrito` con `id IS NOT NULL` |
| 4 | `test_agregar_item_existente_suma_cantidad` | COUNT(`items_carrito`) = 1, `cantidad` = 4 (1+3) |
| 5 | `test_calcular_total_con_items_en_bd` | `total` = 2.670.000 (Laptop×1 + Mouse×2) |
| 6 | `test_descuento_persiste_en_bd` | `descuento_tipo="porcentaje"`, `descuento_valor=10.0` |
| 7 | `test_vaciar_carrito_elimina_items_de_bd` | `len(carrito.items)` = 0, `carrito.id IS NOT NULL` |
| 8 | `test_precio_invalido_no_se_guarda` | COUNT(`items_carrito`) = 0 tras `ValueError` |
| 9 | `test_total_carrito_inexistente_es_cero` | `calcular_total("inexistente")` = 0.0 |
| 10 | `test_rollback_en_error_no_corrompe_estado` | Item válido persiste; item inválido no contamina |

### test_api_integracion.py — 6 pruebas

| # | Nombre del test | Qué cruza |
|---|----------------|-----------|
| 1 | `test_post_producto_persiste_en_bd` | HTTP POST → verifica fila en `items_carrito` |
| 2 | `test_get_carrito_lee_datos_reales_de_bd` | Inserta en BD directamente → verifica GET HTTP |
| 3 | `test_estado_persiste_entre_requests` | 2 POST + 1 GET → verifica 2 productos |
| 4 | `test_descuento_persiste_y_afecta_total` | POST producto + POST descuento → GET total correcto |
| 5 | `test_vaciar_elimina_todo_de_bd` | POST + DELETE → COUNT = 0 en BD |
| 6 | `test_estructura_respuesta_es_correcta` | GET → verifica campos `sesion_id`, `productos`, `total`, `total_con_iva`, `cantidad_productos` |

### Resultado

```
16 passed in 18.97s
```

---

## 9. Fase 6 — Pruebas de sistema end-to-end

### Qué son las pruebas de sistema

Verifican el **sistema completo desde el exterior**, tal como lo haría un usuario o cliente real. Están en la cima de la pirámide de pruebas: son las más lentas y costosas de mantener, pero las que más se parecen al comportamiento en producción.

A diferencia de las pruebas de integración (que usan `TestClient` en memoria), estas pruebas:
- Usan `httpx.Client` que abre conexiones TCP reales.
- Requieren la API corriendo como proceso externo en un puerto de red.
- No tienen acceso al proceso interno ni a la sesión de base de datos.
- Solo pueden observar lo que la API retorna en sus respuestas HTTP.

### Infraestructura levantada

```bash
docker compose up -d
```

Levanta tres contenedores en la red `carrito-compras_default`:

| Contenedor | Imagen | Puerto | Propósito |
|------------|--------|--------|-----------|
| `tiendauv_db` | postgres:16-alpine | 5432 | Base de datos PostgreSQL |
| `tiendauv_api` | carrito-compras-api (local) | 8000 | API REST FastAPI |
| `adminer` | adminer:latest | 8080 | Interfaz web para inspeccionar BD |

La API se conecta al DB usando la URL interna: `postgresql://tiendauv:tiendauv_pass@db:5432/tiendauv`

### Sesiones únicas por test

Cada test genera un `sesion_id` único para evitar contaminación entre pruebas:

```python
def sesion_unica() -> str:
    return f"e2e-{uuid.uuid4().hex[:8]}"
# Ejemplo: "e2e-a3f9b2c1"
```

Como no hay rollback (los datos persisten en PostgreSQL real), cada test opera sobre su propio carrito completamente independiente.

### test_sistema_e2e.py — 6 pruebas

| # | Nombre del test | Flujo de negocio verificado |
|---|----------------|----------------------------|
| 1 | `test_health_check_sistema` | GET `/carrito/health-check` → `{"status": "ok"}` |
| 2 | `test_flujo_compra_normal_completo` | POST Laptop + POST Mouse → GET total = 2.670.000 |
| 3 | `test_flujo_con_descuento_porcentaje` | POST Laptop + POST descuento 15% → GET total = 850.000, total_con_iva = 1.011.500 |
| 4 | `test_sesiones_independientes` | Vaciar sesión A no modifica sesión B |
| 5 | `test_mismo_producto_dos_veces_suma` | 2 POST mismo producto → 1 producto, cantidad=3 |
| 6 | `test_sistema_responde_en_menos_de_500ms` | Tiempo de respuesta de GET < 500ms |

### Cálculo verificado en el test 3

```
Producto:    Laptop × 1 = $1.000.000
Descuento:   15% sobre $1.000.000 = $150.000
Total neto:  $1.000.000 - $150.000 = $850.000
IVA 19%:     $850.000 × 0.19 = $161.500
Total c/IVA: $850.000 + $161.500 = $1.011.500
```

### Resultado

```
6 passed in 0.23s
```

---

## 10. Fase 7 — Pruebas de rendimiento con Locust

### Qué es Locust

Locust es una herramienta de pruebas de carga que simula múltiples usuarios concurrentes enviando requests HTTP a la API. Permite definir el comportamiento de cada usuario como código Python.

### Archivo involucrado

`tests/performance/locustfile.py`

### Configuración de carga

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| Usuarios concurrentes | 50 | Usuarios virtuales simultáneos |
| Tasa de generación | 10/s | Nuevos usuarios por segundo al inicio |
| Duración | 30 segundos | Tiempo total de la prueba |
| Host | `http://localhost:8001` | Stack de pruebas |

### SLAs (Service Level Agreements) configurados

| Métrica | Umbral | Consecuencia si se viola |
|---------|--------|--------------------------|
| Percentil 95 (P95) | < 500ms | El pipeline falla |
| Tasa de error | < 1% | El pipeline falla |

### Escenario simulado

Cada usuario virtual ejecuta el siguiente flujo de compra completo:

1. `GET /carrito/health-check` — verificar disponibilidad
2. `POST /carrito/{id}/productos` — agregar Laptop
3. `POST /carrito/{id}/productos` — agregar Mouse
4. `POST /carrito/{id}/descuento` — aplicar descuento
5. `GET /carrito/{id}` — consultar estado final
6. `DELETE /carrito/{id}` — vaciar carrito

---

## 11. Pipeline CI/CD

### Archivo: `.github/workflows/pipeline.yml`

El pipeline se ejecuta automáticamente en cada `push` a `main` o `develop` y en cada Pull Request. Tiene 4 jobs en secuencia:

```
tests-rapidos (sin Docker)
      │
      ▼
tests-integracion (TestContainers)
      │
      ▼
tests-sistema (docker compose)
      │
      ▼
tests-rendimiento (Locust, solo push a main)
```

### Job 1 — Tests rápidos

- **Entorno:** Ubuntu Latest, sin Docker
- **Qué corre:** lint (ruff), formato (ruff), 89 tests (unitarios + BDD + funcionales + decisión + seguridad)
- **Cobertura mínima requerida:** 80%
- **Artefactos generados:** `coverage.xml`, `htmlcov/`, `test_results.xml`
- **Condición de éxito:** 100% de tests pasan y cobertura ≥ 80%

### Job 2 — Tests de integración

- **Entorno:** Ubuntu Latest con Docker daemon disponible
- **Qué corre:** 16 tests en `tests/integration/` con TestContainers
- **PostgreSQL:** levantado automáticamente por TestContainers en puerto aleatorio
- **Tiempo estimado:** 20-30 segundos
- **Depende de:** Job 1

### Job 3 — Tests de sistema E2E

- **Entorno:** Ubuntu Latest
- **Qué corre:** 6 tests en `tests/system/` vía `httpx.Client`
- **Stack:** `docker compose -f docker-compose.test.yml up -d --build` (API en puerto 8001)
- **Limpieza:** `docker compose down -v` siempre, aunque fallen los tests
- **Depende de:** Job 2

### Job 4 — Tests de rendimiento

- **Entorno:** Ubuntu Latest
- **Cuándo corre:** Solo en `push` directo a `main` (no en PRs)
- **Qué corre:** Locust, 50 usuarios, 30 segundos
- **SLAs verificados:** P95 < 500ms, error rate < 1%
- **Artefactos generados:** `reporte.html` y CSVs de Locust (14 días de retención)
- **Depende de:** Job 3

---

## 12. Resumen consolidado de resultados

### Inventario completo de pruebas

| Suite | Archivo | Tests | Tecnología | Estado |
|-------|---------|-------|------------|--------|
| Unitarias TDD | `test_carrito.py` | 21 | pytest, en memoria | ✅ 21/21 |
| BDD Gherkin | `features/test_carrito_bdd.py` | 12 | pytest-bdd, Gherkin | ✅ 12/12 |
| Funcionales | `test_funcional.py` | 29 | pytest, equivalencia + límites | ✅ 29/29 |
| Tabla de decisión | `test_tabla_decision.py` | 15 | pytest, reglas de envío | ✅ 15/15 |
| Seguridad OWASP | `security/test_seguridad_api.py` | 11 | pytest + TestClient | ✅ 11/11 |
| Integración — Repositorio | `integration/test_repositorio_db.py` | 10 | TestContainers + PostgreSQL | ✅ 10/10 |
| Integración — API | `integration/test_api_integracion.py` | 6 | TestContainers + TestClient | ✅ 6/6 |
| Sistema E2E | `system/test_sistema_e2e.py` | 6 | httpx + docker compose | ✅ 6/6 |
| Rendimiento | `performance/locustfile.py` | — | Locust, 50 usuarios | ✅ SLAs OK |
| **TOTAL** | | **110** | | **✅ 110/110** |

### Pirámide de pruebas del proyecto

```
                    ▲
                   /▲\
                  / ▲ \
                 /  ▲  \
                / SIST. \      6 tests  — httpx real, docker compose
               /─────────\
              /  INTEGR.  \   16 tests  — TestContainers + PostgreSQL
             /─────────────\
            /   SEGURIDAD   \  11 tests — OWASP Top 10
           /─────────────────\
          /   FUNCIONALES     \ 44 tests — equivalencia + límites + decisión
         /─────────────────────\
        /     UNITARIAS TDD     \ 21 tests — lógica en memoria
       /  +  BDD GHERKIN         \ 12 tests — lenguaje natural
      /─────────────────────────────\
```

### Cobertura de requisitos del taller

| Requisito del taller | ¿Implementado? | Detalle |
|---------------------|---------------|---------|
| Carpeta `tests/integration/` con TestContainers | ✅ | `test_repositorio_db.py` + `test_api_integracion.py` |
| PostgreSQL real en integración | ✅ | `postgres:16-alpine` via TestContainers |
| Mínimo 4 tests de integración | ✅ | 16 tests implementados |
| Carrito nuevo se crea correctamente | ✅ | `test_crear_carrito_nuevo_en_bd` |
| Mismo producto suma cantidad | ✅ | `test_agregar_item_existente_suma_cantidad` |
| Total calculado con datos persistidos | ✅ | `test_calcular_total_con_items_en_bd` |
| Vaciar elimina items de la tabla | ✅ | `test_vaciar_carrito_elimina_items_de_bd` |
| Rollback automático entre tests | ✅ | Fixture `db_session` en `conftest.py` |
| Carpeta `tests/system/` con httpx | ✅ | `test_sistema_e2e.py` |
| Mínimo 3 tests de sistema | ✅ | 6 tests implementados |
| Flujo con descuento + total con IVA | ✅ | `test_flujo_con_descuento_porcentaje` |
| Dos sesiones independientes | ✅ | `test_sesiones_independientes` |
| `uv run pytest tests/integration/ -v` | ✅ | 16 passed in 18.97s |
| `uv run pytest tests/system/ -v` | ✅ | 6 passed in 0.23s |
| Pipeline CI/CD con los 4 tipos de prueba | ✅ | `.github/workflows/pipeline.yml` |

### Comandos de ejecución

```bash
# Instalar dependencias
uv sync --dev

# Tests rápidos (sin Docker)
uv run pytest tests/test_carrito.py tests/features/ \
  tests/test_funcional.py tests/test_tabla_decision.py \
  tests/security/ -v

# Tests de integración (requiere Docker)
uv run pytest tests/integration/ -v

# Levantar stack y correr tests de sistema
docker compose up -d
uv run pytest tests/system/ -v
docker compose down

# Todas las suites juntas
uv run pytest -v
```

---

*Informe generado para el Taller de Pruebas de Integración y Sistema — Asignatura Pruebas de Software, Semestre V.*
