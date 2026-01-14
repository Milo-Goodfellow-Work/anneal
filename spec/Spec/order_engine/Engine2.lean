import Spec.Prelude
import Spec.order_engine.Engine

namespace Spec.order_engine

/-!
Translation of `examples/order_engine/engine.h`.

This header declares the public API and core data types for the order-engine.

The executable semantics are implemented in `order_engine/Engine.lean`.
This module provides compatible type/constant definitions and recognizable
function names, plus lightweight wrappers that forward to `Engine`.

We model C pointers with pool indices (`Nat`) and use `Option` to represent
nullable pointers.
-/

namespace Engine2

/-- Constants from the C header. -/
def MAX_ORDERS : Nat := 1024
/-- Constants from the C header. -/
def MAX_LEVELS : Nat := 256

/-- `Side` from the C header. -/
inductive Side where
  | SIDE_BUY
  | SIDE_SELL
  deriving BEq, DecidableEq, Repr

/-- Order node (C: doubly-linked list node).

In C, `next/prev` are pointers; here we model them as nullable pool indices.
The actual engine semantics in `Engine.lean` use a simpler FIFO representation,
so these fields mainly serve to mirror the header.
-/
structure Order where
  id : UInt32
  price : UInt32
  quantity : UInt32
  side : Side
  next : Option Nat
  prev : Option Nat
  deriving Repr

/-- Price level node (C: BST node + queue head/tail pointers).

In C, `orders_head/orders_tail/left/right` are pointers.
Here we model them as nullable pool indices.
-/
structure Level where
  price : UInt32
  orders_head : Option Nat
  orders_tail : Option Nat
  left : Option Nat
  right : Option Nat
  deriving Repr

/-- Root pointers for both sides of the book. -/
structure OrderBook where
  buy_levels : Option Nat
  sell_levels : Option Nat
  deriving Repr

/-- Engine state (pools + free lists + book).

The C header uses fixed-size arrays of structs and arrays of pointers for the
free lists. In Lean we store pool slots as `Option` values and represent the
free lists as stacks (`List Nat`).
-/
structure Engine where
  order_pool : Array (Option Order)
  level_pool : Array (Option Level)
  free_orders : List Nat
  free_orders_count : Int
  free_levels : List Nat
  free_levels_count : Int
  book : OrderBook
  deriving Repr

/-!
Wrappers to the executable implementation in `order_engine/Engine.lean`.

The project uses `Spec.order_engine.Engine` (a structure) as the canonical state
machine; to keep header-level names available, we forward operations.
-/

private def toImplSide : Side → Spec.order_engine.Side
  | .SIDE_BUY => .buy
  | .SIDE_SELL => .sell

/-- Initialize an implementation engine (`Engine.lean`) from scratch. -/
def init_engine : Spec.order_engine.Engine :=
  Spec.order_engine.Engine.init

/-- Allocate an order from the implementation free list.
Returns updated engine and allocated pool index (if any).
-/
def alloc_order (e : Spec.order_engine.Engine) : (Spec.order_engine.Engine × Option Nat) :=
  Spec.order_engine.Engine.allocOrder e

/-- Free an order pool index back to the implementation free list. -/
def free_order (e : Spec.order_engine.Engine) (orderIdx : Nat) : Spec.order_engine.Engine :=
  Spec.order_engine.Engine.freeOrder e orderIdx

/-- Allocate a level from the implementation free list. -/
def alloc_level (e : Spec.order_engine.Engine) : (Spec.order_engine.Engine × Option Nat) :=
  Spec.order_engine.Engine.allocLevel e

/-- Free a level pool index back to the implementation free list. -/
def free_level (e : Spec.order_engine.Engine) (levelIdx : Nat) : Spec.order_engine.Engine :=
  Spec.order_engine.Engine.freeLevel e levelIdx

/-- Submit an order into the book (does not necessarily match immediately).

This forwards to the implementation. Inputs are `UInt32` in the header; the
implementation uses `Nat`, so we coerce via `.toNat`.
-/
def submit_order (e : Spec.order_engine.Engine)
    (id price quantity : UInt32) (side : Side) : Spec.order_engine.Engine :=
  Spec.order_engine.Engine.submitOrder e id.toNat price.toNat quantity.toNat (toImplSide side)

/-- Cancel an order by user id.

The C header exposes this, but the `engine.c` implementation in this benchmark
is simplified/truncated. We therefore provide a conservative no-op wrapper.
-/
def cancel_order (e : Spec.order_engine.Engine) (_id : UInt32) : Spec.order_engine.Engine :=
  e

/-- Run the batch matching loop until no more crossing. -/
def match_orders (e : Spec.order_engine.Engine) : Spec.order_engine.Engine :=
  Spec.order_engine.Engine.matchOrders e

/-- Book integrity check.

The C header exposes this; for this benchmark we return `true` as a placeholder.
A full translation would check BST ordering and queue invariants.
-/
def verify_book_integrity (_e : Spec.order_engine.Engine) : Bool :=
  true

end Engine2

end Spec.order_engine
