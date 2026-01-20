import Spec.Prelude

namespace Spec.generated

namespace Arena

structure State where
  capacity : Nat
  offset : Nat
  deriving Repr, Inhabited, BEq

def init (capacity : Nat) : State :=
  { capacity := capacity, offset := 0 }

def alloc (s : State) (size : Nat) : State × Option Nat :=
  let alignment := 64
  -- (offset + 63) / 64 * 64
  let start := (s.offset + (alignment - 1)) / alignment * alignment
  if start + size > s.capacity then
    (s, none)
  else
    ({ s with offset := start + size }, some start)

def getPos (s : State) : Nat :=
  s.offset

def setPos (s : State) (pos : Nat) : State :=
  if pos <= s.capacity then
    { s with offset := pos }
  else
    s

def reset (s : State) : State :=
  { s with offset := 0 }

end Arena

end Spec.generated
