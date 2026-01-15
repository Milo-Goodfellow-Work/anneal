/-
This file was edited by Aristotle.

Lean version: leanprover/lean4:v4.24.0
Mathlib version: f897ebcf72cd16f89ab4577d0c826cd14afaafc7
This project request had uuid: e007b15c-61cf-42e4-99db-d76db00ce9c7
-/

import Spec.Prelude
import Spec.order_engine.Engine



namespace Spec.order_engine

open Spec

instance : Inhabited Order := ⟨Order.mk 0 0 0 Side.SIDE_BUY none none⟩
instance : Inhabited Level := ⟨Level.mk 0 none none none none⟩


/-!
Specification module for the translated `order_engine` project.

This file is *specification-only*: it states safety invariants and functional
correctness properties that the executable translation
(`Spec.order_engine.Engine`) is expected to satisfy.

Proofs may use `sorry` in this file, but statements must connect to the
translated definitions.
-/

/-- Order indices used as pointers into `Engine.order_pool`. -/
def OrderIdx (i : Nat) : Prop := i < MAX_ORDERS

/-- Level indices used as pointers into `Engine.level_pool`. -/
def LevelIdx (i : Nat) : Prop := i < MAX_LEVELS

/-- Engine pool sizes are fixed at the compile-time constants. -/
def PoolsSized (e : Engine) : Prop :=
  e.order_pool.size = MAX_ORDERS ∧
  e.level_pool.size = MAX_LEVELS ∧
  e.free_orders.size = MAX_ORDERS ∧
  e.free_levels.size = MAX_LEVELS

/-- Free-list counters are within bounds. -/
def FreeCountsInRange (e : Engine) : Prop :=
  e.free_orders_count ≤ MAX_ORDERS ∧
  e.free_levels_count ≤ MAX_LEVELS

/-- A basic memory-safety invariant for the engine state. -/
def EngineSafe (e : Engine) : Prop :=
  PoolsSized e ∧ FreeCountsInRange e

/-- An order node has well-formed link indices (if present). -/
def OrderLinksInRange (_e : Engine) (o : Order) : Prop :=
  (match o.next with | none => True | some i => OrderIdx i) ∧
  (match o.prev with | none => True | some i => OrderIdx i)

/-- A level node has well-formed tree/queue indices (if present). -/
def LevelLinksInRange (_e : Engine) (l : Level) : Prop :=
  (match l.orders_head with | none => True | some i => OrderIdx i) ∧
  (match l.orders_tail with | none => True | some i => OrderIdx i) ∧
  (match l.left with | none => True | some i => LevelIdx i) ∧
  (match l.right with | none => True | some i => LevelIdx i)

/--
All entries in the order pool have in-range link pointers.

This is an *intended invariant* for memory-safety: all pointers stored inside
pool elements must remain valid indices.
-/
def OrderPoolLinksSafe (e : Engine) : Prop :=
  ∀ i, i < e.order_pool.size → OrderLinksInRange e (e.order_pool[i]!)

/--
All entries in the level pool have in-range link pointers.

This is an *intended invariant* for memory-safety: all pointers stored inside
pool elements must remain valid indices.
-/
def LevelPoolLinksSafe (e : Engine) : Prop :=
  ∀ i, i < e.level_pool.size → LevelLinksInRange e (e.level_pool[i]!)

/-- Stronger safety invariant combining pool sizes and link well-formedness. -/
def EngineWellFormed (e : Engine) : Prop :=
  EngineSafe e ∧ OrderPoolLinksSafe e ∧ LevelPoolLinksSafe e

/-- An order is *active* if it has nonzero quantity. -/
def OrderActive (o : Order) : Prop := o.quantity ≠ 0

/-- A level pointer is optional: `none` means an empty side of the book. -/
def BookSideEmpty (root : Option Nat) : Prop := root = none

/--
A no-cross condition for the best prices at top-of-book.

This is used as a postcondition for `match_orders`: matching should stop when
`bestBuy.price < bestSell.price`, or when one side is empty.
-/
def NoMoreMatchesPossible (e : Engine) : Prop :=
  match get_best_buy e e.book.buy_levels, get_best_sell e e.book.sell_levels with
  | some bi, some si => e.level_pool[bi]!.price < e.level_pool[si]!.price
  | _, _ => True

/-- Determinism of `submit_order` (pure function). -/
theorem submit_order_deterministic
    (e : Engine) (id price qty : U32) (side : Side) :
    submit_order e id price qty side = submit_order e id price qty side := by
  rfl

