import Spec.Prelude

namespace Spec.generated

def cacheLine : Nat := 64

structure Arena where
  capacity : Nat
  top : Nat
  deriving Repr, DecidableEq

structure AllocResult where
  ok : Bool
  offset : Nat
  size : Nat
  align : Nat
  deriving Repr, DecidableEq

def isPow2 (n : Nat) : Bool :=
  n > 0 && (n &&& (n - 1) == 0)

/-- Align `x` up to alignment `a` (where `a` is a power of two and > 0).
Implemented with division to avoid requiring bitwise complement on `Nat`. -/
def alignUp (x a : Nat) : Nat :=
  ((x + (a - 1)) / a) * a

def arenaInit (capacity : Nat) : Arena :=
  { capacity := capacity, top := 0 }

def arenaUsed (a : Arena) : Nat := a.top

def arenaRemaining (a : Arena) : Nat :=
  if a.top ≥ a.capacity then 0 else a.capacity - a.top

def arenaAlloc (a : Arena) (size align : Nat) : Arena × AllocResult :=
  let r0 : AllocResult := { ok := false, offset := 0, size := size, align := align }
  if !isPow2 align then
    (a, r0)
  else
    let alignedTop := alignUp a.top align
    if alignedTop > a.capacity then
      (a, r0)
    else
      let avail := a.capacity - alignedTop
      if size > avail then
        (a, r0)
      else
        let r : AllocResult := { r0 with ok := true, offset := alignedTop }
        ({ a with top := alignedTop + size }, r)

def arenaAllocCacheLine (a : Arena) (size : Nat) : Arena × AllocResult :=
  arenaAlloc a size cacheLine

def arenaMark (a : Arena) : Nat := a.top

def arenaResetToMark (a : Arena) (mark : Nat) : Arena :=
  if mark ≤ a.top then { a with top := mark } else a

def arenaReset (a : Arena) : Arena := { a with top := 0 }

end Spec.generated
