import Spec.Prelude
import Spec.order_engine.Engine2

namespace Spec.order_engine

/-!
Translation of `examples/order_engine/main.c`.

The C program prints a small scenario that:
1. Initializes the engine.
2. Submits two resting sell orders.
3. Submits a buy that crosses.
4. Calls `match_orders`.
5. Submits an aggressive buy and matches again.

In Lean we avoid direct IO; instead we return the final engine state (which
contains a log of executed matches), along with the same informational lines
that `printf` would have produced.
-/

open Engine2

/-- The informational lines printed by `main.c` in order. -/
def mainMessages : List String :=
  [ "Initializing Engine..."
  , "Submitting Sell Orders..."
  , "Submitting Buy Orders..."
  , "Matching..."
  , "Submitting Aggressive Buy..."
  , "Done." ]

/-- Run the `main.c` scenario as a pure state machine, producing the final engine.

This uses the public API wrappers from `Engine2`, which forward to the
executable semantics in `order_engine/Engine.lean`.
-/
def runMainScenario : Spec.order_engine.Engine :=
  let e0 := Engine2.init_engine
  let e1 := Engine2.submit_order e0 1 100 100 .SIDE_SELL
  let e2 := Engine2.submit_order e1 2 101 50 .SIDE_SELL
  let e3 := Engine2.submit_order e2 3 101 50 .SIDE_BUY
  let e4 := Engine2.match_orders e3
  let e5 := Engine2.submit_order e4 4 102 150 .SIDE_BUY
  let e6 := Engine2.match_orders e5
  e6

/-- Combined output that corresponds to `main.c`:

We include the `printf` messages, followed by the match log produced by the
engine during `match_orders`.
-/
def mainOutput : List String :=
  mainMessages ++ runMainScenario.log

end Spec.order_engine
