import Src.Prelude

namespace Src

def solveTwoSum (nums : Array Int) (target : Int) : Option (Nat × Nat) :=
  let rec findSecond (i : Nat) (hi : i < nums.size) (j : Nat) : Option (Nat × Nat) :=
    if hj : j < nums.size then
      if nums[i] + nums[j] == target then
        some (i, j)
      else
        findSecond i hi (j + 1)
    else
      none

  let rec findFirst (i : Nat) : Option (Nat × Nat) :=
    if hi : i < nums.size then
      match findSecond i hi (i + 1) with
      | some res => some res
      | none => findFirst (i + 1)
    else
      none
  
  findFirst 0

partial def main_logic : IO Unit := do
  let stdin ← IO.getStdin
  let rec loop : IO Unit := do
    let line ← stdin.getLine
    if line.isEmpty then return ()
    match line.trim.toNat? with
    | none => return ()
    | some _count =>
      let line2 ← stdin.getLine
      if line2.isEmpty then return ()
      let target := line2.trim.toInt!
      let line3 ← stdin.getLine
      if line3.isEmpty then return ()
      let nums := line3.splitOn " " |>.filter (λ s => !s.isEmpty) |>.map (λ s => s.trim.toInt!) |>.toArray
      match solveTwoSum nums target with
      | some (i, j) => IO.println s!"{i} {j}"
      | none => IO.println "-1 -1"
      loop
  loop

end Src