/-- Determinism of `match_orders` (pure function). -/
theorem match_orders_deterministic (e : Engine) :
    match_orders e = match_orders e := by
  rfl


/-- `init_engine` produces correctly sized pools and in-range counters. -/
theorem init_engine_safe : EngineSafe init_engine := by
  -- Depends on arithmetic and array-size facts; stated as a proof obligation.
  sorry


/-- Allocation does not increase the free-order counter and stays in range. -/
theorem alloc_order_count_monotone (e : Engine) :
    (alloc_order e).1.free_orders_count ≤ e.free_orders_count ∧
    (alloc_order e).1.free_orders_count ≤ MAX_ORDERS := by
  sorry


/-- Allocation, when it returns an index, returns an in-bounds index. -/
theorem alloc_order_returns_in_range
    (e : Engine) (e' : Engine) (oi : Nat)
    (h : alloc_order e = (e', some oi)) :
    OrderIdx oi := by
  sorry


/-- Freeing an order keeps the free-order counter in range. -/
theorem free_order_count_in_range (e : Engine) (oi : Nat) :
    (free_order e oi).free_orders_count ≤ MAX_ORDERS := by
  sorry


/-- Allocation, when it returns a level index, returns an in-bounds index. -/
theorem alloc_level_returns_in_range
    (e : Engine) (e' : Engine) (li : Nat)
    (h : alloc_level e = (e', some li)) :
    LevelIdx li := by
  sorry


/-- `insert_level` either fails (no free levels) or returns a valid level index. -/
theorem insert_level_returns_valid
    (e : Engine) (side : Side) (p : U32) :
    (match insert_level e side p with
     | (_e', none) => True
     | (_e', some li) => LevelIdx li) := by
  sorry


/-- Queue safety: if `dequeue_order` returns an order index, it is in bounds. -/
theorem dequeue_order_returns_valid
    (e : Engine) (li : Nat) (e' : Engine) (oi : Nat)
    (h : dequeue_order e li = (e', some oi)) :
    OrderIdx oi := by
  sorry


/--
Functional correctness: `match_orders` returns an engine state where no more
matches are possible at the top of the book (or one side is empty).
-/
theorem match_orders_makes_progress (e : Engine) :
    NoMoreMatchesPossible (match_orders e).1 := by
  sorry


/--
Memory-safety preservation obligation: `submit_order` preserves `EngineSafe`.
-/
theorem submit_order_preserves_safety
    (e : Engine) (id price qty : U32) (side : Side)
    (h : EngineSafe e) :
    EngineSafe (submit_order e id price qty side) := by
  sorry


/-- Memory-safety preservation obligation: `match_orders` preserves `EngineSafe`. -/
theorem match_orders_preserves_safety (e : Engine) (h : EngineSafe e) :
    EngineSafe (match_orders e).1 := by
  sorry


/--
Scenario (multi-step): the `main.c`-style sequence up to the first
`match_orders`.
-/
def main_scenario_step1 : Engine :=
  let e0 := init_engine
  let e1 := submit_order e0 1 100 100 Side.SIDE_SELL
  let e2 := submit_order e1 2 101 50  Side.SIDE_SELL
  let e3 := submit_order e2 3 101 50  Side.SIDE_BUY
  (match_orders e3).1


/-- Postcondition for scenario step 1: stable top-of-book. -/
theorem main_scenario_step1_post : NoMoreMatchesPossible main_scenario_step1 := by
  simpa [main_scenario_step1] using (match_orders_makes_progress
    (let e0 := init_engine
     let e1 := submit_order e0 1 100 100 Side.SIDE_SELL
     let e2 := submit_order e1 2 101 50  Side.SIDE_SELL
     let e3 := submit_order e2 3 101 50  Side.SIDE_BUY
     e3))


/--
Scenario (multi-step): extend scenario 1 with an aggressive buy and match again.
-/
def main_scenario_step2 : Engine :=
  let e1 := main_scenario_step1
  let e2 := submit_order e1 4 102 150 Side.SIDE_BUY
  (match_orders e2).1


/-- Postcondition for scenario step 2: stable top-of-book. -/
theorem main_scenario_step2_post : NoMoreMatchesPossible main_scenario_step2 := by
  simpa [main_scenario_step2] using (match_orders_makes_progress
    (let e1 := main_scenario_step1
     let e2 := submit_order e1 4 102 150 Side.SIDE_BUY
     e2))


end Spec.order_engine