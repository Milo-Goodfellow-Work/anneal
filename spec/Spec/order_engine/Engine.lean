import Spec.Prelude

namespace Spec.order_engine

open Spec

/-
Direct Lean translation of `engine.c`.

We model C pointers into fixed-size pools as `Nat` indices into arrays.
A "null pointer" is represented by `none`.

Faithfulness points:
* `alloc_order` does not clear/reset the order contents (C does not `memset`).
* `alloc_level` *does* clear/reset the level contents (C does `memset`).
* `free_order` / `free_level` do not check for double free (C does not).
* BST helpers and best-price selection follow C control flow.
* `match_orders` produces deterministic log lines corresponding to C `printf`.
-/

-- -----------------------------
-- Constants (pool sizes)
-- -----------------------------

def MAX_ORDERS : Nat := 1024

def MAX_LEVELS : Nat := 256

-- -----------------------------
-- Basic types
-- -----------------------------

inductive Side where
  | SIDE_BUY
  | SIDE_SELL
  deriving BEq, Repr, DecidableEq

structure Order where
  id       : U32 := 0
  price    : U32 := 0
  quantity : U32 := 0
  side     : Side := Side.SIDE_BUY
  next     : Option Nat := none
  prev     : Option Nat := none
  deriving Repr

structure Level where
  price       : U32 := 0
  orders_head : Option Nat := none
  orders_tail : Option Nat := none
  left        : Option Nat := none
  right       : Option Nat := none
  deriving Repr

structure OrderBook where
  buy_levels  : Option Nat := none
  sell_levels : Option Nat := none
  deriving Repr

structure Engine where
  order_pool : Array Order
  level_pool : Array Level
  free_orders : Array (Option Nat)
  free_orders_count : Nat
  free_levels : Array (Option Nat)
  free_levels_count : Nat
  book : OrderBook
  deriving Repr

-- -----------------------------
-- Helpers for fixed-size arrays
-- -----------------------------

private def mkArrayReplicate {α : Type} (n : Nat) (a : α) : Array α :=
  Array.mk (List.replicate n a)

private def arrayGetD {α} (arr : Array α) (i : Nat) (d : α) : α :=
  -- `arr[i]!` requires an `Inhabited α` instance; we avoid that requirement
  -- by using `get?` which returns an `Option`.
  match arr.get? i with
  | some v => v
  | none => d

/-- Total array set: out-of-bounds writes are ignored.

In C, out-of-bounds would be UB; here we keep the state unchanged.
-/
private def arraySetSafe {α} (arr : Array α) (i : Nat) (v : α) : Array α :=
  if i < arr.size then arr.set! i v else arr

/-- Build a size-`n` array by mapping over `0..n-1`. -/
private def arrayOfFn {α : Type} (n : Nat) (f : Nat → α) : Array α :=
  Array.mk ((List.range n).map f)

-- -----------------------------
-- Engine initialization
-- -----------------------------

/-- Create an initialized engine state corresponding to C `init_engine`. -/
def init_engine : Engine :=
  let order_pool := mkArrayReplicate MAX_ORDERS {}
  let level_pool := mkArrayReplicate MAX_LEVELS {}
  let free_orders := arrayOfFn MAX_ORDERS (fun i => some i)
  let free_levels := arrayOfFn MAX_LEVELS (fun i => some i)
  {
    order_pool := order_pool
    level_pool := level_pool
    free_orders := free_orders
    free_orders_count := MAX_ORDERS
    free_levels := free_levels
    free_levels_count := MAX_LEVELS
    book := {}
  }

-- -----------------------------
-- Memory management
-- -----------------------------

/-- Pop from free order stack. Returns `(engine', ptr?)`. -/
def alloc_order (e : Engine) : Engine × Option Nat :=
  if 0 < e.free_orders_count then
    let newCount := e.free_orders_count - 1
    let idxOpt := arrayGetD e.free_orders newCount none
    let e := { e with free_orders_count := newCount }
    (e, idxOpt)
  else
    (e, none)

/-- Push onto free order stack if not full.

No double-free protection, mirroring the C behavior.
-/
def free_order (e : Engine) (orderIdx : Nat) : Engine :=
  if e.free_orders_count < MAX_ORDERS then
    let e := { e with free_orders := arraySetSafe e.free_orders e.free_orders_count (some orderIdx) }
    { e with free_orders_count := e.free_orders_count + 1 }
  else
    e

/-- Pop from free level stack and zero the level (C `memset(l,0,sizeof(Level))`). -/
def alloc_level (e : Engine) : Engine × Option Nat :=
  if 0 < e.free_levels_count then
    let newCount := e.free_levels_count - 1
    let idxOpt := arrayGetD e.free_levels newCount none
    let e := { e with free_levels_count := newCount }
    match idxOpt with
    | none => (e, none)
    | some li =>
      let e := { e with level_pool := arraySetSafe e.level_pool li {} }
      (e, some li)
  else
    (e, none)

