import Spec.Prelude

namespace Spec.generated

/-- Cache line size used for alignment. -/
def cacheLine : Nat := 64

/-- Align `n` up to the next multiple of `a`.

This is defined for all `a`; callers should use power-of-two `a` (we use 64).
Uses arithmetic (division) to avoid needing bitwise complement on `Nat`.
-/
@[inline] def alignUp (n a : Nat) : Nat :=
  if a = 0 then n else ((n + (a - 1)) / a) * a

/-- A simple stack-based arena model. `cap` is total bytes.
`top` is current allocation offset. `marks` is a stack of saved `top` values.

This Lean model is purely functional; the C side will use mutable arrays.
-/
structure Arena where
  cap   : Nat
  top   : Nat
  marks : List Nat
  deriving Repr, BEq

@[inline] def Arena.init (cap : Nat) : Arena :=
  { cap := cap, top := 0, marks := [] }

@[inline] def Arena.push (a : Arena) : Arena :=
  { a with marks := a.top :: a.marks }

@[inline] def Arena.pop (a : Arena) : Arena :=
  match a.marks with
  | [] => a
  | m :: ms => { a with top := m, marks := ms }

@[inline] def Arena.reset (a : Arena) : Arena :=
  { a with top := 0, marks := [] }

/-- Allocate `n` bytes aligned to cache line.
Returns `(newArena, ok, offset)` where `offset` is start position if ok else 0.
-/
@[inline] def Arena.alloc (a : Arena) (n : Nat) : Arena × Bool × Nat :=
  let start := alignUp a.top cacheLine
  let newTop := start + n
  if newTop ≤ a.cap then
    ({ a with top := newTop }, true, start)
  else
    (a, false, 0)

@[inline] def Arena.remaining (a : Arena) : Nat :=
  if a.top ≤ a.cap then a.cap - a.top else 0

end Spec.generated
