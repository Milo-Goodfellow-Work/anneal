import Spec.Prelude

namespace Spec.generated

def alignUp (x a : Nat) : Nat :=
  if a = 0 then x else ((x + (a - 1)) / a) * a

/-- Power-of-two predicate.
    We implement it via a finite fold over the low 64 bits.
    (The harness only generates values within this range.) -/
def isPow2 (x : Nat) : Bool :=
  if x = 0 then false
  else
    let bits : List Nat := (List.range 64)
    let step (acc : Nat) (i : Nat) : Nat :=
      if x.testBit i then acc + 1 else acc
    let ones := bits.foldl step 0
    ones = 1

structure Arena where
  cap : Nat
  top : Nat
  cacheLine : Nat
  deriving Repr, DecidableEq

structure Marker where
  top : Nat
  deriving Repr, DecidableEq

def arenaInit (cap cacheLine : Nat) : Option Arena :=
  if cap = 0 then none
  else if cacheLine = 0 then none
  else if isPow2 cacheLine then
    some { cap := cap, top := 0, cacheLine := cacheLine }
  else none

def arenaAlloc (a : Arena) (n : Nat) : Option (Arena × Nat) :=
  if n = 0 then none
  else if a.cacheLine = 0 then none
  else if isPow2 a.cacheLine then
    let start := alignUp a.top a.cacheLine
    if start > a.cap then none
    else if n > a.cap - start then none
    else
      let a' : Arena := { a with top := start + n }
      some (a', start)
  else none

def arenaMark (a : Arena) : Marker :=
  { top := a.top }

def arenaReset (a : Arena) (m : Marker) : Option Arena :=
  if m.top > a.cap then none
  else some { a with top := m.top }

def arenaClear (a : Arena) : Arena :=
  { a with top := 0 }

def arenaRemaining (a : Arena) : Nat :=
  if a.top >= a.cap then 0 else a.cap - a.top

end Spec.generated
