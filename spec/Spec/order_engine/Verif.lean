import Spec.Prelude
import Spec.order_engine.Engine
import Spec.order_engine.Engine2
import Spec.order_engine.Main

namespace Spec.order_engine

/-!
Specification and verification-facing statements for the `order_engine` project.

This file is intentionally *not* an executable part of the engine; rather, it
collects key invariants and theorems that one would typically want to prove
about a limit order book implementation.

Proofs are allowed to use `sorry` in this benchmark, but the statements should
be meaningful and track the translated semantics in `Engine.lean`.

We focus on:
* pool bounds and basic safety properties
* monotonicity of logs and bounded resource usage
* high-level matching properties (no crossing after matching)
* a sanity theorem for the `main.c` scenario
-/

open Spec.order_engine

namespace Verif

/-- A pool index is valid for the order pool of a given engine. -/
def ValidOrderIdx (e : Engine) (i : Nat) : Prop :=
  i < e.orders.size

/-- A pool index is valid for the level pool of a given engine. -/
def ValidLevelIdx (e : Engine) (i : Nat) : Prop :=
  i < e.levels.size

/-- The engine's pools have the expected fixed sizes. -/
def PoolsSized (e : Engine) : Prop :=
  e.orders.size = Engine.MAX_ORDERS ∧ e.levels.size = Engine.MAX_LEVELS

/-- Free-list indices are in range of the corresponding pool.

This is a key memory-safety invariant: a later `get!`/`set!` will not go out of
bounds when it uses an index taken from a free list.
-/
def FreeListsInRange (e : Engine) : Prop :=
  (∀ i ∈ e.freeOrders, ValidOrderIdx e i) ∧ (∀ i ∈ e.freeLevels, ValidLevelIdx e i)

/-- A (weak) structural invariant tying together sizes and free-lists. -/
def WellFormed (e : Engine) : Prop :=
  PoolsSized e ∧ FreeListsInRange e

/-- `Engine.init` produces a well-formed engine. -/
theorem init_wellFormed : WellFormed Engine.init := by
  -- The translated `init` uses `mkArray` with the constant sizes and
  -- constructs free lists from `List.range`, so this should be provable.
  sorry

/-- Allocating an order either fails (OOM) or returns an in-range index. -/
theorem allocOrder_index_inRange (e e' : Engine) (oi : Option Nat)
    (h : Engine.allocOrder e = (e', oi)) :
    (oi = none) ∨ (∃ i, oi = some i ∧ ValidOrderIdx e' i) := by
  -- Unfolding `allocOrder` and analyzing the free-list head.
  sorry

/-- Allocating a level either fails (OOM) or returns an in-range index. -/
theorem allocLevel_index_inRange (e e' : Engine) (li : Option Nat)
    (h : Engine.allocLevel e = (e', li)) :
    (li = none) ∨ (∃ i, li = some i ∧ ValidLevelIdx e' i) := by
  sorry

/-- Freeing an order never changes pool sizes. -/
theorem freeOrder_sizes (e : Engine) (i : Nat) :
    (Engine.freeOrder e i).orders.size = e.orders.size ∧
    (Engine.freeOrder e i).levels.size = e.levels.size := by
  -- `freeOrder` uses `Array.set!` which preserves size.
  sorry

/-- Freeing a level never changes pool sizes. -/
theorem freeLevel_sizes (e : Engine) (i : Nat) :
    (Engine.freeLevel e i).orders.size = e.orders.size ∧
    (Engine.freeLevel e i).levels.size = e.levels.size := by
  sorry

/-- Submitting an order never changes pool sizes. -/
theorem submitOrder_sizes (e : Engine) (id price qty : Nat) (side : Side) :
    (Engine.submitOrder e id price qty side).orders.size = e.orders.size ∧
    (Engine.submitOrder e id price qty side).levels.size = e.levels.size := by
  sorry

/-- Matching never changes pool sizes. -/
theorem matchOrders_sizes (e : Engine) :
    (Engine.matchOrders e).orders.size = e.orders.size ∧
    (Engine.matchOrders e).levels.size = e.levels.size := by
  sorry

/-- Logs only ever grow by appending; no entry is removed.

We state this as a prefix property.
-/
def IsPrefix (xs ys : List α) : Prop := ∃ zs, ys = xs ++ zs

/-- `matchStep` either leaves the log unchanged or appends exactly one match line. -/
theorem matchStep_log_monotone (e : Engine) :
    let (e', _cont) := Engine.matchStep e
    IsPrefix e.log e'.log := by
  -- The only log update in `matchStep` is `e.log ++ [fmtMatch ...]`.
  sorry

/-- `matchOrders` is log-monotone: it never removes log entries. -/
theorem matchOrders_log_monotone (e : Engine) :
    IsPrefix e.log (Engine.matchOrders e).log := by
  -- Follows from `matchStep_log_monotone` and the bounded loop.
  sorry

/-- A high-level postcondition: after `matchOrders`, the book is not crossing.

Informally: either there is no best buy or no best sell, or the best buy price
is strictly less than the best sell price.

This is the central functional-correctness condition for a matching engine.
-/
def NotCrossing (e : Engine) : Prop :=
  match Engine.getBestBuy e e.book.buy_levels, Engine.getBestSell e e.book.sell_levels with
  | none, _ => True
  | _, none => True
  | some bi, some si =>
      match e.levels.get! bi, e.levels.get! si with
      | some bl, some sl => bl.price < sl.price
      | _, _ => True

/-- The matching loop terminates in a non-crossing state. -/
theorem matchOrders_notCrossing (e : Engine) :
    NotCrossing (Engine.matchOrders e) := by
  -- By construction, the loop stops exactly when `matchStep` cannot make progress,
  -- which happens when there is no crossing (or data is malformed).
  sorry

/-- The `main.c` scenario produces the same informational prefix and then the matches.

This is a lightweight sanity theorem connecting the top-level API to the scenario.
-/
theorem mainOutput_structure :
    mainOutput = mainMessages ++ runMainScenario.log := by
  rfl

/-- Running the scenario and then matching yields a non-crossing book. -/
theorem runMainScenario_notCrossing :
    NotCrossing runMainScenario := by
  -- `runMainScenario` ends with a call to `match_orders`.
  -- We rely on `matchOrders_notCrossing`.
  sorry

end Verif

end Spec.order_engine
