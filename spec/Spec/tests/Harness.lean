import Spec.Prelude
import Spec.order_engine.Engine

namespace Spec.order_engine

open Spec.order_engine

/-- Differential-test harness: same fixed scenario as `main.c`, prints match lines. -/
def main : IO Unit := do
  let e0 := Engine.Engine.init
  let e1 := Engine.Engine.submitOrder e0 1 100 100 Side.sell
  let e2 := Engine.Engine.submitOrder e1 2 101 50 Side.sell
  let e3 := Engine.Engine.submitOrder e2 3 101 50 Side.buy
  let e4 := Engine.Engine.matchOrders e3
  let e5 := Engine.Engine.submitOrder e4 4 102 150 Side.buy
  let e6 := Engine.Engine.matchOrders e5
  for line in e6.log do
    IO.println line

end Spec.order_engine
