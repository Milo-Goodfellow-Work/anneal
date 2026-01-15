import Spec.Prelude
import Spec.order_engine.Engine

namespace Spec.order_engine

open Spec

/--
Lean translation of `examples/order_engine/main.c`.

The C `main` performs a deterministic sequence of engine operations and prints
status messages to stdout. For the Lean translation, we preserve the *engine*
behavior but omit the printing; the differential harness for this project
observes behavior through the engine API rather than stdout.
-/
def main : IO Unit := do
  -- C: `Engine engine; init_engine(&engine);`
  let mut engine : Engine := init_engine

  -- C: submit two sell orders: (id=1) 100@100 and (id=2) 50@101
  engine := submit_order engine 1 100 100 Side.SIDE_SELL
  engine := submit_order engine 2 101 50  Side.SIDE_SELL

  -- C: submit buy order (id=3) 50@101
  engine := submit_order engine 3 101 50 Side.SIDE_BUY

  -- C: match_orders(&engine);
  let (engine1, _logs1) := match_orders engine
  engine := engine1

  -- C: submit aggressive buy order (id=4) 150@102
  engine := submit_order engine 4 102 150 Side.SIDE_BUY

  -- C: match_orders(&engine);
  let (_engineFinal, _logs2) := match_orders engine

  pure ()

end Spec.order_engine
