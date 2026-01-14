import Spec.Prelude

namespace Spec.order_engine

/-!
Translation of `examples/order_engine/engine.c`.

The original C implementation is a single-instrument limit order book engine using:
* BSTs for price levels (bids: max on right, asks: min on left)
* FIFO queues at each level (doubly-linked list)
* fixed-size pools with free-list stacks for allocation (no malloc)

In Lean we model the same observable behavior as a pure state machine.
We replace pointers with stable pool indices (`Nat`), and make allocation explicit
via free-list stacks.

This file intentionally focuses on the executable semantics used by `main.c`:
`init_engine`, `submit_order`, `match_orders`.
Printing is modeled by accumulating log lines (rather than IO).
-/

abbrev Price := Nat
abbrev Qty := Nat
abbrev OrderUserId := Nat

inductive Side where
  | buy
  | sell
  deriving BEq, DecidableEq, Repr

structure Order where
  id : OrderUserId
  price : Price
  quantity : Qty
  side : Side
  deriving Repr

/-- A price level stores FIFO queue of resting order pool indices. -/
structure Level where
  price : Price
  orders : List Nat
  left : Option Nat
  right : Option Nat
  deriving Repr

structure OrderBook where
  buy_levels : Option Nat
  sell_levels : Option Nat
  deriving Repr

structure Engine where
  /-- Order pool: index -> current order if allocated. -/
  orders : Array (Option Order)
  /-- Level pool: index -> current level if allocated. -/
  levels : Array (Option Level)
  /-- Free list stacks (top at head). -/
  freeOrders : List Nat
  freeLevels : List Nat
  book : OrderBook
  /-- Log of matches (in place of `printf`). -/
  log : List String
  deriving Repr

namespace Engine

/-- Constants from the C header. -/
def MAX_ORDERS : Nat := 1024
/-- Constants from the C header. -/
def MAX_LEVELS : Nat := 256

private def mkFreeList (n : Nat) : List Nat :=
  (List.range n).reverse

/-- `memset(engine,0,...)` + free-list initialization. -/
def init : Engine :=
  { orders := Array.mkArray MAX_ORDERS none
    levels := Array.mkArray MAX_LEVELS none
    freeOrders := mkFreeList MAX_ORDERS
    freeLevels := mkFreeList MAX_LEVELS
    book := { buy_levels := none, sell_levels := none }
    log := [] }

/-- Pop an order index from the free-list. -/
def allocOrder (e : Engine) : (Engine × Option Nat) :=
  match e.freeOrders with
  | [] => (e, none)
  | i :: is => ({ e with freeOrders := is }, some i)

/-- Push an order index back onto the free-list. (No double-free checks.) -/
def freeOrder (e : Engine) (i : Nat) : Engine :=
  if e.freeOrders.length < MAX_ORDERS then
    { e with
      orders := e.orders.set! i none
      freeOrders := i :: e.freeOrders }
  else
    e