/-- Push onto free level stack if not full. -/
def free_level (e : Engine) (levelIdx : Nat) : Engine :=
  if e.free_levels_count < MAX_LEVELS then
    let e := { e with free_levels := arraySetSafe e.free_levels e.free_levels_count (some levelIdx) }
    { e with free_levels_count := e.free_levels_count + 1 }
  else
    e

-- -----------------------------
-- Pool accessors
-- -----------------------------

private def getOrder (e : Engine) (i : Nat) : Order :=
  arrayGetD e.order_pool i {}

private def setOrder (e : Engine) (i : Nat) (o : Order) : Engine :=
  { e with order_pool := arraySetSafe e.order_pool i o }

private def getLevel (e : Engine) (i : Nat) : Level :=
  arrayGetD e.level_pool i {}

private def setLevel (e : Engine) (i : Nat) (l : Level) : Engine :=
  { e with level_pool := arraySetSafe e.level_pool i l }

-- -----------------------------
-- BST helpers
-- -----------------------------

/-- Recursive BST search by price (C `find_level`). -/
partial def find_level (e : Engine) (root : Option Nat) (price : U32) : Option Nat :=
  match root with
  | none => none
  | some ri =>
    let r := getLevel e ri
    if price == r.price then
      some ri
    else if price < r.price then
      find_level e r.left price
    else
      find_level e r.right price

/-- Internal BST insertion that updates a given root location using `setRoot`.

