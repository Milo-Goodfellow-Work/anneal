import Spec.Prelude
import Spec.generated.Main

namespace Spec.generated

private def parseNat (s : String) : Nat :=
  match s.toNat? with
  | some n => n
  | none => 0

private def words (s : String) : List String :=
  (s.trim.splitOn " ").filter (fun w => w != "")

private def readLineTrim (h : IO.FS.Stream) : IO (Option String) := do
  let line ← h.getLine
  if line.isEmpty then
    return none
  else
    return some line.trim

private def mainLoop (stdin : IO.FS.Stream) (steps : Nat) (i : Nat)
    (a : Arena) : IO Unit := do
  if i ≥ steps then
    return ()
  else
    let lineOpt ← readLineTrim stdin
    match lineOpt with
    | none => return ()
    | some line =>
      let ws := words line
      match ws with
      | [] =>
        mainLoop stdin steps (i+1) a
      | op :: rest =>
        match op with
        | "A" =>
          let size := parseNat (rest.getD 0 "0")
          let align := parseNat (rest.getD 1 "0")
          let (a', r) := arenaAlloc a size align
          IO.println s!"{a'.top} {a'.capacity} {(if r.ok then 1 else 0)} {r.offset} {r.size} {r.align}"
          mainLoop stdin steps (i+1) a'
        | "C" =>
          let size := parseNat (rest.getD 0 "0")
          let (a', r) := arenaAllocCacheLine a size
          IO.println s!"{a'.top} {a'.capacity} {(if r.ok then 1 else 0)} {r.offset} {r.size} {r.align}"
          mainLoop stdin steps (i+1) a'
        | "M" =>
          let m := arenaMark a
          IO.println s!"MARK {m}"
          mainLoop stdin steps (i+1) a
        | "R" =>
          let m := parseNat (rest.getD 0 "0")
          let a' := arenaResetToMark a m
          IO.println s!"RESET {a'.top} {a'.capacity}"
          mainLoop stdin steps (i+1) a'
        | "Z" =>
          let a' := arenaReset a
          IO.println s!"ZERO {a'.top} {a'.capacity}"
          mainLoop stdin steps (i+1) a'
        | _ =>
          mainLoop stdin steps (i+1) a

def harnessMain : IO Unit := do
  let stdin ← IO.getStdin
  let headerOpt ← readLineTrim stdin
  match headerOpt with
  | none => return ()
  | some header =>
    let ws := words header
    let cap := parseNat (ws.getD 0 "0")
    let steps := parseNat (ws.getD 1 "0")
    let a := arenaInit cap
    mainLoop stdin steps 0 a

end Spec.generated

/-- Entry point for the differential test runner. -/
def main : IO Unit := Spec.generated.harnessMain
