import Src.Prelude

namespace Src

def findTwoSum (target : Int) (arr : List Int) : Option (Nat × Nat) :=
  let rec loopI (i : Nat) : Option (Nat × Nat) :=
    if h : i < arr.length then
      let rec loopJ (j : Nat) : Option (Nat × Nat) :=
        if hj : j < arr.length then
          if arr.get ⟨i, h⟩ + arr.get ⟨j, hj⟩ == target then
            some (i, j)
          else
            loopJ (j + 1)
        else
          none
      match loopJ (i + 1) with
      | some res => some res
      | none => loopI (i + 1)
    else
      none
  loopI 0

def solve : IO Unit := do
  let stdin ← IO.getStdin
  let line1 ← stdin.getLine
  if line1.isEmpty then return
  let parts1 := line1.splitOn " " |>.map String.trim |>.filter (!·.isEmpty)
  if parts1.length < 2 then return
  let target := parts1.get! 0 |>.toInt!
  let n := parts1.get! 1 |>.toNat!
  
  let line2 ← stdin.getLine
  let parts2 := line2.splitOn " " |>.map String.trim |>.filter (!·.isEmpty)
  let arr := parts2.map String.toInt!

  match findTwoSum target arr with
  | some (i, j) => IO.println s!"{i} {j}"
  | none => IO.println "-1 -1"

end Src
