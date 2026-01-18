import Spec.Prelude
import Spec.generated.Main

namespace Spec.generated

open Spec.generated

private def parseNat (s : String) : Nat :=
  match s.trim.toNat? with
  | some n => n
  | none => 0

private def splitWS (s : String) : List String :=
  (s.trim.splitOn " ").filter (fun t => t ≠ "")

/-- Read all lines until EOF by catching the end-of-file exception.
    Implemented with `partial` since termination depends on IO. -/
partial def readAllLines : IO (List String) := do
  let stdin ← IO.getStdin
  let rec loop (acc : List String) : IO (List String) := do
    try
      let line ← stdin.getLine
      loop (line :: acc)
    catch _ =>
      return acc.reverse
  loop []

private def run (lines : List String) : IO Unit := do
  match lines with
  | [] => pure ()
  | header :: rest =>
    let hs := splitWS header
    let cap := parseNat (hs.getD 0 "0")
    let cacheLine := parseNat (hs.getD 1 "0")
    match arenaInit cap cacheLine with
    | none =>
      IO.println s!"INIT ERR 1"
    | some a0 =>
      let rec go (a : Arena) (marks : Array Marker) (ls : List String) : IO Unit := do
        match ls with
        | [] => pure ()
        | l :: ls' =>
          let parts := splitWS l
          match parts.getD 0 "" with
          | "A" =>
            let n := parseNat (parts.getD 1 "0")
            match arenaAlloc a n with
            | none =>
              IO.println s!"A FAIL top={a.top} rem={arenaRemaining a}"
              go a marks ls'
            | some (a', off) =>
              IO.println s!"A OK off={off} top={a'.top} rem={arenaRemaining a'}"
              go a' marks ls'
          | "M" =>
            let m := arenaMark a
            let idx := marks.size
            IO.println s!"M idx={idx} top={a.top}"
            go a (marks.push m) ls'
          | "R" =>
            let idx := parseNat (parts.getD 1 "0")
            if h : idx < marks.size then
              let m := marks[idx]
              match arenaReset a m with
              | none =>
                IO.println s!"R FAIL rc=2"
                go a marks ls'
              | some a' =>
                IO.println s!"R OK idx={idx} top={a'.top} rem={arenaRemaining a'}"
                go a' marks ls'
            else
              IO.println s!"R FAIL_BADIDX idx={idx}"
              go a marks ls'
          | "C" =>
            let a' := arenaClear a
            IO.println s!"C OK top={a'.top} rem={arenaRemaining a'}"
            go a' marks ls'
          | _ =>
            go a marks ls'
      go a0 #[] rest

end Spec.generated

/-- Entry point for differential testing. -/
def main : IO Unit := do
  let lines ← Spec.generated.readAllLines
  Spec.generated.run lines