/-- Pop a level index from the free-list; the allocated level is reset/cleared. -/
def allocLevel (e : Engine) : (Engine × Option Nat) :=
  match e.freeLevels with
  | [] => (e, none)
  | i :: is =>
      let e' := { e with
        freeLevels := is
        levels := e.levels.set! i (some { price := 0, orders := [], left := none, right := none }) }
      (e', some i)

/-- Push a level index back onto the free-list. -/
def freeLevel (e : Engine) (i : Nat) : Engine :=
  if e.freeLevels.length < MAX_LEVELS then
    { e with
      levels := e.levels.set! i none
      freeLevels := i :: e.freeLevels }
  else
    e

private def getLevel? (e : Engine) (i : Nat) : Option Level :=
  e.levels.get! i

private def setLevel (e : Engine) (i : Nat) (l : Level) : Engine :=
  { e with levels := e.levels.set! i (some l) }

/-- BST lookup (`find_level`).

We implement this using `partial` recursion because the BST is represented via
pool indices without a structural recursion measure available to Lean.
-/
partial def findLevel (e : Engine) (root : Option Nat) (price : Price) : Option Nat :=
  let rec go (r : Option Nat) : Option Nat :=
    match r with
    | none => none
    | some i =>
        match getLevel? e i with
        | none => none
        | some l =>
            if price == l.price then some i
            else if price < l.price then go l.left
            else go l.right
  go root

/-- BST insert (`insert_level`). Returns updated engine + new root + resulting level index (or none on OOM).

Marked `partial` for the same reason as `findLevel`.
-/
partial def insertLevel (e : Engine) (root : Option Nat) (price : Price) : (Engine × Option Nat × Option Nat) :=
  let rec go (e : Engine) (r : Option Nat) : (Engine × Option Nat × Option Nat) :=
    match r with
    | none =>
        let (e1, oi) := allocLevel e
        match oi with
        | none => (e1, none, none)
        | some i =>
            let l := { price := price, orders := [], left := none, right := none }
            let e2 := setLevel e1 i l
            (e2, some i, some i)
    | some i =>
        match getLevel? e i with
        | none => (e, none, some i)
        | some l =>
            if price == l.price then
              (e, some i, some i)
            else if price < l.price then
              let (e', newLeft, res) := go e l.left
              let l' := { l with left := newLeft }
              (setLevel e' i l', some i, res)
            else
              let (e', newRight, res) := go e l.right
              let l' := { l with right := newRight }
              (setLevel e' i l', some i, res)
  go e root

/-- Rightmost node (`get_best_buy`). -/
partial def getBestBuy (e : Engine) (root : Option Nat) : Option Nat :=
  let rec go (r : Option Nat) : Option Nat :=
    match r with
    | none => none
    | some i =>
        match getLevel? e i with
        | none => some i
        | some l =>
            match l.right with
            | none => some i
            | some _ => go l.right
  go root

/-- Leftmost node (`get_best_sell`). -/
partial def getBestSell (e : Engine) (root : Option Nat) : Option Nat :=
  let rec go (r : Option Nat) : Option Nat :=
    match r with
    | none => none
    | some i =>
        match getLevel? e i with
        | none => some i
        | some l =>
            match l.left with
            | none => some i
            | some _ => go l.left
  go root

/-- Remove max node (best buy) from BST (`remove_best_buy_node`). -/
partial def removeBestBuyNode (e : Engine) (root : Option Nat) : (Engine × Option Nat) :=
  let rec go (e : Engine) (r : Option Nat) : (Engine × Option Nat) :=
    match r with
    | none => (e, none)
    | some i =>
        match getLevel? e i with
        | none => (e, none)
        | some l =>
            match l.right with
            | some _ =>
                let (e', newRight) := go e l.right
                let l' := { l with right := newRight }
                (setLevel e' i l', some i)
            | none =>
                -- this is max; replace by left
                let e' := freeLevel e i
                (e', l.left)
  go e root

/-- Remove min node (best sell) from BST (`remove_best_sell_node`). -/
partial def removeBestSellNode (e : Engine) (root : Option Nat) : (Engine × Option Nat) :=
  let rec go (e : Engine) (r : Option Nat) : (Engine × Option Nat) :=
    match r with
    | none => (e, none)
    | some i =>
        match getLevel? e i with
        | none => (e, none)
        | some l =>
            match l.left with
            | some _ =>
                let (e', newLeft) := go e l.left
                let l' := { l with left := newLeft }
                (setLevel e' i l', some i)
            | none =>
                let e' := freeLevel e i
                (e', l.right)
  go e root

/-- Enqueue at tail (FIFO). -/
def enqueueOrderAtLevel (e : Engine) (lvlIdx : Nat) (ordIdx : Nat) : Engine :=
  match getLevel? e lvlIdx with
  | none => e
  | some l =>
      setLevel e lvlIdx { l with orders := l.orders ++ [ordIdx] }

/-- Dequeue from head (FIFO). -/
def dequeueOrderAtLevel (e : Engine) (lvlIdx : Nat) : (Engine × Option Nat) :=
  match getLevel? e lvlIdx with
  | none => (e, none)
  | some l =>
      match l.orders with
      | [] => (e, none)
      | o :: os =>
          let e' := setLevel e lvlIdx { l with orders := os }
          (e', some o)

/-- C `submit_order`. Drops the order on OOM. -/
def submitOrder (e : Engine) (id : OrderUserId) (price : Price) (quantity : Qty) (side : Side) : Engine :=
  let (e1, oi?) := allocOrder e
  match oi? with
  | none => e1
  | some oi =>
      let o : Order := { id := id, price := price, quantity := quantity, side := side }
      let e2 := { e1 with orders := e1.orders.set! oi (some o) }
      let root := match side with | .buy => e2.book.buy_levels | .sell => e2.book.sell_levels
      let (e3, newRoot?, lvlIdx?) := insertLevel e2 root price
      match lvlIdx? with
      | none =>
          -- failed to get level; return order to free list
          freeOrder e3 oi
      | some li =>
          let book' :=
            match side with
            | .buy => { e3.book with buy_levels := newRoot? }
            | .sell => { e3.book with sell_levels := newRoot? }
          let e4 := { e3 with book := book' }
          enqueueOrderAtLevel e4 li oi

private def fmtMatch (buy sell : Order) (qty : Qty) : String :=
  "MATCH: Buy " ++ toString buy.id ++ " @ " ++ toString buy.price ++
  " matches Sell " ++ toString sell.id ++ " @ " ++ toString sell.price ++
  " for " ++ toString qty ++ " qty"

/-- One iteration of the C `while(true)` matching loop. -/
def matchStep (e : Engine) : (Engine × Bool) :=
  let bestBuy? := getBestBuy e e.book.buy_levels
  let bestSell? := getBestSell e e.book.sell_levels
  match bestBuy?, bestSell? with
  | some bi, some si =>
      match getLevel? e bi, getLevel? e si with
      | some bl, some sl =>
          if bl.price < sl.price then
            (e, false)
          else
            match bl.orders, sl.orders with
            | bo :: _, so :: _ =>
                match e.orders.get! bo, e.orders.get! so with
                | some buyO, some sellO =>
                    let qty := Nat.min buyO.quantity sellO.quantity
                    let buyO' := { buyO with quantity := buyO.quantity - qty }
                    let sellO' := { sellO with quantity := sellO.quantity - qty }
                    let e1 := { e with
                      orders := (e.orders.set! bo (some buyO')).set! so (some sellO')
                      log := e.log ++ [fmtMatch buyO sellO qty] }
                    -- cleanup filled orders
                    let (e2, _) :=
                      if buyO'.quantity == 0 then
                        let (eD, o?) := dequeueOrderAtLevel e1 bi
                        match o? with
                        | none => (eD, none)
                        | some oidx => (freeOrder eD oidx, some oidx)
                      else (e1, none)
                    let (e3, _) :=
                      if sellO'.quantity == 0 then
                        let (eD, o?) := dequeueOrderAtLevel e2 si
                        match o? with
                        | none => (eD, none)
                        | some oidx => (freeOrder eD oidx, some oidx)
                      else (e2, none)
                    -- cleanup empty levels
                    let e4 :=
                      match getLevel? e3 bi with
                      | some bl2 =>
                          if bl2.orders.isEmpty then
                            let (eR, newRoot) := removeBestBuyNode e3 e3.book.buy_levels
                            { eR with book := { eR.book with buy_levels := newRoot } }
                          else e3
                      | none => e3
                    let e5 :=
                      match getLevel? e4 si with
                      | some sl2 =>
                          if sl2.orders.isEmpty then
                            let (eR, newRoot) := removeBestSellNode e4 e4.book.sell_levels
                            { eR with book := { eR.book with sell_levels := newRoot } }
                          else e4
                      | none => e4
                    (e5, true)
                | _, _ => (e, false)
            | _, _ => (e, false)
      | _, _ => (e, false)
  | _, _ => (e, false)

/-- Run matching until no further progress is possible. -/
def matchOrders (e : Engine) : Engine :=
  let rec loop (fuel : Nat) (e : Engine) : Engine :=
    match fuel with
    | 0 => e
    | fuel + 1 =>
        let (e', cont) := matchStep e
        if cont then loop fuel e' else e'
  -- fuel bound: at most orders can be fully filled; use a safe upper bound.
  loop (MAX_ORDERS * 2 + MAX_LEVELS * 2) e

end Engine

end Spec.order_engine
