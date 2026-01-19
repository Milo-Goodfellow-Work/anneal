import Spec.Prelude
import Spec.generated.Main

namespace Spec.generated

private def parseNat (s : String) : Nat :=
  match s.toNat? with
  | some n => n
  | none => 0

private def tokens (line : String) : List String :=
  line.trim.splitOn " " |>.filter (fun t => t ≠ "")

partial def loop (stdin : IO.FS.Stream) (n : Nat) (a : Arena) : IO Unit := do
  if n = 0 then
    pure ()
  else
    let line ← stdin.getLine
    if line.isEmpty then
      pure ()
    else
      let ts := tokens line
      match ts with
      | [] => loop stdin (n-1) a
      | op :: rest =>
        match op.get 0 with
        | 'a' =>
          let bytes :=
            match rest with
            | b :: _ => parseNat b
            | _ => 0
          let (a', ok, off) := Arena.alloc a bytes
          IO.println s!"A {(if ok then 1 else 0)} {off} {a'.top}"
          loop stdin (n-1) a'
        | 'p' =>
          let a' := Arena.push a
          IO.println s!"P {a'.top} {a'.marks.length}"
          loop stdin (n-1) a'
        | 'o' =>
          let a' := Arena.pop a
          IO.println s!"O {a'.top} {a'.marks.length}"
          loop stdin (n-1) a'
        | 'r' =>
          let a' := Arena.reset a
          IO.println s!"R {a'.top} {a'.marks.length}"
          loop stdin (n-1) a'
        | _ =>
          loop stdin (n-1) a

/-- Entry point for the Lean differential harness. -/
def harnessMain : IO Unit := do
  let stdin ← IO.getStdin
  let header ← stdin.getLine
  if header.isEmpty then
    pure ()
  else
    let ts := tokens header
    let cap := match ts with | c :: _ => parseNat c | _ => 0
    let steps := match ts with | _ :: s :: _ => parseNat s | _ => 0
    let a := Arena.init cap
    loop stdin steps a

end Spec.generated

/-- The evaluator looks for a top-level `main`. -/
def main : IO Unit := Spec.generated.harnessMain
