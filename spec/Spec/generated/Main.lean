import Spec.Prelude

namespace Spec.generated

/-- Fixed capacity; must match C. -/
def stackCapacity : Nat := 32

/-- Stack represented as a list (top at head). This is pure and total.
Capacity is enforced by operations (list length never exceeds `stackCapacity`). -/
structure Stack where
  xs : List Int32
  deriving Repr, DecidableEq

def stackEmpty : Stack := { xs := [] }

def stackIsEmpty (s : Stack) : Bool := s.xs.isEmpty

def stackIsFull (s : Stack) : Bool := s.xs.length ≥ stackCapacity

structure StackRes where
  stack : Stack
  ok : Bool
  deriving Repr, DecidableEq

structure StackPopRes where
  stack : Stack
  value : Int32
  ok : Bool
  deriving Repr, DecidableEq

structure StackPeekRes where
  value : Int32
  ok : Bool
  deriving Repr, DecidableEq

def stackPush (s : Stack) (x : Int32) : StackRes :=
  if s.xs.length < stackCapacity then
    { stack := { xs := x :: s.xs }, ok := true }
  else
    { stack := s, ok := false }

def stackPop (s : Stack) : StackPopRes :=
  match s.xs with
  | [] => { stack := s, value := 0, ok := false }
  | y :: ys => { stack := { xs := ys }, value := y, ok := true }

def stackPeek (s : Stack) : StackPeekRes :=
  match s.xs with
  | [] => { value := 0, ok := false }
  | y :: _ => { value := y, ok := true }

end Spec.generated