Mirrors C `insert_level` (recursive with `Level**`).
-/
private partial def insert_level_at
    (e : Engine)
    (root : Option Nat)
    (setRoot : Option Nat → Engine → Engine)
    (price : U32) : Engine × Option Nat :=
  match root with
  | none =>
    let (e, li?) := alloc_level e
    match li? with
    | none => (e, none)
    | some li =>
      let l := { (getLevel e li) with price := price }
      let e := setLevel e li l
      let e := setRoot (some li) e
      (e, some li)
  | some ri =>
    let r := getLevel e ri
    if price == r.price then
      (e, some ri)
    else if price < r.price then
      let (e, child?) :=
        insert_level_at e r.left
          (fun v e =>
            let r' := { (getLevel e ri) with left := v }
            setLevel e ri r')
          price
      (e, child?)
    else
      let (e, child?) :=
        insert_level_at e r.right
          (fun v e =>
            let r' := { (getLevel e ri) with right := v }
            setLevel e ri r')
          price
      (e, child?)

/-- Insert/find a level in the correct side tree (C `insert_level`). -/
def insert_level (e : Engine) (side : Side) (price : U32) : Engine × Option Nat :=
  match side with
  | Side.SIDE_BUY =>
    insert_level_at e e.book.buy_levels
      (fun v e => { e with book := { e.book with buy_levels := v } })
      price
  | Side.SIDE_SELL =>
    insert_level_at e e.book.sell_levels
      (fun v e => { e with book := { e.book with sell_levels := v } })
      price

/-- Best buy is highest price => rightmost (C `get_best_buy`). -/
partial def get_best_buy (e : Engine) (root : Option Nat) : Option Nat :=
  let rec loop (cur : Option Nat) : Option Nat :=
    match cur with
    | none => none
    | some i =>
      let l := getLevel e i
      match l.right with
      | none => some i
      | some _ => loop l.right
  loop root

/-- Best sell is lowest price => leftmost (C `get_best_sell`). -/
partial def get_best_sell (e : Engine) (root : Option Nat) : Option Nat :=
  let rec loop (cur : Option Nat) : Option Nat :=
    match cur with
    | none => none
    | some i =>
      let l := getLevel e i
      match l.left with
      | none => some i
      | some _ => loop l.left
  loop root

/-- Remove max node from BST (best buy). Returns `(engine', newRoot)`.

Mirrors C `remove_best_buy_node`.
-/
private partial def remove_best_buy_node_at (e : Engine) (root : Option Nat) : Engine × Option Nat :=
  match root with
  | none => (e, none)
  | some ri =>
    let r := getLevel e ri
    match r.right with
    | some rR =>
      let (e, newRight) := remove_best_buy_node_at e (some rR)
      let r' := { (getLevel e ri) with right := newRight }
      (setLevel e ri r', some ri)
    | none =>
      let e := free_level e ri
      (e, r.left)

/-- Remove min node from BST (best sell). Returns `(engine', newRoot)`.

Mirrors C `remove_best_sell_node`.
-/
private partial def remove_best_sell_node_at (e : Engine) (root : Option Nat) : Engine × Option Nat :=
  match root with
  | none => (e, none)
  | some ri =>
    let r := getLevel e ri
    match r.left with
    | some rL =>
      let (e, newLeft) := remove_best_sell_node_at e (some rL)
      let r' := { (getLevel e ri) with left := newLeft }
      (setLevel e ri r', some ri)
    | none =>
      let e := free_level e ri
      (e, r.right)

/-- Remove best buy level from engine book. -/
def remove_best_buy_node (e : Engine) : Engine :=
  let (e, newRoot) := remove_best_buy_node_at e e.book.buy_levels
  { e with book := { e.book with buy_levels := newRoot } }

/-- Remove best sell level from engine book. -/
def remove_best_sell_node (e : Engine) : Engine :=
  let (e, newRoot) := remove_best_sell_node_at e e.book.sell_levels
  { e with book := { e.book with sell_levels := newRoot } }

-- -----------------------------
-- Queue helpers
-- -----------------------------

/-- Enqueue order at tail (FIFO), updating DLL links (C `enqueue_order`). -/
def enqueue_order (e : Engine) (levelIdx : Nat) (orderIdx : Nat) : Engine :=
  let lvl := getLevel e levelIdx
  let o := getOrder e orderIdx
  let o := { o with next := none, prev := lvl.orders_tail }
  let e := setOrder e orderIdx o
  match lvl.orders_tail with
  | some tailIdx =>
    let tail := getOrder e tailIdx
    let tail := { tail with next := some orderIdx }
    let e := setOrder e tailIdx tail
    let lvl := { (getLevel e levelIdx) with orders_tail := some orderIdx }
    setLevel e levelIdx lvl
  | none =>
    let lvl := { lvl with orders_head := some orderIdx, orders_tail := some orderIdx }
    setLevel e levelIdx lvl

/-- Dequeue from head, updating DLL links (C `dequeue_order`).

Returns `(engine', orderIdx?)`.
-/
def dequeue_order (e : Engine) (levelIdx : Nat) : Engine × Option Nat :=
  let lvl := getLevel e levelIdx
  match lvl.orders_head with
  | none => (e, none)
  | some oi =>
    let o := getOrder e oi
    let newHead := o.next
    let e := setLevel e levelIdx { lvl with orders_head := newHead }
    let e :=
      match newHead with
      | some nhi =>
        let nh := getOrder e nhi
        setOrder e nhi { nh with prev := none }
      | none =>
        setLevel e levelIdx { (getLevel e levelIdx) with orders_tail := none }
    let o' := { (getOrder e oi) with next := none, prev := none }
    let e := setOrder e oi o'
    (e, some oi)

-- -----------------------------
-- Logic
-- -----------------------------

/-- Submit a new order (C `submit_order`).

Drops on OOM. If a level cannot be allocated, the order is freed back.
-/
def submit_order (e : Engine) (id price quantity : U32) (side : Side) : Engine :=
  let (e, oi?) := alloc_order e
  match oi? with
  | none => e
  | some oi =>
    let o0 := getOrder e oi
    let o := { o0 with id := id, price := price, quantity := quantity, side := side }
    let e := setOrder e oi o
    let (e, li?) := insert_level e side price
    match li? with
    | none => free_order e oi
    | some li => enqueue_order e li oi

/-- Match loop (C `match_orders`).

Returns `(engine', logs)` where each log line matches the C `printf` format.
-/
partial def match_orders (e : Engine) : Engine × Array String :=
  let rec loop (e : Engine) (logs : Array String) : Engine × Array String :=
    let bestBuy? := get_best_buy e e.book.buy_levels
    let bestSell? := get_best_sell e e.book.sell_levels
    match bestBuy?, bestSell? with
    | some bi, some si =>
      let bestBuy := getLevel e bi
      let bestSell := getLevel e si
      if bestBuy.price < bestSell.price then
        (e, logs)
      else
        match bestBuy.orders_head, bestSell.orders_head with
        | some boi, some soi =>
          let buyOrder := getOrder e boi
          let sellOrder := getOrder e soi
          let qty : U32 := if buyOrder.quantity < sellOrder.quantity then buyOrder.quantity else sellOrder.quantity
          let logs :=
            logs.push
              s!"MATCH: Buy {buyOrder.id} @ {buyOrder.price} matches Sell {sellOrder.id} @ {sellOrder.price} for {qty} qty\n"
          let e := setOrder e boi { buyOrder with quantity := buyOrder.quantity - qty }
          let sellNow := getOrder e soi
          let e := setOrder e soi { sellNow with quantity := sellNow.quantity - qty }
          let e :=
            if (getOrder e boi).quantity == 0 then
              let (e2, o?) := dequeue_order e bi
              match o? with
              | none => e2
              | some oidx => free_order e2 oidx
            else e
          let e :=
            if (getOrder e soi).quantity == 0 then
              let (e2, o?) := dequeue_order e si
              match o? with
              | none => e2
              | some oidx => free_order e2 oidx
            else e
          let e :=
            if (getLevel e bi).orders_head.isNone then
              remove_best_buy_node e
            else e
          let e :=
            if (getLevel e si).orders_head.isNone then
              remove_best_sell_node e
            else e
          loop e logs
        | _, _ => (e, logs)
    | _, _ => (e, logs)
  loop e #[]

end Spec.order_engine
