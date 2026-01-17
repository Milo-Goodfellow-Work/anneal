import Spec.Prelude
import Spec.generated.Main

namespace Spec.generated

open Spec.generated

private def parseInt32? (s : String) : Option Int32 :=
  match s.trim.toInt? with
  | some i =>
    if i < Int32.minValue.toInt ∨ i > Int32.maxValue.toInt then
      none
    else
      some (Int32.ofInt i)
  | none => none

private def loop (stdin : IO.FS.Stream) (n : Nat) (s : Stack) : IO Unit := do
  if n = 0 then
    pure ()
  else
    let line ← stdin.getLine
    if line.isEmpty then
      pure ()
    else
      let parts := line.trim.splitOn " "
      match parts with
      | ["push", xstr] =>
          match parseInt32? xstr with
          | none =>
              IO.println "push 0"
              loop stdin (n-1) s
          | some x =>
              let r := stackPush s x
              IO.println s!"push {(if r.ok then (1:Nat) else 0)}"
              loop stdin (n-1) r.stack
      | ["pop"] =>
          let r := stackPop s
          if r.ok then
            IO.println s!"pop 1 {r.value}"
          else
            IO.println "pop 0"
          loop stdin (n-1) r.stack
      | ["peek"] =>
          let r := stackPeek s
          if r.ok then
            IO.println s!"peek 1 {r.value}"
          else
            IO.println "peek 0"
          loop stdin (n-1) s
      | ["isEmpty"] =>
          IO.println s!"isEmpty {(if stackIsEmpty s then (1:Nat) else 0)}"
          loop stdin (n-1) s
      | ["isFull"] =>
          IO.println s!"isFull {(if stackIsFull s then (1:Nat) else 0)}"
          loop stdin (n-1) s
      | _ =>
          pure ()

/-- Entry point used by the test runner. -/
def main : IO Unit := do
  let stdin ← IO.getStdin
  let first ← stdin.getLine
  if first.isEmpty then
    pure ()
  else
    match first.trim.toNat? with
    | none => pure ()
    | some n =>
        loop stdin n stackEmpty

end Spec.generated

-- Ensure `main` is in the root namespace for the interpreter.
def main : IO Unit := Spec.generated.main
