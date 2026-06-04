@carrito
Feature: Carrito de compras de TiendaUV
  Como cliente de TiendaUV
  Quiero poder gestionar mi carrito de compras
  Para realizar mis compras de forma organizada y correcta.

  Background:
    Given un carrito de compras vacío

  # ─────────────────────────────────────────────
  # Escenarios básicos de agregar y eliminar
  # ─────────────────────────────────────────────

  @smoke @critical
  Scenario: Agregar un producto al carrito vacío
    When agrego el producto "Laptop" con precio 2500000 y cantidad 1
    Then el carrito contiene 1 producto
    And el producto "Laptop" está en el carrito

  @smoke
  Scenario: Agregar múltiples productos diferentes
    When agrego el producto "Laptop" con precio 2500000 y cantidad 1
    And agrego el producto "Mouse" con precio 85000 y cantidad 2
    Then el carrito contiene 2 productos

  @regression
  Scenario: Agregar el mismo producto dos veces suma cantidades
    When agrego el producto "Laptop" con precio 2500000 y cantidad 1
    And agrego el producto "Laptop" con precio 2500000 y cantidad 2
    Then el carrito contiene 1 producto
    And el producto "Laptop" tiene cantidad 3

  @smoke
  Scenario: Eliminar un producto del carrito
    Given el carrito tiene el producto "Laptop" con precio 2500000 y cantidad 1
    When elimino el producto "Laptop"
    Then el carrito contiene 0 productos

  # ─────────────────────────────────────────────
  # Escenarios de cálculo de totales
  # ─────────────────────────────────────────────

  @critical
  Scenario: Calcular el total del carrito
    When agrego el producto "Laptop" con precio 2500000 y cantidad 1
    And agrego el producto "Mouse" con precio 85000 y cantidad 2
    Then el total del carrito es 2670000

  @critical
  Scenario Outline: Aplicar diferentes tipos de descuento
    Given el carrito tiene el producto "Laptop" con precio 1000000 y cantidad 1
    When aplico un descuento de tipo "<tipo>" con valor <valor>
    Then el total del carrito es <total_esperado>

    Examples:
      | tipo       | valor  | total_esperado |
      | porcentaje | 10     | 900000         |
      | porcentaje | 50     | 500000         |
      | fijo       | 150000 | 850000         |
      | fijo       | 0      | 1000000        |

  @critical
  Scenario: Calcular total con IVA del 19%
    When agrego el producto "Laptop" con precio 1000000 y cantidad 1
    Then el total con impuestos es 1190000

  # ─────────────────────────────────────────────
  # Escenarios de validación y bordes
  # ─────────────────────────────────────────────

  @regression
  Scenario: No se puede agregar producto sin stock suficiente
    Given un carrito con stock disponible:
      | producto | stock |
      | Laptop   | 2     |
    When intento agregar "Laptop" con precio 2500000 y cantidad 5
    Then se produce un error que contiene "stock"

  @smoke
  Scenario: Vaciar el carrito elimina todo
    Given el carrito tiene el producto "Laptop" con precio 2500000 y cantidad 1
    And el carrito tiene el producto "Mouse" con precio 85000 y cantidad 3
    When vacío el carrito
    Then el carrito contiene 0 productos
    And el total del carrito es 0
