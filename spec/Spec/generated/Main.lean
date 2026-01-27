import Spec.Prelude
import Std.Data.HashMap

namespace Spec.generated.Main

def twoSum (nums : Array Int) (target : Int) : Option (Nat × Nat) :=
  let rec loop (i : Nat) (map : Std.HashMap Int Nat) : Option (Nat × Nat) :=
    if h : i < nums.size then
      let x := nums[i]
      let complement := target - x
      match map.get? complement with
      | some j => some (j, i)
      | none => loop (i + 1) (map.insert x i)
    else
      none
  loop 0 Std.HashMap.empty

def main : IO Unit := do
  let stdin ← IO.getStdin
  let stdout ← IO.getStdout
  
  let line1 ← stdin.getLine
  if line1.isEmpty then return
  let n := line1.trim.toNat!
  
  let line2 ← stdin.getLine
  if line2.isEmpty then return
  let target := line2.trim.toInt!
  
  let line3 ← stdin.getLine
  if line3.isEmpty then return
  let nums := line3.splitOn " " |>.filter (fun s => !s.isEmpty) |>.map (fun s => s.trim.toInt!) |>.toArray
  
  match twoSum nums target with
  | some (i, j) => 
    if i < j then
      stdout.putStrLn s!"{i} {j}"
    else
      stdout.putStrLn s!"{j} {i}"
  | none => 
    stdout.putStrLn "-1 -1"

end Spec.generated.Main
